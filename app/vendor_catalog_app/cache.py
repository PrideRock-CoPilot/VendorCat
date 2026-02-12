from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Callable, Generic, TypeVar


K = TypeVar("K")
V = TypeVar("V")


class LruTtlCache(Generic[K, V]):
    """Thread-safe in-memory cache with TTL and LRU eviction."""

    def __init__(
        self,
        *,
        enabled: bool,
        ttl_seconds: int,
        max_entries: int,
        clone_value: Callable[[V], V] | None = None,
    ) -> None:
        self._enabled = bool(enabled)
        self._ttl_seconds = max(0, int(ttl_seconds))
        self._max_entries = max(1, int(max_entries))
        self._clone_value = clone_value
        self._lock = threading.Lock()
        self._entries: OrderedDict[K, tuple[float, V]] = OrderedDict()

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def get(self, key: K) -> V | None:
        if not self._enabled or self._ttl_seconds <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at <= now:
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key, last=True)
            return self._clone(value)

    def set(self, key: K, value: V, *, ttl_seconds: int | None = None) -> None:
        if not self._enabled:
            return
        ttl = self._ttl_seconds if ttl_seconds is None else max(0, int(ttl_seconds))
        if ttl <= 0:
            return
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            self._entries[key] = (now + float(ttl), self._clone(value))
            self._entries.move_to_end(key, last=True)
            self._evict_lru()

    def get_or_load(
        self,
        key: K,
        loader: Callable[[], V],
        *,
        ttl_seconds: int | None = None,
    ) -> V:
        if not self._enabled:
            return loader()
        ttl = self._ttl_seconds if ttl_seconds is None else max(0, int(ttl_seconds))
        if ttl <= 0:
            return loader()

        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            entry = self._entries.get(key)
            if entry is not None:
                expires_at, cached_value = entry
                if expires_at > now:
                    self._entries.move_to_end(key, last=True)
                    return self._clone(cached_value)
                self._entries.pop(key, None)

        loaded = loader()
        self.set(key, loaded, ttl_seconds=ttl)
        return loaded

    def _clone(self, value: V) -> V:
        if self._clone_value is None:
            return value
        return self._clone_value(value)

    def _evict_expired(self, now: float) -> None:
        expired_keys = [key for key, (expires_at, _) in self._entries.items() if expires_at <= now]
        for key in expired_keys:
            self._entries.pop(key, None)

    def _evict_lru(self) -> None:
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
