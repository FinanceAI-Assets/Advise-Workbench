"""Provider-neutral LLM errors. Every provider translates its native failures into these.

The gateway's resilience middleware decides what to do from the type alone: retry ``retryable`` errors,
count them toward the circuit breaker, and fail over to ``LLM_FALLBACK_PROVIDER`` once retries run out.
All of them subclass ``RuntimeError`` so existing ``except RuntimeError`` callers keep working.
"""

from __future__ import annotations


class LLMError(RuntimeError):
    """Base class. ``provider`` names the provider that failed; the native exception is ``__cause__``."""

    retryable: bool = False

    def __init__(self, message: str, *, provider: str = "", retry_after: float | None = None) -> None:
        super().__init__(f"[{provider}] {message}" if provider else message)
        self.provider = provider
        self.retry_after = retry_after


class LLMConfigError(LLMError, ValueError):
    """The provider is not configured (missing env var, CLI not installed, optional package missing)."""


class LLMAuthError(LLMError):
    """Credentials were rejected (bad key, expired login, no permission for the model)."""


class LLMBadRequestError(LLMError):
    """The request itself is invalid (unknown model, bad parameter, context too long). Retrying will not help."""


class LLMRateLimitError(LLMError):
    """Rate or usage limit hit. ``retry_after`` carries the provider's hint in seconds when it sent one."""

    retryable = True


class LLMTimeoutError(LLMError):
    """The provider did not answer in time."""

    retryable = True


class LLMUnavailableError(LLMError):
    """Transient provider failure: 5xx, overloaded, connection error, or the circuit breaker is open."""

    retryable = True


def status_error(status: int, message: str, *, provider: str, retry_after: float | None = None) -> LLMError:
    """Map an HTTP status code from any provider to the matching error type."""
    if status in (401, 403):
        return LLMAuthError(message, provider=provider)
    if status == 429:
        return LLMRateLimitError(message, provider=provider, retry_after=retry_after)
    if status in (408, 409) or status >= 500:
        return LLMUnavailableError(message, provider=provider, retry_after=retry_after)
    return LLMBadRequestError(message, provider=provider)


def parse_retry_after(value: str | None) -> float | None:
    try:
        return max(0.0, float(value)) if value else None
    except ValueError:
        return None
