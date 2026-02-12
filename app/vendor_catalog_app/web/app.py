from __future__ import annotations

import hmac
import logging
from pathlib import Path
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from vendor_catalog_app.db import (
    clear_request_perf_context,
    get_request_perf_context,
    start_request_perf_context,
)
from vendor_catalog_app.env import (
    TVENDOR_ALLOW_DEFAULT_SESSION_SECRET,
    TVENDOR_METRICS_ALLOW_UNAUTHENTICATED,
    TVENDOR_METRICS_AUTH_TOKEN,
    TVENDOR_PERF_LOG_ENABLED,
    TVENDOR_PERF_RESPONSE_HEADER,
    TVENDOR_REQUEST_ID_HEADER_ENABLED,
    TVENDOR_SECURITY_HEADERS_ENABLED,
    TVENDOR_SESSION_HTTPS_ONLY,
    TVENDOR_SESSION_SECRET,
    TVENDOR_SLOW_QUERY_MS,
    TVENDOR_SQL_PRELOAD_ON_STARTUP,
    get_env,
    get_env_bool,
    get_env_float,
)
from vendor_catalog_app.local_db_bootstrap import ensure_local_db_ready
from vendor_catalog_app.logging import setup_app_logging
from vendor_catalog_app.observability import get_observability_manager
from vendor_catalog_app.repository_errors import SchemaBootstrapRequiredError
from vendor_catalog_app.web.bootstrap_diagnostics import (
    bootstrap_diagnostics_authorized,
    build_bootstrap_diagnostics_payload,
)
from vendor_catalog_app.web.errors import ApiError, api_error_response, is_api_request, normalize_exception
from vendor_catalog_app.web.routers import router as web_router
from vendor_catalog_app.web.services import get_config, get_repo, resolve_databricks_request_identity

LOGGER = logging.getLogger(__name__)
PERF_LOGGER = logging.getLogger("vendor_catalog_app.perf")


def _route_path_label(request: Request) -> str:
    route = request.scope.get("route")
    route_path = str(getattr(route, "path", "") or "").strip()
    if route_path:
        return route_path
    return str(request.url.path or "/")


def _request_matches_token(request: Request, *, token: str, header_name: str) -> bool:
    expected = str(token or "").strip()
    if not expected:
        return False
    header_value = str(request.headers.get(header_name, "")).strip()
    if header_value and hmac.compare_digest(header_value, expected):
        return True
    auth_header = str(request.headers.get("authorization", "")).strip()
    if auth_header.lower().startswith("bearer "):
        bearer = auth_header[7:].strip()
        if bearer and hmac.compare_digest(bearer, expected):
            return True
    return False


