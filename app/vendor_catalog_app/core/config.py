from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vendor_catalog_app.core.defaults import (
    DEFAULT_ALLOWED_WRITE_VERBS,
    DEFAULT_ALLOWED_WRITE_VERBS_CSV,
    DEFAULT_DEV_CATALOG,
    DEFAULT_DEV_ENV_NAMES,
    DEFAULT_DEV_SCHEMA,
    DEFAULT_ENV_NAME,
    DEFAULT_LOCAL_DB_PATH,
    DEFAULT_SCHEMA_BOOTSTRAP_SQL_PATH,
)
from vendor_catalog_app.core.env import (
    DATABRICKS_CLIENT_ID,
    DATABRICKS_CLIENT_SECRET,
    DATABRICKS_HTTP_PATH_KEYS,
    DATABRICKS_RESOURCE_WAREHOUSE_KEYS,
    DATABRICKS_SERVER_HOSTNAME_KEYS,
    DATABRICKS_TOKEN,
    DATABRICKS_WAREHOUSE_ID_KEYS,
    TVENDOR_ALLOWED_WRITE_VERBS,
    TVENDOR_CATALOG,
    TVENDOR_DEV_ALLOW_ALL_ACCESS,
    TVENDOR_ENFORCE_PROD_SQL_POLICY,
    TVENDOR_ENV,
    TVENDOR_FQ_SCHEMA,
    TVENDOR_LOCAL_DB_PATH,
    TVENDOR_LOCKED_MODE,
    TVENDOR_SCHEMA,
    TVENDOR_SCHEMA_BOOTSTRAP_SQL,
    TVENDOR_USE_LOCAL_DB,
    get_env,
    get_env_bool,
    get_first_env,
)


DEV_ENV_NAMES = set(DEFAULT_DEV_ENV_NAMES)


def _clean_host(raw_host: str) -> str:
    value = str(raw_host or "").strip()
    if not value:
        return ""
    value = value.replace("https://", "").replace("http://", "").rstrip("/")
    return value


def _resolve_http_path() -> str:
    direct_path = get_first_env(DATABRICKS_HTTP_PATH_KEYS)
    if direct_path:
        return direct_path

    warehouse_id = get_first_env(DATABRICKS_WAREHOUSE_ID_KEYS)
    if warehouse_id:
        return f"/sql/1.0/warehouses/{warehouse_id}"

    # Databricks Apps resources may expose custom keys (for example sql-warehouse/sql_warehouse).
    resource_value = get_first_env(DATABRICKS_RESOURCE_WAREHOUSE_KEYS)
    if resource_value:
        if resource_value.startswith("/sql/"):
            return resource_value
        return f"/sql/1.0/warehouses/{resource_value}"
    return ""


def _repo_root() -> Path:
    # app/vendor_catalog_app/core/config.py -> repo root
    # parents[0]=core, [1]=vendor_catalog_app, [2]=app, [3]=repo root
    return Path(__file__).resolve().parents[3]


def _resolve_repo_relative_path(raw_path: str) -> str:
    value = str(raw_path or "").strip()
    if not value:
        return value
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((_repo_root() / path).resolve())


def _resolve_catalog_schema(env_name: str) -> tuple[str, str]:
    fq_schema = get_env(TVENDOR_FQ_SCHEMA)
    if fq_schema:
        parts = [item.strip() for item in fq_schema.split(".", 1)]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise RuntimeError(
                "TVENDOR_FQ_SCHEMA must be in '<catalog>.<schema>' format."
            )
        return parts[0], parts[1]

    default_catalog = DEFAULT_DEV_CATALOG if env_name in DEV_ENV_NAMES else ""
    default_schema = DEFAULT_DEV_SCHEMA if env_name in DEV_ENV_NAMES else ""
    catalog = get_env(TVENDOR_CATALOG, default_catalog)
    schema = get_env(TVENDOR_SCHEMA, default_schema)

    if not catalog or not schema:
        raise RuntimeError(
            "TVENDOR_CATALOG and TVENDOR_SCHEMA are required outside local/dev mode "
            "(or set TVENDOR_FQ_SCHEMA)."
        )
    return catalog, schema


