from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class AppConfig:
    databricks_server_hostname: str
    databricks_http_path: str
    databricks_token: str
    catalog: str = "vendor_dev"
    schema: str = "twvendor"
    use_mock: bool = True
    use_local_db: bool = False
    local_db_path: str = "setup/local_db/twvendor_local.db"
    locked_mode: bool = False
    schema_bootstrap_sql_path: str = "setup/databricks/001_create_databricks_schema.sql"

    @property
    def fq_schema(self) -> str:
        return f"{self.catalog}.{self.schema}"

    @staticmethod
    def from_env() -> "AppConfig":
        return AppConfig(
            databricks_server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME", "").replace(
                "https://", ""
            ),
            databricks_http_path=os.getenv("DATABRICKS_HTTP_PATH", ""),
            databricks_token=os.getenv("DATABRICKS_TOKEN", ""),
            catalog=os.getenv("TVENDOR_CATALOG", "vendor_dev"),
            schema=os.getenv("TVENDOR_SCHEMA", "twvendor"),
            use_mock=_as_bool(os.getenv("TVENDOR_USE_MOCK"), default=True),
            use_local_db=_as_bool(os.getenv("TVENDOR_USE_LOCAL_DB"), default=False),
            local_db_path=os.getenv("TVENDOR_LOCAL_DB_PATH", "setup/local_db/twvendor_local.db"),
            locked_mode=_as_bool(os.getenv("TVENDOR_LOCKED_MODE"), default=False),
            schema_bootstrap_sql_path=os.getenv(
                "TVENDOR_SCHEMA_BOOTSTRAP_SQL",
                "setup/databricks/001_create_databricks_schema.sql",
            ),
        )