def create_app() -> FastAPI:
    setup_app_logging()
    config = get_config()
    session_secret = get_env(TVENDOR_SESSION_SECRET, "vendor-catalog-dev-secret")
    allow_default_session_secret = get_env_bool(TVENDOR_ALLOW_DEFAULT_SESSION_SECRET, default=False)
    if (
        not config.is_dev_env
        and session_secret == "vendor-catalog-dev-secret"
        and not allow_default_session_secret
    ):
        raise RuntimeError(
            "TVENDOR_SESSION_SECRET must be set to a strong, non-default value outside dev/local environments."
        )
    session_https_only = get_env_bool(TVENDOR_SESSION_HTTPS_ONLY, default=not config.is_dev_env)
    security_headers_enabled = get_env_bool(TVENDOR_SECURITY_HEADERS_ENABLED, default=True)
    metrics_allow_unauthenticated = get_env_bool(
        TVENDOR_METRICS_ALLOW_UNAUTHENTICATED,
        default=config.is_dev_env,
    )
    metrics_auth_token = get_env(TVENDOR_METRICS_AUTH_TOKEN, "")

    app = FastAPI(title="Vendor Catalog")
    observability = get_observability_manager()
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        same_site="lax",
        https_only=session_https_only,
    )
    perf_enabled = get_env_bool(TVENDOR_PERF_LOG_ENABLED, default=False)
    perf_header_enabled = get_env_bool(TVENDOR_PERF_RESPONSE_HEADER, default=True)
    request_id_header_enabled = get_env_bool(TVENDOR_REQUEST_ID_HEADER_ENABLED, default=True)
    sql_preload_on_startup = get_env_bool(TVENDOR_SQL_PRELOAD_ON_STARTUP, default=False)
    slow_query_ms = max(1.0, get_env_float(TVENDOR_SLOW_QUERY_MS, default=750.0, min_value=1.0))

    base_dir = Path(__file__).resolve().parent
    templates = Jinja2Templates(directory=str(base_dir / "templates"))
    app.state.templates = templates

    if security_headers_enabled:

        @app.middleware("http")
        async def _security_headers_middleware(request: Request, call_next):
            response = await call_next(request)
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
            if session_https_only:
                response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
            return response

    @app.middleware("http")
    async def _request_perf_middleware(request: Request, call_next):
        request_id = uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        token = start_request_perf_context(
            request_id=request_id,
            method=request.method,
            path=str(request.url.path),
            slow_query_ms=slow_query_ms,
        )
        started = time.perf_counter()
        response = None
        status_code = 500
        route_path = str(request.url.path)
        try:
            response = await call_next(request)
            status_code = response.status_code
            route_path = _route_path_label(request)
            return response
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            ctx = get_request_perf_context() or {}
            db_calls = int(ctx.get("db_calls", 0))
            db_total_ms = float(ctx.get("db_total_ms", 0.0))
            db_max_ms = float(ctx.get("db_max_ms", 0.0))
            db_cache_hits = int(ctx.get("db_cache_hits", 0))
            db_errors = int(ctx.get("db_errors", 0))
            slow_queries = list(ctx.get("slow_queries", []))
            request_id = str(ctx.get("request_id") or request_id or "-")

            route_path = _route_path_label(request)
            observability.record_request(
                method=request.method,
                path=route_path,
                status_code=status_code,
                elapsed_ms=elapsed_ms,
                db_calls=db_calls,
                db_total_ms=db_total_ms,
                db_cache_hits=db_cache_hits,
                db_errors=db_errors,
            )

            if perf_enabled:
                PERF_LOGGER.info(
                    (
                        "request_perf id=%s method=%s path=%s status=%s total_ms=%.2f "
                        "db_calls=%s db_ms=%.2f db_max_ms=%.2f db_cache_hits=%s db_errors=%s"
                    ),
                    request_id,
                    request.method,
                    route_path,
                    status_code,
                    elapsed_ms,
                    db_calls,
                    db_total_ms,
                    db_max_ms,
                    db_cache_hits,
                    db_errors,
                    extra={
                        "event": "request_perf",
                        "request_id": request_id,
                        "method": request.method,
                        "path": route_path,
                        "status_code": status_code,
                        "total_ms": round(float(elapsed_ms), 2),
                        "db_calls": int(db_calls),
                        "db_ms": round(float(db_total_ms), 2),
                        "db_max_ms": round(float(db_max_ms), 2),
                        "db_cache_hits": int(db_cache_hits),
                        "db_errors": int(db_errors),
                    },
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
                        extra={
                            "event": "request_slow_sql",
                            "request_id": request_id,
                            "operation": query.get("operation"),
                            "elapsed_ms": float(query.get("elapsed_ms") or 0.0),
                            "cached": bool(query.get("cached")),
                            "rows": query.get("rows"),
                            "sql_hash": query.get("sql_hash"),
                            "sql_preview": query.get("sql"),
                        },
                    )

            if response is not None:
                if request_id_header_enabled:
                    response.headers["X-Request-ID"] = request_id
                if perf_enabled and perf_header_enabled:
                    response.headers["X-TVendor-Perf"] = (
                        f"total_ms={elapsed_ms:.2f};db_ms={db_total_ms:.2f};db_calls={db_calls};cache_hits={db_cache_hits}"
                    )

            clear_request_perf_context(token)

    if observability.prometheus_enabled:

        @app.get(observability.prometheus_path, include_in_schema=False)
        async def _prometheus_metrics(request: Request) -> PlainTextResponse:
            if not metrics_allow_unauthenticated:
                if not metrics_auth_token or not _request_matches_token(
                    request,
                    token=metrics_auth_token,
                    header_name="x-tvendor-metrics-token",
                ):
                    return PlainTextResponse("Not found.", status_code=404)
            return PlainTextResponse(
                observability.render_prometheus(),
                media_type="text/plain; version=0.0.4; charset=utf-8",
            )

    @app.exception_handler(SchemaBootstrapRequiredError)
    async def _schema_bootstrap_exception_handler(request: Request, exc: SchemaBootstrapRequiredError):
        if is_api_request(request):
            spec = normalize_exception(exc)
            return api_error_response(
                request,
                status_code=spec.status_code,
                code=spec.code,
                message=spec.message,
                details=spec.details,
            )
        try:
            repo = get_repo()
            config = get_config()
            if bootstrap_diagnostics_authorized(request, config):
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

    @app.exception_handler(ApiError)
    async def _api_error_exception_handler(request: Request, exc: ApiError):
        if not is_api_request(request):
            return PlainTextResponse(str(exc), status_code=exc.status_code)
        spec = normalize_exception(exc)
        return api_error_response(
            request,
            status_code=spec.status_code,
            code=spec.code,
            message=spec.message,
            details=spec.details,
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation_error_handler(request: Request, exc: RequestValidationError):
        if not is_api_request(request):
            return await request_validation_exception_handler(request, exc)
        spec = normalize_exception(exc)
        return api_error_response(
            request,
            status_code=spec.status_code,
            code=spec.code,
            message=spec.message,
            details=spec.details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error_handler(request: Request, exc: StarletteHTTPException):
        if not is_api_request(request):
            return await http_exception_handler(request, exc)
        spec = normalize_exception(exc)
        return api_error_response(
            request,
            status_code=spec.status_code,
            code=spec.code,
            message=spec.message,
            details=spec.details,
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        if not is_api_request(request):
            LOGGER.exception(
                "Unhandled web request error. path=%s method=%s",
                request.url.path,
                request.method,
                extra={
                    "event": "unhandled_web_error",
                    "request_id": str(getattr(request.state, "request_id", "-")),
                    "method": request.method,
                    "path": str(request.url.path),
                },
            )
            return PlainTextResponse("An unexpected error occurred.", status_code=500)

        spec = normalize_exception(exc)
        log_fn = LOGGER.warning if spec.status_code < 500 else LOGGER.exception
        log_fn(
            "API request failed. code=%s status=%s path=%s method=%s",
            spec.code,
            spec.status_code,
            request.url.path,
            request.method,
            extra={
                "event": "api_error",
                "request_id": str(getattr(request.state, "request_id", "-")),
                "error_code": spec.code,
                "status_code": int(spec.status_code),
                "method": request.method,
                "path": str(request.url.path),
            },
        )
        return api_error_response(
            request,
            status_code=spec.status_code,
            code=spec.code,
            message=spec.message,
            details=spec.details,
        )

    @app.on_event("startup")
    async def _startup_local_db_bootstrap() -> None:
        config = get_config()
        ensure_local_db_ready(config)
        if not sql_preload_on_startup:
            return
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

    @app.on_event("shutdown")
    async def _shutdown_repo_resources() -> None:
        if get_repo.cache_info().currsize == 0:
            return
        try:
            get_repo().close()
        except Exception:
            LOGGER.warning("Failed to close repository resources cleanly.", exc_info=True)
        finally:
            get_repo.cache_clear()

    app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")
    app.include_router(web_router)
    return app


app = create_app()
