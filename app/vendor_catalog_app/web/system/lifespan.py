from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from vendor_catalog_app.infrastructure.local_db_bootstrap import ensure_local_db_ready
from vendor_catalog_app.web.core.runtime import get_config, get_repo
from vendor_catalog_app.web.system.settings import AppRuntimeSettings


LOGGER = logging.getLogger(__name__)


def create_app_lifespan(settings: AppRuntimeSettings):
    @asynccontextmanager
    async def _app_lifespan(_app: FastAPI):
        runtime_config = get_config()
        ensure_local_db_ready(runtime_config)
        if settings.sql_preload_on_startup:
            try:
                loaded = get_repo().preload_sql_templates()
            except Exception:
                LOGGER.exception("SQL template preload failed during startup.")
                raise
            LOGGER.info(
                "SQL templates preloaded during startup. files=%s",
                loaded,
                extra={
                    "event": "sql_preload_startup",
                    "sql_files_loaded": int(loaded),
                },
            )
        try:
            yield
        finally:
            repo = get_repo()
            if repo.cache_info().currsize == 0:
                return
            try:
                repo.close()
            except Exception:
                LOGGER.warning("Failed to close repository resources cleanly.", exc_info=True)
            finally:
                repo.cache_clear()

    return _app_lifespan
