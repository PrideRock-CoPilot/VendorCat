from __future__ import annotations

import hmac
import time
import uuid
from typing import Any

from fastapi import Request

from vendor_catalog_app.core.env import (
    TVENDOR_CONNECTION_LAB_AUTH_TTL_SEC,
    TVENDOR_CONNECTION_LAB_OVERRIDE_TTL_SEC,
    TVENDOR_CONNECTION_LAB_TOKEN,
    get_env,
    get_env_int,
)
from vendor_catalog_app.infrastructure.cache import LruTtlCache

CONNECTION_LAB_AUTH_EXPIRES_AT_SESSION_KEY = "tvendor_connection_lab_auth_expires_at"
CONNECTION_LAB_OVERRIDE_ID_SESSION_KEY = "tvendor_connection_lab_override_id"

_OVERRIDE_CACHE = LruTtlCache[str, dict[str, str]](
    enabled=True,
    ttl_seconds=3600,
    max_entries=64,
    clone_value=lambda value: dict(value),
)


def _connection_lab_auth_ttl_sec() -> int:
    return max(60, get_env_int(TVENDOR_CONNECTION_LAB_AUTH_TTL_SEC, default=1800, min_value=60))


def _connection_lab_override_ttl_sec() -> int:
    return max(60, get_env_int(TVENDOR_CONNECTION_LAB_OVERRIDE_TTL_SEC, default=3600, min_value=60))


def _session_dict(request: Request) -> dict[str, Any] | None:
    session = request.scope.get("session")
    if not isinstance(session, dict):
        return None
    return session


def connection_lab_token() -> str:
    return get_env(TVENDOR_CONNECTION_LAB_TOKEN, "")


def connection_lab_enabled(config) -> bool:
    if bool(getattr(config, "is_dev_env", False)):
        return True
    return bool(connection_lab_token())


def connection_lab_authorized(request: Request, config) -> bool:
    if bool(getattr(config, "is_dev_env", False)):
        return True
    session = _session_dict(request)
    if session is None:
        return False
    expires_at = int(str(session.get(CONNECTION_LAB_AUTH_EXPIRES_AT_SESSION_KEY, "0")).strip() or "0")
    return expires_at > int(time.time())


def authorize_connection_lab(request: Request, provided_token: str) -> bool:
    expected = connection_lab_token()
    if not expected:
        return False
    candidate = str(provided_token or "").strip()
    if not candidate:
        return False
    if not hmac.compare_digest(candidate, expected):
        return False
    session = _session_dict(request)
    if session is None:
        return False
    session[CONNECTION_LAB_AUTH_EXPIRES_AT_SESSION_KEY] = int(time.time()) + _connection_lab_auth_ttl_sec()
    return True


def clear_connection_lab_auth(request: Request) -> None:
    session = _session_dict(request)
    if session is None:
        return
    session.pop(CONNECTION_LAB_AUTH_EXPIRES_AT_SESSION_KEY, None)


def _build_http_path(http_path: str, warehouse_id: str) -> str:
    path = str(http_path or "").strip()
    if path:
        return path
    warehouse = str(warehouse_id or "").strip()
    if not warehouse:
        return ""
    return f"/sql/1.0/warehouses/{warehouse}"


def build_override_from_form(form: dict[str, Any]) -> dict[str, str]:
    override: dict[str, str] = {}

    host = str(form.get("databricks_server_hostname", "") or "").strip()
    http_path = str(form.get("databricks_http_path", "") or "").strip()
    warehouse_id = str(form.get("databricks_warehouse_id", "") or "").strip()
    auth_mode = str(form.get("auth_mode", "inherit") or "inherit").strip().lower()
    if auth_mode not in {"inherit", "pat", "oauth_client"}:
        auth_mode = "inherit"

    if host:
        override["databricks_server_hostname"] = host
    if http_path:
        override["databricks_http_path"] = http_path
    elif warehouse_id:
        override["databricks_warehouse_id"] = warehouse_id
        built_path = _build_http_path("", warehouse_id)
        if built_path:
            override["databricks_http_path"] = built_path

    if auth_mode == "pat":
        override["databricks_token"] = str(form.get("databricks_token", "") or "").strip()
        override["databricks_client_id"] = ""
        override["databricks_client_secret"] = ""
    elif auth_mode == "oauth_client":
        override["databricks_token"] = ""
        override["databricks_client_id"] = str(form.get("databricks_client_id", "") or "").strip()
        override["databricks_client_secret"] = str(form.get("databricks_client_secret", "") or "").strip()

    return override


def override_preview(override: dict[str, str] | None) -> dict[str, str]:
    value = dict(override or {})
    if not value:
        return {}
    preview: dict[str, str] = {}
    host = str(value.get("databricks_server_hostname", "") or "").strip()
    if host:
        preview["databricks_server_hostname"] = host
    path = str(value.get("databricks_http_path", "") or "").strip()
    if path:
        preview["databricks_http_path"] = path
    if "databricks_token" in value:
        preview["auth_mode"] = "pat" if str(value.get("databricks_token", "")).strip() else "inherit"
    if "databricks_client_id" in value or "databricks_client_secret" in value:
        has_client = bool(str(value.get("databricks_client_id", "") or "").strip())
        has_secret = bool(str(value.get("databricks_client_secret", "") or "").strip())
        if has_client or has_secret:
            preview["auth_mode"] = "oauth_client"
        elif preview.get("auth_mode") != "pat":
            preview["auth_mode"] = "inherit"
    return preview


def save_runtime_override_for_session(request: Request, override: dict[str, str]) -> bool:
    session = _session_dict(request)
    if session is None:
        return False
    normalized = dict(override or {})
    if not normalized:
        return False
    override_id = uuid.uuid4().hex
    _OVERRIDE_CACHE.set(
        override_id,
        normalized,
        ttl_seconds=_connection_lab_override_ttl_sec(),
    )
    session[CONNECTION_LAB_OVERRIDE_ID_SESSION_KEY] = override_id
    return True


def clear_runtime_override_for_session(request: Request) -> None:
    session = _session_dict(request)
    if session is None:
        return
    session.pop(CONNECTION_LAB_OVERRIDE_ID_SESSION_KEY, None)


def load_runtime_override_from_session(session: dict[str, Any] | None) -> dict[str, str] | None:
    if not isinstance(session, dict):
        return None
    override_id = str(session.get(CONNECTION_LAB_OVERRIDE_ID_SESSION_KEY, "") or "").strip()
    if not override_id:
        return None
    override = _OVERRIDE_CACHE.get(override_id)
    if override is None:
        session.pop(CONNECTION_LAB_OVERRIDE_ID_SESSION_KEY, None)
        return None
    return dict(override)

