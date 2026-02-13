from __future__ import annotations

from dataclasses import dataclass
import hmac

from fastapi import Request

from vendor_catalog_app.config import AppConfig
from vendor_catalog_app.defaults import DEFAULT_CSP_POLICY, DEFAULT_SESSION_SECRET
from vendor_catalog_app.env import (
    TVENDOR_ALLOW_DEFAULT_SESSION_SECRET,
    TVENDOR_CSP_ENABLED,
    TVENDOR_CSP_POLICY,
    TVENDOR_CSRF_ENABLED,
    TVENDOR_DATABRICKS_REPORTS_ALLOWED_HOSTS,
    TVENDOR_DATABRICKS_REPORTS_ALLOW_EMBED,
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
from vendor_catalog_app.web.security.controls import SlidingWindowRateLimiter


@dataclass(frozen=True)
class AppRuntimeSettings:
    session_secret: str
    session_https_only: bool
    security_headers_enabled: bool
    metrics_allow_unauthenticated: bool
    metrics_auth_token: str
    csrf_enabled: bool
    csp_enabled: bool
    csp_policy: str
    perf_enabled: bool
    perf_header_enabled: bool
    request_id_header_enabled: bool
    sql_preload_on_startup: bool
    slow_query_ms: float
    write_rate_limit_window_sec: int
    write_rate_limit_max_requests: int
    write_rate_limiter: SlidingWindowRateLimiter


def normalize_host_value(raw_host: str) -> str:
    host = str(raw_host or "").strip().lower()
    if not host:
        return ""
    host = host.replace("https://", "").replace("http://", "").strip("/")
    if "/" in host:
        host = host.split("/", 1)[0].strip()
    if ":" in host:
        host = host.split(":", 1)[0].strip()
    return host


def build_csp_policy(base_policy: str, *, databricks_host: str) -> str:
    policy = str(base_policy or "").strip()
    if not policy:
        return policy
    if "frame-src" in policy.lower():
        return policy

    host_values: list[str] = []
    if databricks_host:
        host_values.append(databricks_host)
    for token in get_env(TVENDOR_DATABRICKS_REPORTS_ALLOWED_HOSTS, "").split(","):
        cleaned = normalize_host_value(token)
        if cleaned:
            host_values.append(cleaned)
    deduped = list(dict.fromkeys(host_values))
    if not deduped:
        return policy

    frame_sources = " ".join(f"https://{host}" for host in deduped)
    return f"{policy}; frame-src 'self' {frame_sources}"


def request_matches_token(request: Request, *, token: str, header_name: str) -> bool:
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


def load_app_runtime_settings(config: AppConfig) -> AppRuntimeSettings:
    session_secret = get_env(TVENDOR_SESSION_SECRET, DEFAULT_SESSION_SECRET)
    allow_default_session_secret = get_env_bool(TVENDOR_ALLOW_DEFAULT_SESSION_SECRET, default=False)
    if (
        not config.is_dev_env
        and session_secret == DEFAULT_SESSION_SECRET
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
        build_csp_policy(
            raw_csp_policy,
            databricks_host=normalize_host_value(config.databricks_server_hostname),
        )
        if allow_databricks_embed
        else raw_csp_policy
    )

    perf_enabled = get_env_bool(TVENDOR_PERF_LOG_ENABLED, default=False)
    perf_header_enabled = get_env_bool(TVENDOR_PERF_RESPONSE_HEADER, default=True)
    request_id_header_enabled = get_env_bool(TVENDOR_REQUEST_ID_HEADER_ENABLED, default=True)
    sql_preload_on_startup = get_env_bool(TVENDOR_SQL_PRELOAD_ON_STARTUP, default=False)
    slow_query_ms = max(1.0, get_env_float(TVENDOR_SLOW_QUERY_MS, default=750.0, min_value=1.0))

    write_rate_limiter = SlidingWindowRateLimiter(
        enabled=write_rate_limit_enabled,
        max_requests=write_rate_limit_max_requests,
        window_seconds=write_rate_limit_window_sec,
    )

    return AppRuntimeSettings(
        session_secret=session_secret,
        session_https_only=session_https_only,
        security_headers_enabled=security_headers_enabled,
        metrics_allow_unauthenticated=metrics_allow_unauthenticated,
        metrics_auth_token=metrics_auth_token,
        csrf_enabled=csrf_enabled,
        csp_enabled=csp_enabled,
        csp_policy=csp_policy,
        perf_enabled=perf_enabled,
        perf_header_enabled=perf_header_enabled,
        request_id_header_enabled=request_id_header_enabled,
        sql_preload_on_startup=sql_preload_on_startup,
        slow_query_ms=slow_query_ms,
        write_rate_limit_window_sec=write_rate_limit_window_sec,
        write_rate_limit_max_requests=write_rate_limit_max_requests,
        write_rate_limiter=write_rate_limiter,
    )
