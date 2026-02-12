from __future__ import annotations

from contextlib import asynccontextmanager
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
    TVENDOR_CSP_ENABLED,
    TVENDOR_CSP_POLICY,
    TVENDOR_DATABRICKS_REPORTS_ALLOWED_HOSTS,
    TVENDOR_DATABRICKS_REPORTS_ALLOW_EMBED,
    TVENDOR_ALLOW_DEFAULT_SESSION_SECRET,
    TVENDOR_CSRF_ENABLED,
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
    TVENDOR_WRITE_RATE_LIMIT_ENABLED,
    TVENDOR_WRITE_RATE_LIMIT_MAX_REQUESTS,
    TVENDOR_WRITE_RATE_LIMIT_WINDOW_SEC,
    get_env,
    get_env_bool,
    get_env_float,
    get_env_int,
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
from vendor_catalog_app.web.security_controls import (
    CSRF_HEADER,
    ensure_csrf_token,
    request_matches_csrf_token,
    request_rate_limit_key,
    request_requires_write_protection,
    SlidingWindowRateLimiter,
)
from vendor_catalog_app.web.services import get_config, get_repo, resolve_databricks_request_identity

LOGGER = logging.getLogger(__name__)
PERF_LOGGER = logging.getLogger("vendor_catalog_app.perf")
DEFAULT_CSP_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "object-src 'none'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; "
    "connect-src 'self'; "
    "form-action 'self'"
)


def _normalize_host_value(raw_host: str) -> str:
    host = str(raw_host or "").strip().lower()
    if not host:
        return ""
    host = host.replace("https://", "").replace("http://", "").strip("/")
    if "/" in host:
        host = host.split("/", 1)[0].strip()
    if ":" in host:
        host = host.split(":", 1)[0].strip()
    return host


