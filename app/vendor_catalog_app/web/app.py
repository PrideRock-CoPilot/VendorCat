from __future__ import annotations

import logging
import os
from pathlib import Path
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from vendor_catalog_app.db import (
    clear_request_perf_context,
    get_request_perf_context,
    start_request_perf_context,
)
from vendor_catalog_app.local_db_bootstrap import ensure_local_db_ready
from vendor_catalog_app.logging import setup_app_logging
from vendor_catalog_app.repository import SchemaBootstrapRequiredError
from vendor_catalog_app.web.bootstrap_diagnostics import build_bootstrap_diagnostics_payload
from vendor_catalog_app.web.routers import router as web_router
from vendor_catalog_app.web.services import get_config, get_repo, resolve_databricks_request_identity

LOGGER = logging.getLogger(__name__)
PERF_LOGGER = logging.getLogger("vendor_catalog_app.perf")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(str(value or "").strip())
    except Exception:
        return float(default)


def create_app() -> FastAPI:
    setup_app_logging()
    app = FastAPI(title="Vendor Catalog")
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.getenv("TVENDOR_SESSION_SECRET", "vendor-catalog-dev-secret"),
        same_site="lax",
        https_only=False,
    )
    perf_enabled = _as_bool(os.getenv("TVENDOR_PERF_LOG_ENABLED"), default=False)
    perf_header_enabled = _as_bool(os.getenv("TVENDOR_PERF_RESPONSE_HEADER"), default=True)
    slow_query_ms = max(1.0, _as_float(os.getenv("TVENDOR_SLOW_QUERY_MS"), default=750.0))

    base_dir = Path(__file__).resolve().parent
    templates = Jinja2Templates(directory=str(base_dir / "templates"))
    app.state.templates = templates

    @app.middleware("http")
    async def _request_perf_middleware(request: Request, call_next):
        if not perf_enabled:
            return await call_next(request)

        token = start_request_perf_context(
            request_id=uuid.uuid4().hex[:12],
            method=request.method,
            path=request.url.path,
            slow_query_ms=slow_query_ms,
        )
        started = time.perf_counter()
        response = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            ctx = get_request_perf_context() or {}
            db_calls = int(ctx.get("db_calls", 0))
            db_total_ms = float(ctx.get("db_total_ms", 0.0))
            db_max_ms = float(ctx.get("db_max_ms", 0.0))
            db_cache_hits = int(ctx.get("db_cache_hits", 0))
            slow_queries = list(ctx.get("slow_queries", []))
            request_id = str(ctx.get("request_id") or "-")

            PERF_LOGGER.info(
                (
                    "request_perf id=%s method=%s path=%s status=%s total_ms=%.2f "
                    "db_calls=%s db_ms=%.2f db_max_ms=%.2f db_cache_hits=%s"
                ),
                request_id,
                request.method,
                request.url.path,
                status_code,
                elapsed_ms,
                db_calls,
                db_total_ms,
                db_max_ms,
                db_cache_hits,
            )
            for query in slow_queries:
                PERF_LOGGER.warning(
                    "request_slow_sql id=%s op=%s ms=%.2f cached=%s rows=%s hash=%s sql=%s",
                    request_id,
                    query.get("operation"),
                    float(query.get("elapsed_ms") or 0.0),
                    query.get("cached"),
                    query.get("rows"),
                    query.get("sql_hash"),
                    query.get("sql"),
                )

            if response is not None and perf_header_enabled:
                response.headers["X-TVendor-Perf"] = (
                    f"total_ms={elapsed_ms:.2f};db_ms={db_total_ms:.2f};db_calls={db_calls};cache_hits={db_cache_hits}"
                )

            clear_request_perf_context(token)

    @app.exception_handler(SchemaBootstrapRequiredError)
    async def _schema_bootstrap_exception_handler(request: Request, exc: SchemaBootstrapRequiredError):
        try:
            repo = get_repo()
            config = get_config()
            identity = resolve_databricks_request_identity(request)
            diagnostics, _status_code = build_bootstrap_diagnostics_payload(repo, config, identity)
            return templates.TemplateResponse(
                request,
                "bootstrap_diagnostics.html",
                {
                    "request": request,
                    "diagnostics": diagnostics,
                    "error_message": str(exc),
                },
                status_code=503,
            )
        except Exception:
            pass
        return templates.TemplateResponse(
            request,
            "bootstrap_required.html",
            {"request": request, "error_message": str(exc)},
            status_code=503,
        )

    @app.on_event("startup")
    async def _startup_local_db_bootstrap() -> None:
        config = get_config()
        ensure_local_db_ready(config)

    app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")
    app.include_router(web_router)
    return app


app = create_app()
