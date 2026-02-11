from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import vendor_catalog_app.db as db_module
from vendor_catalog_app.config import AppConfig
from vendor_catalog_app.db import DatabricksSQLClient


def test_databricks_validate_accepts_pat() -> None:
    config = AppConfig(
        databricks_server_hostname="example.cloud.databricks.com",
        databricks_http_path="/sql/1.0/warehouses/abc",
        databricks_token="dapiXXX",
        use_local_db=False,
    )
    client = DatabricksSQLClient(config)
    client._validate()


def test_databricks_validate_accepts_oauth_service_principal_credentials() -> None:
    config = AppConfig(
        databricks_server_hostname="example.cloud.databricks.com",
        databricks_http_path="/sql/1.0/warehouses/abc",
        databricks_token="",
        databricks_client_id="client-id",
        databricks_client_secret="client-secret",
        use_local_db=False,
    )
    client = DatabricksSQLClient(config)
    client._validate()


def test_databricks_validate_rejects_missing_auth_without_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_module, "DatabricksSDKConfig", None)
    config = AppConfig(
        databricks_server_hostname="example.cloud.databricks.com",
        databricks_http_path="/sql/1.0/warehouses/abc",
        databricks_token="",
        databricks_client_id="",
        databricks_client_secret="",
        use_local_db=False,
    )
    client = DatabricksSQLClient(config)
    with pytest.raises(RuntimeError):
        client._validate()


def test_databricks_connect_supports_runtime_oauth_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeConfig:
        def __init__(self, host: str) -> None:
            self.host = host

        def authenticate(self) -> dict[str, str]:
            return {"Authorization": "Bearer runtime-token"}

    def _fake_connect(**kwargs):
        return kwargs

    monkeypatch.setattr(db_module, "DatabricksSDKConfig", _FakeConfig)
    monkeypatch.setattr(db_module.dbsql, "connect", _fake_connect)

    config = AppConfig(
        databricks_server_hostname="example.cloud.databricks.com",
        databricks_http_path="/sql/1.0/warehouses/abc",
        databricks_token="",
        databricks_client_id="",
        databricks_client_secret="",
        use_local_db=False,
    )
    client = DatabricksSQLClient(config)
    result = client._connect_databricks()

    assert "credentials_provider" in result
    provider = result["credentials_provider"]
    header_factory = provider()
    assert callable(header_factory)
    assert header_factory()["Authorization"] == "Bearer runtime-token"


def test_prod_sql_policy_blocks_ddl_and_delete() -> None:
    config = AppConfig(
        databricks_server_hostname="example.cloud.databricks.com",
        databricks_http_path="/sql/1.0/warehouses/abc",
        databricks_token="dapiXXX",
        env="prod",
        use_local_db=False,
        enforce_prod_sql_policy=True,
        allowed_write_verbs=("INSERT", "UPDATE"),
    )
    client = DatabricksSQLClient(config)

    with pytest.raises(RuntimeError):
        client._enforce_prod_sql_policy("CREATE TABLE t (id INT)", is_query=False)
    with pytest.raises(RuntimeError):
        client._enforce_prod_sql_policy("DELETE FROM t WHERE id = 1", is_query=False)


def test_prod_sql_policy_allows_insert_update_and_select() -> None:
    config = AppConfig(
        databricks_server_hostname="example.cloud.databricks.com",
        databricks_http_path="/sql/1.0/warehouses/abc",
        databricks_token="dapiXXX",
        env="prod",
        use_local_db=False,
        enforce_prod_sql_policy=True,
        allowed_write_verbs=("INSERT", "UPDATE"),
    )
    client = DatabricksSQLClient(config)

    client._enforce_prod_sql_policy("INSERT INTO t VALUES (1)", is_query=False)
    client._enforce_prod_sql_policy("UPDATE t SET id = 2 WHERE id = 1", is_query=False)
    client._enforce_prod_sql_policy("SELECT 1", is_query=True)