def _build_csp_policy(base_policy: str, *, databricks_host: str) -> str:
    policy = str(base_policy or "").strip()
    if not policy:
        return policy
    if "frame-src" in policy.lower():
        return policy

    host_values: list[str] = []
    if databricks_host:
        host_values.append(databricks_host)
    for token in get_env(TVENDOR_DATABRICKS_REPORTS_ALLOWED_HOSTS, "").split(","):
        cleaned = _normalize_host_value(token)
        if cleaned:
            host_values.append(cleaned)
    deduped = list(dict.fromkeys(host_values))
    if not deduped:
        return policy

    frame_sources = " ".join(f"https://{host}" for host in deduped)
    return f"{policy}; frame-src 'self' {frame_sources}"


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
    csrf_enabled = get_env_bool(TVENDOR_CSRF_ENABLED, default=not config.is_dev_env)
    write_rate_limit_enabled = get_env_bool(TVENDOR_WRITE_RATE_LIMIT_ENABLED, default=not config.is_dev_env)
    write_rate_limit_window_sec = get_env_int(
        TVENDOR_WRITE_RATE_LIMIT_WINDOW_SEC,
        default=60,
        min_value=1,
    )
    write_rate_limit_max_requests = get_env_int(
        TVENDOR_WRITE_RATE_LIMIT_MAX_REQUESTS,
        default=120,
        min_value=1,
    )
    csp_enabled = get_env_bool(TVENDOR_CSP_ENABLED, default=True)
    raw_csp_policy = get_env(TVENDOR_CSP_POLICY, DEFAULT_CSP_POLICY)
    allow_databricks_embed = get_env_bool(TVENDOR_DATABRICKS_REPORTS_ALLOW_EMBED, default=False)
    csp_policy = (
        _build_csp_policy(
            raw_csp_policy,
            databricks_host=_normalize_host_value(config.databricks_server_hostname),
        )
        if allow_databricks_embed
        else raw_csp_policy
    )
    write_rate_limiter = SlidingWindowRateLimiter(
        enabled=write_rate_limit_enabled,
        max_requests=write_rate_limit_max_requests,
        window_seconds=write_rate_limit_window_sec,
    )

    perf_enabled = get_env_bool(TVENDOR_PERF_LOG_ENABLED, default=False)
    perf_header_enabled = get_env_bool(TVENDOR_PERF_RESPONSE_HEADER, default=True)
    request_id_header_enabled = get_env_bool(TVENDOR_REQUEST_ID_HEADER_ENABLED, default=True)
    sql_preload_on_startup = get_env_bool(TVENDOR_SQL_PRELOAD_ON_STARTUP, default=False)
    slow_query_ms = max(1.0, get_env_float(TVENDOR_SLOW_QUERY_MS, default=750.0, min_value=1.0))

    @asynccontextmanager
    async def _app_lifespan(_app: FastAPI):
        runtime_config = get_config()
        ensure_local_db_ready(runtime_config)
        if sql_preload_on_startup:
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
            if get_repo.cache_info().currsize == 0:
                return
            try:
                get_repo().close()
            except Exception:
                LOGGER.warning("Failed to close repository resources cleanly.", exc_info=True)
            finally:
                get_repo.cache_clear()

    app = FastAPI(title="Vendor Catalog", lifespan=_app_lifespan)
    observability = get_observability_manager()

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
            if csp_enabled and csp_policy:
                response.headers.setdefault("Content-Security-Policy", csp_policy)
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
            csrf_token = ensure_csrf_token(request)
            request.state.csrf_token = csrf_token
            if csrf_enabled and request_requires_write_protection(request.method):
                if not await request_matches_csrf_token(
                    request,
                    expected_token=csrf_token,
                    header_name=CSRF_HEADER,
                ):
                    LOGGER.warning(
                        "Blocked write request due to invalid CSRF token. method=%s path=%s",
                        request.method,
                        request.url.path,
                        extra={
                            "event": "csrf_validation_failed",
                            "method": request.method,
                            "path": str(request.url.path),
                        },
                    )
                    message = "Invalid CSRF token. Refresh and try again."
                    if is_api_request(request):
                        response = api_error_response(
                            request,
                            status_code=403,
                            code="FORBIDDEN",
                            message=message,
                        )
                    else:
                        response = PlainTextResponse(message, status_code=403)
                    status_code = response.status_code
                    return response

            if request_requires_write_protection(request.method):
                limiter_key = f"{request_rate_limit_key(request)}:{request.method.upper()}"
                allowed, retry_after = write_rate_limiter.allow(limiter_key)
                if not allowed:
                    LOGGER.warning(
                        (
                            "Blocked write request due to rate limit. method=%s path=%s "
                            "window_sec=%s max_requests=%s retry_after=%s"
                        ),
                        request.method,
                        request.url.path,
                        write_rate_limit_window_sec,
                        write_rate_limit_max_requests,
                        retry_after,
                        extra={
                            "event": "write_rate_limit_blocked",
                            "method": request.method,
                            "path": str(request.url.path),
                            "window_sec": int(write_rate_limit_window_sec),
                            "max_requests": int(write_rate_limit_max_requests),
                            "retry_after_sec": int(retry_after),
                        },
                    )
                    message = "Too many write requests. Please retry shortly."
                    if is_api_request(request):
                        response = api_error_response(
                            request,
                            status_code=429,
                            code="TOO_MANY_REQUESTS",
                            message=message,
                        )
                    else:
                        response = PlainTextResponse(message, status_code=429)
                    response.headers["Retry-After"] = str(max(1, int(retry_after)))
                    status_code = response.status_code
                    return response

            try:
                response = await call_next(request)
            except Exception as exc:
                spec = normalize_exception(exc)
                status_code = int(spec.status_code)
                if is_api_request(request):
                    response = api_error_response(
                        request,
                        status_code=spec.status_code,
                        code=spec.code,
                        message=spec.message,
                        details=spec.details,
                    )
                else:
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
                    response = PlainTextResponse("An unexpected error occurred.", status_code=500)
                status_code = response.status_code
                return response
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

    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        same_site="lax",
        https_only=session_https_only,
    )

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

    app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")
    app.include_router(web_router)
    return app


app = create_app()
