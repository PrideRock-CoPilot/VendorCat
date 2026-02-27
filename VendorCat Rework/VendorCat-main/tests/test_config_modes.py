from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.core.config import AppConfig


def _clear_mode_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "TVENDOR_ENV",
        "TVENDOR_USE_LOCAL_DB",
        "TVENDOR_DEV_ALLOW_ALL_ACCESS",
        "DATABRICKS_HTTP_PATH",
        "DATABRICKS_SQL_HTTP_PATH",
        "DBSQL_HTTP_PATH",
        "SQL_HTTP_PATH",
        "DATABRICKS_WAREHOUSE_ID",
        "DATABRICKS_SQL_WAREHOUSE_ID",
        "DBSQL_WAREHOUSE_ID",
        "SQL_WAREHOUSE_ID",
        "DATABRICKS_HOST",
        "DATABRICKS_SERVER_HOSTNAME",
        "DBSQL_SERVER_HOSTNAME",
        "sql-warehouse",
        "sql_warehouse",
        "SQL_WAREHOUSE",
        "SQL-WAREHOUSE",
    ):
        monkeypatch.delenv(key, raising=False)


def test_dev_defaults_to_local_db(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TVENDOR_ENV", "dev")

    config = AppConfig.from_env()

    assert config.env == "dev"
    assert config.is_dev_env is True
    assert config.use_local_db is True


def test_prod_defaults_to_databricks_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TVENDOR_ENV", "prod")
    monkeypatch.setenv("TVENDOR_CATALOG", "a1_dlk")
    monkeypatch.setenv("TVENDOR_SCHEMA", "twanalytics")

    config = AppConfig.from_env()

    assert config.env == "prod"
    assert config.is_dev_env is False
    assert config.use_local_db is False


def test_prod_rejects_local_db_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TVENDOR_ENV", "prod")
    monkeypatch.setenv("TVENDOR_CATALOG", "a1_dlk")
    monkeypatch.setenv("TVENDOR_SCHEMA", "twanalytics")
    monkeypatch.setenv("TVENDOR_USE_LOCAL_DB", "true")

    with pytest.raises(RuntimeError):
        AppConfig.from_env()


def test_http_path_can_be_derived_from_warehouse_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TVENDOR_ENV", "prod")
    monkeypatch.setenv("TVENDOR_CATALOG", "a1_dlk")
    monkeypatch.setenv("TVENDOR_SCHEMA", "twanalytics")
    monkeypatch.setenv("DATABRICKS_WAREHOUSE_ID", "abc123")

    config = AppConfig.from_env()

    assert config.databricks_http_path == "/sql/1.0/warehouses/abc123"


def test_host_normalization_supports_databricks_host(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TVENDOR_ENV", "prod")
    monkeypatch.setenv("TVENDOR_CATALOG", "a1_dlk")
    monkeypatch.setenv("TVENDOR_SCHEMA", "twanalytics")
    monkeypatch.setenv("DATABRICKS_HOST", "https://dbc-12345.cloud.databricks.com/")

    config = AppConfig.from_env()

    assert config.databricks_server_hostname == "dbc-12345.cloud.databricks.com"


def test_host_normalization_supports_dbsql_server_hostname(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TVENDOR_ENV", "prod")
    monkeypatch.setenv("TVENDOR_CATALOG", "a1_dlk")
    monkeypatch.setenv("TVENDOR_SCHEMA", "twanalytics")
    monkeypatch.setenv("DBSQL_SERVER_HOSTNAME", "https://dbc-67890.cloud.databricks.com/")

    config = AppConfig.from_env()

    assert config.databricks_server_hostname == "dbc-67890.cloud.databricks.com"


def test_http_path_alias_is_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TVENDOR_ENV", "prod")
    monkeypatch.setenv("TVENDOR_CATALOG", "a1_dlk")
    monkeypatch.setenv("TVENDOR_SCHEMA", "twanalytics")
    monkeypatch.setenv("DBSQL_HTTP_PATH", "/sql/1.0/warehouses/alias123")

    config = AppConfig.from_env()

    assert config.databricks_http_path == "/sql/1.0/warehouses/alias123"


def test_http_path_can_be_resolved_from_sql_warehouse_resource_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TVENDOR_ENV", "prod")
    monkeypatch.setenv("TVENDOR_CATALOG", "a1_dlk")
    monkeypatch.setenv("TVENDOR_SCHEMA", "twanalytics")
    monkeypatch.setenv("sql_warehouse", "wh-resource-123")

    config = AppConfig.from_env()

    assert config.databricks_http_path == "/sql/1.0/warehouses/wh-resource-123"


def test_fq_schema_can_drive_catalog_and_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TVENDOR_ENV", "prod")
    monkeypatch.setenv("TVENDOR_FQ_SCHEMA", "a1_dlk.twanalytics")

    config = AppConfig.from_env()

    assert config.catalog == "a1_dlk"
    assert config.schema == "twanalytics"


def test_local_db_path_is_repo_root_relative_not_cwd_relative(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TVENDOR_ENV", "dev")
    monkeypatch.setenv("TVENDOR_LOCAL_DB_PATH", "setup/local_db/twvendor_local.db")
    monkeypatch.chdir(tmp_path)

    config = AppConfig.from_env()

    assert Path(config.local_db_path).is_absolute()
    assert str(config.local_db_path).replace("\\", "/").endswith("setup/local_db/twvendor_local.db")


def test_dev_can_enable_allow_all_access(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TVENDOR_ENV", "dev")
    monkeypatch.setenv("TVENDOR_DEV_ALLOW_ALL_ACCESS", "true")

    config = AppConfig.from_env()

    assert config.dev_allow_all_access is True


def test_prod_ignores_allow_all_access_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mode_env(monkeypatch)
    monkeypatch.setenv("TVENDOR_ENV", "prod")
    monkeypatch.setenv("TVENDOR_CATALOG", "a1_dlk")
    monkeypatch.setenv("TVENDOR_SCHEMA", "twanalytics")
    monkeypatch.setenv("TVENDOR_DEV_ALLOW_ALL_ACCESS", "true")

    config = AppConfig.from_env()

    assert config.dev_allow_all_access is False
