from __future__ import annotations

import time
from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pandas as pd

from vendor_catalog_app.core.env import TVENDOR_USAGE_LOG_MIN_INTERVAL_SEC, get_env


class RepositoryCoreCacheMixin:
    @staticmethod
    def _clone_cache_value(value: Any) -> Any:
        if isinstance(value, pd.DataFrame):
            return value.copy(deep=True)
        if isinstance(value, (list, dict, set, tuple)):
            return deepcopy(value)
        return value

    def _cache_clear(self) -> None:
        self._repo_cache.clear()

    def close(self) -> None:
        self.client.close()

    def _cached(
        self,
        key: tuple[Any, ...],
        loader: Callable[[], Any],
        *,
        ttl_seconds: int | None = None,
    ) -> Any:
        ttl = self._repo_cache_ttl_seconds if ttl_seconds is None else max(0, int(ttl_seconds))
        return self._repo_cache.get_or_load(key, loader, ttl_seconds=ttl)

    def _allow_usage_event(
        self,
        *,
        user_principal: str,
        page_name: str,
        event_type: str,
    ) -> bool:
        raw_value = get_env(TVENDOR_USAGE_LOG_MIN_INTERVAL_SEC, "120")
        try:
            min_interval = max(0, int(str(raw_value).strip() or "120"))
        except Exception:
            min_interval = 120
        if min_interval <= 0:
            return True

        key = (
            str(user_principal or "").strip().lower(),
            str(page_name or "").strip().lower(),
            str(event_type or "").strip().lower(),
        )
        if not all(key):
            return True

        now = time.monotonic()
        with self._usage_event_lock:
            last_seen = float(self._usage_event_last_seen.get(key, 0.0))
            if (now - last_seen) < float(min_interval):
                return False
            self._usage_event_last_seen[key] = now
            if len(self._usage_event_last_seen) > 5000:
                self._usage_event_last_seen.pop(next(iter(self._usage_event_last_seen)))
        return True

