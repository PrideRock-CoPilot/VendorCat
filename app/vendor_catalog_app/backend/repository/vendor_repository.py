from __future__ import annotations

import threading
from typing import Any

from vendor_catalog_app.backend.repository_mixins import (
    RepositoryAdminMixin,
    RepositoryCoreMixin,
    RepositoryDocumentsMixin,
    RepositoryIdentityMixin,
    RepositoryLookupMixin,
    RepositoryOfferingMixin,
    RepositoryProjectMixin,
    RepositoryReportingMixin,
    RepositoryWorkflowMixin,
)
from vendor_catalog_app.core.config import AppConfig
from vendor_catalog_app.core.env import (
    TVENDOR_REPO_CACHE_ENABLED,
    TVENDOR_REPO_CACHE_MAX_ENTRIES,
    TVENDOR_REPO_CACHE_TTL_SEC,
    get_env_bool,
    get_env_int,
)
from vendor_catalog_app.infrastructure.cache import LruTtlCache
from vendor_catalog_app.infrastructure.db import DatabricksSQLClient


class VendorRepository(
    RepositoryCoreMixin,
    RepositoryIdentityMixin,
    RepositoryReportingMixin,
    RepositoryOfferingMixin,
    RepositoryProjectMixin,
    RepositoryDocumentsMixin,
    RepositoryWorkflowMixin,
    RepositoryLookupMixin,
    RepositoryAdminMixin,
):
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.client = DatabricksSQLClient(config)
        self._runtime_tables_ensured = False
        self._local_lookup_table_ensured = False
        self._local_offering_columns_ensured = False
        self._local_offering_extension_tables_ensured = False
        self._repo_cache_enabled = get_env_bool(TVENDOR_REPO_CACHE_ENABLED, default=True)
        self._repo_cache_ttl_seconds = max(
            0,
            get_env_int(TVENDOR_REPO_CACHE_TTL_SEC, default=120, min_value=0),
        )
        self._repo_cache_max_entries = max(
            32,
            get_env_int(TVENDOR_REPO_CACHE_MAX_ENTRIES, default=512, min_value=1),
        )
        self._repo_cache = LruTtlCache[tuple[Any, ...], Any](
            enabled=self._repo_cache_enabled,
            ttl_seconds=self._repo_cache_ttl_seconds,
            max_entries=self._repo_cache_max_entries,
            clone_value=self._clone_cache_value,
        )
        self._usage_event_lock = threading.Lock()
        self._usage_event_last_seen: dict[tuple[str, str, str], float] = {}
