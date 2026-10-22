import json
import logging
import threading
import time

import redis

from src.core.config import settings

log = logging.getLogger("advise_workbench.cache")


class CacheService:
    def __init__(self) -> None:
        # In-memory entries: key -> (expires_at_monotonic, json_str)
        self._mem: dict[str, tuple[float, str]] = {}
        self._mem_lock = threading.Lock()
        self._redis = None
        try:
            self._redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            self._redis.ping()
        except Exception as exc:
            self._redis = None
            if settings.cache_allow_memory_fallback:
                log.warning(
                    "Redis unavailable; using in-memory cache for this process only. "
                    "Set CACHE_ALLOW_MEMORY_FALLBACK=false in multi-replica production to fail fast.",
                    exc_info=exc,
                )
            else:
                raise RuntimeError(
                    "Redis required when CACHE_ALLOW_MEMORY_FALLBACK=false (multi-replica safe cache)."
                ) from exc

    def get(self, key: str) -> dict | None:
        if self._redis:
            raw = self._redis.get(key)
            if not raw:
                return None
            return json.loads(raw)
        ent = self._mem.get(key)
        if not ent:
            return None
        exp_mono, raw = ent
        if time.monotonic() >= exp_mono:
            self._mem.pop(key, None)
            return None
        return json.loads(raw)

    def set(self, key: str, value: dict, ttl_seconds: int) -> None:
        raw = json.dumps(value)
        if self._redis:
            self._redis.setex(key, ttl_seconds, raw)
        else:
            ttl = max(1, int(ttl_seconds))
            self._mem[key] = (time.monotonic() + float(ttl), raw)

    def pop(self, key: str) -> dict | None:
        """Read and delete an entry atomically for one-time exchange values."""
        if self._redis:
            with self._redis.pipeline(transaction=True) as pipe:
                raw = pipe.get(key).delete(key).execute()[0]
            return json.loads(raw) if raw else None
        with self._mem_lock:
            ent = self._mem.pop(key, None)
        if not ent:
            return None
        exp_mono, raw = ent
        return None if time.monotonic() >= exp_mono else json.loads(raw)


cache_service = CacheService()
