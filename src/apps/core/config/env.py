from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeSettings:
    env: str
    runtime_profile: str
    debug: bool
    secret_key: str
    allowed_hosts: tuple[str, ...]
    local_duckdb_path: str
    databricks_host: str
    databricks_http_path: str
    databricks_token: str
    databricks_client_id: str
    databricks_client_secret: str


TRUE_VALUES = {"1", "true", "yes", "y", "on"}


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default)).strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name, "1" if default else "0").lower()
    return raw in TRUE_VALUES


def get_runtime_settings() -> RuntimeSettings:
    env = _env("VC_ENV", "dev")
    profile = _env("VC_RUNTIME_PROFILE", "local").lower()
    if profile not in {"local", "databricks"}:
        profile = "local"

    hosts = tuple(host.strip() for host in _env("VC_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip())

    return RuntimeSettings(
        env=env,
        runtime_profile=profile,
        debug=_env_bool("VC_DEBUG", env != "prod"),
        secret_key=_env("VC_SECRET_KEY", "dev-not-secure-change-me"),
        allowed_hosts=hosts,
        local_duckdb_path=_env("VC_LOCAL_DUCKDB_PATH", "src/.local/vendorcatalog.duckdb"),
        databricks_host=_env("DATABRICKS_SERVER_HOSTNAME", ""),
        databricks_http_path=_env("DATABRICKS_HTTP_PATH", ""),
        databricks_token=_env("DATABRICKS_TOKEN", ""),
        databricks_client_id=_env("DATABRICKS_CLIENT_ID", ""),
        databricks_client_secret=_env("DATABRICKS_CLIENT_SECRET", ""),
    )


def validate_runtime_settings(settings: RuntimeSettings) -> list[str]:
    issues: list[str] = []
    if settings.env == "prod" and (
        not settings.secret_key or settings.secret_key == "dev-not-secure-change-me"
    ):
        issues.append("VC_SECRET_KEY must be set to a non-default value in prod")

    if settings.runtime_profile == "databricks":
        if not settings.databricks_host:
            issues.append("DATABRICKS_SERVER_HOSTNAME is required for databricks profile")
        if not settings.databricks_http_path:
            issues.append("DATABRICKS_HTTP_PATH is required for databricks profile")
        if not settings.databricks_token:
            issues.append("DATABRICKS_TOKEN is required for databricks profile")

    return issues
