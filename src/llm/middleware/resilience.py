"""Retry with backoff and a per-provider circuit breaker, applied by the gateway to every call.

Only ``retryable`` errors (rate limits, timeouts, 5xx, connection failures) are retried and counted toward
the breaker; bad requests and auth failures surface immediately. Waits between attempts call ``on_event``
so a run abort still lands within a fraction of a second.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable
from typing import TypeVar

from src.core.config import settings
from src.llm.errors import LLMError, LLMUnavailableError

logger = logging.getLogger(__name__)

T = TypeVar("T")

_BASE_DELAY_SEC = 1.0
_MAX_BACKOFF_SEC = 20.0
_MAX_RETRY_AFTER_SEC = 60.0
_POLL_SEC = 0.25


class CircuitBreaker:
    """Opens after ``failures`` consecutive retryable failures; lets one trial call through after ``reset_sec``."""

    def __init__(self, label: str, failures: int, reset_sec: float) -> None:
        self.label = label
        self.failures = max(1, failures)
        self.reset_sec = max(1.0, reset_sec)
        self._count = 0
        self._open_until = 0.0
        self._lock = threading.Lock()

    def before_call(self) -> None:
        with self._lock:
            remaining = self._open_until - time.monotonic()
            if remaining <= 0:
                return
        raise LLMUnavailableError(
            f"circuit breaker open after {self.failures} consecutive failures; next attempt in {remaining:.0f}s",
            provider=self.label,
        )

    def record_success(self) -> None:
        with self._lock:
            self._count = 0
            self._open_until = 0.0

    def record_failure(self) -> None:
        with self._lock:
            self._count += 1
            if self._count >= self.failures:
                self._open_until = time.monotonic() + self.reset_sec
                logger.error("LLM circuit breaker opened for %s for %.0fs", self.label, self.reset_sec)

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._open_until > time.monotonic()


_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def get_breaker(label: str) -> CircuitBreaker:
    with _breakers_lock:
        breaker = _breakers.get(label)
        if breaker is None:
            failures = settings.llm_circuit_breaker_failures or settings.anthropic_circuit_breaker_failures
            reset = settings.llm_circuit_breaker_reset_sec or settings.anthropic_circuit_breaker_reset_sec
            breaker = _breakers[label] = CircuitBreaker(label, int(failures), float(reset))
        return breaker


def reset_breakers() -> None:
    with _breakers_lock:
        _breakers.clear()


def backoff_delay(attempt: int, retry_after: float | None) -> float:
    if retry_after is not None:
        return min(retry_after, _MAX_RETRY_AFTER_SEC)
    return min(_MAX_BACKOFF_SEC, _BASE_DELAY_SEC * 2**attempt) * (0.5 + random.random() / 2)  # noqa: S311 — jitter, not crypto


def _wait(delay: float, on_event: Callable[[], None] | None) -> None:
    deadline = time.monotonic() + delay
    while (remaining := deadline - time.monotonic()) > 0:
        if on_event:
            on_event()  # may raise RunAborted
        time.sleep(min(_POLL_SEC, remaining))


def call_with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int,
    on_event: Callable[[], None] | None = None,
    sleep: Callable[[float, Callable[[], None] | None], None] = _wait,
) -> T:
    attempt = 0
    while True:
        try:
            return fn()
        except LLMError as exc:
            if not exc.retryable or attempt >= max_retries:
                raise
            delay = backoff_delay(attempt, exc.retry_after)
            attempt += 1
            logger.warning("LLM call failed (%s); retry %d/%d in %.1fs", exc, attempt, max_retries, delay)
            sleep(delay, on_event)