def _resolve_allowed_write_verbs() -> tuple[str, ...]:
    raw = get_env(TVENDOR_ALLOWED_WRITE_VERBS, DEFAULT_ALLOWED_WRITE_VERBS_CSV)
    values = [
        token.strip().upper()
        for token in raw.split(",")
        if token.strip()
    ]
    if not values:
        values = list(DEFAULT_ALLOWED_WRITE_VERBS)
    return tuple(dict.fromkeys(values))


@dataclass(frozen=True)
class AppConfig:
    databricks_server_hostname: str
    databricks_http_path: str
    databricks_token: str
    databricks_client_id: str = ""
    databricks_client_secret: str = ""
    env: str = DEFAULT_ENV_NAME
    catalog: str = DEFAULT_DEV_CATALOG
    schema: str = DEFAULT_DEV_SCHEMA
    use_local_db: bool = False
    local_db_path: str = DEFAULT_LOCAL_DB_PATH
    locked_mode: bool = False
    enforce_prod_sql_policy: bool = True
    allowed_write_verbs: tuple[str, ...] = DEFAULT_ALLOWED_WRITE_VERBS
    schema_bootstrap_sql_path: str = DEFAULT_SCHEMA_BOOTSTRAP_SQL_PATH
    dev_allow_all_access: bool = False

    @property
    def fq_schema(self) -> str:
        return f"{self.catalog}.{self.schema}"

    @property
    def is_dev_env(self) -> bool:
        return self.env in DEV_ENV_NAMES

    @staticmethod
    def from_env() -> "AppConfig":
        env_name = get_env(TVENDOR_ENV, DEFAULT_ENV_NAME).lower() or DEFAULT_ENV_NAME
        catalog, schema = _resolve_catalog_schema(env_name)
        default_local_db = env_name in DEV_ENV_NAMES
        requested_local_db = get_env_bool(TVENDOR_USE_LOCAL_DB, default=default_local_db)
        raw_host = get_first_env(DATABRICKS_SERVER_HOSTNAME_KEYS)
        if requested_local_db and env_name not in DEV_ENV_NAMES:
            raise RuntimeError(
                "TVENDOR_USE_LOCAL_DB=true is allowed only for dev/local environments. "
                "Set TVENDOR_ENV=dev (or local), or disable TVENDOR_USE_LOCAL_DB."
            )
        return AppConfig(
            databricks_server_hostname=_clean_host(raw_host),
            databricks_http_path=_resolve_http_path(),
            databricks_token=get_env(DATABRICKS_TOKEN),
            databricks_client_id=get_env(DATABRICKS_CLIENT_ID),
            databricks_client_secret=get_env(DATABRICKS_CLIENT_SECRET),
            env=env_name,
            catalog=catalog,
            schema=schema,
            use_local_db=requested_local_db,
            local_db_path=_resolve_repo_relative_path(
                get_env(TVENDOR_LOCAL_DB_PATH, DEFAULT_LOCAL_DB_PATH)
            ),
            locked_mode=get_env_bool(TVENDOR_LOCKED_MODE, default=False),
            enforce_prod_sql_policy=get_env_bool(
                TVENDOR_ENFORCE_PROD_SQL_POLICY,
                default=True,
            ),
            allowed_write_verbs=_resolve_allowed_write_verbs(),
            schema_bootstrap_sql_path=get_env(
                TVENDOR_SCHEMA_BOOTSTRAP_SQL,
                DEFAULT_SCHEMA_BOOTSTRAP_SQL_PATH,
            ),
            dev_allow_all_access=(
                env_name in DEV_ENV_NAMES
                and get_env_bool(TVENDOR_DEV_ALLOW_ALL_ACCESS, default=False)
            ),
        )
