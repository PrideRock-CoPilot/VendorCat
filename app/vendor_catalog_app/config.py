from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEV_ENV_NAMES = {"dev", "development", "local"}


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _clean_host(raw_host: str) -> str:
    value = str(raw_host or "").strip()
    if not value:
        return ""
    value = value.replace("https://", "").replace("http://", "").rstrip("/")
    return value


def _resolve_http_path() -> str:
    direct_keys = (
        "DATABRICKS_HTTP_PATH",
        "DATABRICKS_SQL_HTTP_PATH",
        "DBSQL_HTTP_PATH",
        "SQL_HTTP_PATH",
    )
    for key in direct_keys:
        value = os.getenv(key, "").strip()
        if value:
            return value

    warehouse_id_keys = (
        "DATABRICKS_WAREHOUSE_ID",
        "DATABRICKS_SQL_WAREHOUSE_ID",
        "SQL_WAREHOUSE_ID",
        "DBSQL_WAREHOUSE_ID",
    )
    for key in warehouse_id_keys:
        warehouse_id = os.getenv(key, "").strip()
        if warehouse_id:
            return f"/sql/1.0/warehouses/{warehouse_id}"

    # Databricks Apps resources may expose custom keys (for example sql-warehouse/sql_warehouse).
    resource_key_candidates = (
        "sql-warehouse",
        "sql_warehouse",
        "SQL_WAREHOUSE",
        "SQL-WAREHOUSE",
    )
    for key in resource_key_candidates:
        raw = os.getenv(key, "").strip()
        if not raw:
            continue
        if raw.startswith("/sql/"):
            return raw
        return f"/sql/1.0/warehouses/{raw}"
    return ""


def _repo_root() -> Path:
    # app/vendor_catalog_app/config.py -> repo root is two levels up from app/
    return Path(__file__).resolve().parents[2]


def _resolve_repo_relative_path(raw_path: str) -> str:
    value = str(raw_path or "").strip()
    if not value:
        return value
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((_repo_root() / path).resolve())


def _resolve_catalog_schema(env_name: str) -> tuple[str, str]:
    fq_schema = os.getenv("TVENDOR_FQ_SCHEMA", "").strip()
    if fq_schema:
        parts = [item.strip() for item in fq_schema.split(".", 1)]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise RuntimeError(
                "TVENDOR_FQ_SCHEMA must be in '<catalog>.<schema>' format."
            )
        return parts[0], parts[1]

    default_catalog = "vendor_dev" if env_name in DEV_ENV_NAMES else ""
    default_schema = "twvendor" if env_name in DEV_ENV_NAMES else ""
    catalog = os.getenv("TVENDOR_CATALOG", default_catalog).strip()
    schema = os.getenv("TVENDOR_SCHEMA", default_schema).strip()

    if not catalog or not schema:
        raise RuntimeError(
            "TVENDOR_CATALOG and TVENDOR_SCHEMA are required outside local/dev mode "
            "(or set TVENDOR_FQ_SCHEMA)."
        )
    return catalog, schema


def _resolve_allowed_write_verbs() -> tuple[str, ...]:
    raw = os.getenv("TVENDOR_ALLOWED_WRITE_VERBS", "INSERT,UPDATE")
    values = [
        token.strip().upper()
        for token in raw.split(",")
        if token.strip()
    ]
    if not values:
        values = ["INSERT", "UPDATE"]
    return tuple(dict.fromkeys(values))


@dataclass(frozen=True)
class AppConfig:
    databricks_server_hostname: str
    databricks_http_path: str
    databricks_token: str
    databricks_client_id: str = ""
    databricks_client_secret: str = ""
    env: str = "dev"
    catalog: str = "vendor_dev"
    schema: str = "twvendor"
    use_local_db: bool = False
    local_db_path: str = "setup/local_db/twvendor_local.db"
    locked_mode: bool = False
    enforce_prod_sql_policy: bool = True
    allowed_write_verbs: tuple[str, ...] = ("INSERT", "UPDATE")
    schema_bootstrap_sql_path: str = "setup/databricks/001_create_databricks_schema.sql"

    @property
    def fq_schema(self) -> str:
        return f"{self.catalog}.{self.schema}"

    @property
    def is_dev_env(self) -> bool:
        return self.env in DEV_ENV_NAMES

    @staticmethod
    def from_env() -> "AppConfig":
        env_name = os.getenv("TVENDOR_ENV", "dev").strip().lower() or "dev"
        catalog, schema = _resolve_catalog_schema(env_name)
        default_local_db = env_name in DEV_ENV_NAMES
        requested_local_db = _as_bool(os.getenv("TVENDOR_USE_LOCAL_DB"), default=default_local_db)
        raw_host = (
            os.getenv("DATABRICKS_SERVER_HOSTNAME", "")
            or os.getenv("DATABRICKS_HOST", "")
            or os.getenv("DBSQL_SERVER_HOSTNAME", "")
        )
        if requested_local_db and env_name not in DEV_ENV_NAMES:
            raise RuntimeError(
                "TVENDOR_USE_LOCAL_DB=true is allowed only for dev/local environments. "
                "Set TVENDOR_ENV=dev (or local), or disable TVENDOR_USE_LOCAL_DB."
            )
        return AppConfig(
            databricks_server_hostname=_clean_host(raw_host),
            databricks_http_path=_resolve_http_path(),
            databricks_token=os.getenv("DATABRICKS_TOKEN", ""),
            databricks_client_id=os.getenv("DATABRICKS_CLIENT_ID", ""),
            databricks_client_secret=os.getenv("DATABRICKS_CLIENT_SECRET", ""),
            env=env_name,
            catalog=catalog,
            schema=schema,
            use_local_db=requested_local_db,
            local_db_path=_resolve_repo_relative_path(
                os.getenv("TVENDOR_LOCAL_DB_PATH", "setup/local_db/twvendor_local.db")
            ),
            locked_mode=_as_bool(os.getenv("TVENDOR_LOCKED_MODE"), default=False),
            enforce_prod_sql_policy=_as_bool(
                os.getenv("TVENDOR_ENFORCE_PROD_SQL_POLICY"),
                default=True,
            ),
            allowed_write_verbs=_resolve_allowed_write_verbs(),
            schema_bootstrap_sql_path=os.getenv(
                "TVENDOR_SCHEMA_BOOTSTRAP_SQL",
                "setup/databricks/001_create_databricks_schema.sql",
            ),
        )
