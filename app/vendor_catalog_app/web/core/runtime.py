from __future__ import annotations

from contextlib import suppress
from contextvars import ContextVar, Token
from dataclasses import replace
from functools import lru_cache
from typing import Any

from vendor_catalog_app.core.config import AppConfig
from vendor_catalog_app.core.env import (
    TVENDOR_ALLOW_TEST_ROLE_OVERRIDE,
    TVENDOR_TRUST_FORWARDED_IDENTITY_HEADERS,
    get_env_bool,
)
from vendor_catalog_app.repository import VendorRepository

_REQUEST_RUNTIME_OVERRIDE: ContextVar[dict[str, str] | None] = ContextVar(
    "tvendor_request_runtime_override",
    default=None,
)
_REQUEST_OVERRIDE_REPO: ContextVar[VendorRepository | None] = ContextVar(
    "tvendor_request_override_repo",
    default=None,
)


def _clean_hostname(raw_value: str) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return ""
    value = value.replace("https://", "").replace("http://", "").rstrip("/")
    return value


@lru_cache(maxsize=1)
def _base_config() -> AppConfig:
    return AppConfig.from_env()


@lru_cache(maxsize=1)
def _base_repo() -> VendorRepository:
    return VendorRepository(_base_config())


def _apply_runtime_override(base: AppConfig, override: dict[str, str]) -> AppConfig:
    values = dict(override or {})
    host = str(values.get("databricks_server_hostname", "") or "").strip()
    http_path = str(values.get("databricks_http_path", "") or "").strip()
    warehouse_id = str(values.get("databricks_warehouse_id", "") or "").strip()
    token_override = "databricks_token" in values
    client_id_override = "databricks_client_id" in values
    client_secret_override = "databricks_client_secret" in values

    if not http_path and warehouse_id:
        http_path = f"/sql/1.0/warehouses/{warehouse_id}"

    return replace(
        base,
        databricks_server_hostname=(_clean_hostname(host) if host else base.databricks_server_hostname),
        databricks_http_path=(http_path if http_path else base.databricks_http_path),
        databricks_token=(
            str(values.get("databricks_token", "") or "").strip()
            if token_override
            else base.databricks_token
        ),
        databricks_client_id=(
            str(values.get("databricks_client_id", "") or "").strip()
            if client_id_override
            else base.databricks_client_id
        ),
        databricks_client_secret=(
            str(values.get("databricks_client_secret", "") or "").strip()
            if client_secret_override
            else base.databricks_client_secret
        ),
    )


def activate_request_runtime_override(override: dict[str, Any] | None) -> tuple[Token, Token]:
    normalized = {
        str(key): str(value or "").strip()
        for key, value in dict(override or {}).items()
        if str(key).strip()
    }
    override_token = _REQUEST_RUNTIME_OVERRIDE.set(normalized or None)
    repo_token = _REQUEST_OVERRIDE_REPO.set(None)
    return override_token, repo_token


def deactivate_request_runtime_override(tokens: tuple[Token, Token]) -> None:
    repo = _REQUEST_OVERRIDE_REPO.get()
    if repo is not None:
        with suppress(Exception):
            repo.client.close()
    _REQUEST_OVERRIDE_REPO.reset(tokens[1])
    _REQUEST_RUNTIME_OVERRIDE.reset(tokens[0])


def get_config() -> AppConfig:
    override = _REQUEST_RUNTIME_OVERRIDE.get()
    base = _base_config()
    if not override:
        return base
    return _apply_runtime_override(base, override)


def _clear_base_config_cache() -> None:
    _base_config.cache_clear()


def get_repo() -> VendorRepository:
    override = _REQUEST_RUNTIME_OVERRIDE.get()
    if not override:
        return _base_repo()
    cached_repo = _REQUEST_OVERRIDE_REPO.get()
    if cached_repo is not None:
        return cached_repo
    repo = VendorRepository(get_config())
    _REQUEST_OVERRIDE_REPO.set(repo)
    return repo


def _clear_base_repo_cache() -> None:
    with suppress(Exception):
        repo = _base_repo()
        repo.client.close()
    _base_repo.cache_clear()


get_config.cache_clear = _clear_base_config_cache  # type: ignore[attr-defined]
get_repo.cache_clear = _clear_base_repo_cache  # type: ignore[attr-defined]


def trust_forwarded_identity_headers(config: AppConfig) -> bool:
    is_dev_env = bool(getattr(config, "is_dev_env", False))
    return get_env_bool(
        TVENDOR_TRUST_FORWARDED_IDENTITY_HEADERS,
        default=is_dev_env,
    )


def testing_role_override_enabled(config: AppConfig) -> bool:
    is_dev_env = bool(getattr(config, "is_dev_env", False))
    return get_env_bool(
        TVENDOR_ALLOW_TEST_ROLE_OVERRIDE,
        default=is_dev_env,
    )
