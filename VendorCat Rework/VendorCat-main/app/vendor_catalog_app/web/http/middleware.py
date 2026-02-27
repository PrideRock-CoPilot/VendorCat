from __future__ import annotations

import json
import logging
import time
import uuid
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

from vendor_catalog_app.infrastructure.db import (
    clear_request_perf_context,
    get_request_perf_context,
    start_request_perf_context,
)
from vendor_catalog_app.web.http.errors import api_error_response, is_api_request, normalize_exception
from vendor_catalog_app.web.security.controls import (
    CSRF_HEADER,
    ensure_csrf_token,
    request_matches_csrf_token,
    request_rate_limit_key,
    request_requires_write_protection,
)
from vendor_catalog_app.web.system.settings import AppRuntimeSettings

LOGGER = logging.getLogger(__name__)
PERF_LOGGER = logging.getLogger("vendor_catalog_app.perf")
PROTECTED_UI_PATH_PREFIXES = (
    "/dashboard",
    "/vendor-360",
    "/vendors",
    "/projects",
    "/contracts",
    "/demos",
    "/imports",
    "/reports",
    "/admin",
    "/workflows",
    "/pending-approvals",
)


def _route_path_label(request: Request) -> str:
    route = request.scope.get("route")
    route_path = str(getattr(route, "path", "") or "").strip()
    if route_path:
        return route_path
    return str(request.url.path or "/")


def _is_protected_ui_path(path: str) -> bool:
    cleaned = str(path or "").strip() or "/"
    if cleaned in {"/", "/access/request"}:
        return False
    return any(cleaned.startswith(prefix) for prefix in PROTECTED_UI_PATH_PREFIXES)


def _request_target_path(request: Request) -> str:
    path = str(request.url.path or "/")
    query = str(request.url.query or "").strip()
    if query:
        return f"{path}?{query}"
    return path


def _payload_contains_legacy_lob_key(payload: object) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = str(key or "").strip().lower().replace("-", "_").replace(" ", "_")
            if normalized == "lob":
                return True
            if _payload_contains_legacy_lob_key(value):
                return True
        return False
    if isinstance(payload, list):
        return any(_payload_contains_legacy_lob_key(item) for item in payload)
    return False


def register_security_headers_middleware(app: FastAPI, settings: AppRuntimeSettings) -> None:
    if not settings.security_headers_enabled:
        return

    @app.middleware("http")
    async def _security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if settings.csp_enabled and settings.csp_policy:
            response.headers.setdefault("Content-Security-Policy", settings.csp_policy)
        if settings.session_https_only:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


def register_request_perf_middleware(app: FastAPI, settings: AppRuntimeSettings, observability) -> None:
    @app.middleware("http")
    async def _request_perf_middleware(request: Request, call_next):
        request_id = uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        token = start_request_perf_context(
            request_id=request_id,
            method=request.method,
            path=str(request.url.path),
            slow_query_ms=settings.slow_query_ms,
        )
        started = time.perf_counter()
        response = None
        status_code = 500
        runtime_override_tokens = None
        try:
            session = request.scope.get("session")
            if isinstance(session, dict):
                from vendor_catalog_app.web.system.connection_lab import load_runtime_override_from_session

                runtime_override = load_runtime_override_from_session(session)
                if runtime_override:
                    from vendor_catalog_app.web.core.runtime import activate_request_runtime_override

                    runtime_override_tokens = activate_request_runtime_override(runtime_override)
                    request.state.runtime_override_active = True

            path = str(request.url.path or "/")
            if _is_protected_ui_path(path):
                from vendor_catalog_app.web.core.user_context_service import get_user_context

                user = get_user_context(request)
                user_roles = set(getattr(user, "roles", set()) or set())
                # Let dashboard route execute its own access/bootstrap handling.
                if not user_roles and not path.startswith("/dashboard"):
                    response = RedirectResponse(url="/access/request", status_code=303)
                    status_code = response.status_code
                    return response
                if user_roles and request.method.upper() in {"GET", "HEAD"}:
                    from vendor_catalog_app.web.core.runtime import get_repo
                    from vendor_catalog_app.web.core.terms import (
                        has_current_terms_acceptance,
                        terms_enforcement_enabled,
                    )

                    if terms_enforcement_enabled() and not has_current_terms_acceptance(
                        request=request,
                        repo=get_repo(),
                        user_principal=user.user_principal,
                    ):
                        next_path = _request_target_path(request)
                        redirect_url = f"/access/terms?next={quote(next_path, safe='/%?=&')}"
                        response = RedirectResponse(url=redirect_url, status_code=303)
                        status_code = response.status_code
                        return response

            if request_requires_write_protection(request.method):
                content_type = str(request.headers.get("content-type", "")).lower()
                if "application/json" in content_type:
                    try:
                        body_bytes = await request.body()
                    except Exception:
                        body_bytes = b""
                    if body_bytes:
                        try:
                            payload = json.loads(body_bytes.decode("utf-8"))
                        except Exception:
                            payload = None
                        if _payload_contains_legacy_lob_key(payload):
                            message = (
                                "Payload field 'lob' is no longer supported. "
                                "Use 'business_unit' instead."
                            )
                            if is_api_request(request):
                                response = api_error_response(
                                    request,
                                    status_code=422,
                                    code="VALIDATION_ERROR",
                                    message=message,
                                )
                            else:
                                response = PlainTextResponse(message, status_code=422)
                            status_code = response.status_code
                            return response

            csrf_token = ensure_csrf_token(request)
            request.state.csrf_token = csrf_token
            if (
                settings.csrf_enabled
                and request_requires_write_protection(request.method)
                and not await request_matches_csrf_token(
                    request,
                    expected_token=csrf_token,
                    header_name=CSRF_HEADER,
                )
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
                allowed, retry_after = settings.write_rate_limiter.allow(limiter_key)
                if not allowed:
                    LOGGER.warning(
                        (
                            "Blocked write request due to rate limit. method=%s path=%s "
                            "window_sec=%s max_requests=%s retry_after=%s"
                        ),
                        request.method,
                        request.url.path,
                        settings.write_rate_limit_window_sec,
                        settings.write_rate_limit_max_requests,
                        retry_after,
                        extra={
                            "event": "write_rate_limit_blocked",
                            "method": request.method,
                            "path": str(request.url.path),
                            "window_sec": int(settings.write_rate_limit_window_sec),
                            "max_requests": int(settings.write_rate_limit_max_requests),
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
                if not is_api_request(request):
                    raise
                response = api_error_response(
                    request,
                    status_code=spec.status_code,
                    code=spec.code,
                    message=spec.message,
                    details=spec.details,
                )
                status_code = response.status_code
                return response

            status_code = response.status_code
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

            if settings.perf_enabled:
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
                if settings.request_id_header_enabled:
                    response.headers["X-Request-ID"] = request_id
                if settings.perf_enabled and settings.perf_header_enabled:
                    response.headers["X-TVendor-Perf"] = (
                        f"total_ms={elapsed_ms:.2f};db_ms={db_total_ms:.2f};db_calls={db_calls};cache_hits={db_cache_hits}"
                    )

            if runtime_override_tokens is not None:
                from vendor_catalog_app.web.core.runtime import deactivate_request_runtime_override

                deactivate_request_runtime_override(runtime_override_tokens)
            clear_request_perf_context(token)
