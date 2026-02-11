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


class _FakeCursor:
    def __init__(self, owner):
        self._owner = owner
        self.description = [("value",)]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params):
        self._owner.executions.append((statement, params))

    def fetchall(self):
        return [(1,)]

    def close(self):
        return None


class _FakeConn:
    def __init__(self, owner):
        self._owner = owner

    def cursor(self):
        return _FakeCursor(self._owner)

    def close(self):
        return None


def _databricks_config() -> AppConfig:
    return AppConfig(
        databricks_server_hostname="example.cloud.databricks.com",
        databricks_http_path="/sql/1.0/warehouses/abc",
        databricks_token="dapiXXX",
        use_local_db=False,
    )


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


def test_databricks_connect_wraps_service_principal_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeConfig:
        def __init__(self, host: str, client_id: str, client_secret: str) -> None:
            self.host = host
            self.client_id = client_id
            self.client_secret = client_secret

    def _fake_oauth_service_principal(_cfg):
        # SDK-style provider that directly returns headers.
        def _headers():
            return {"Authorization": "Bearer sp-token"}

        return _headers

    def _fake_connect(**kwargs):
        return kwargs

    monkeypatch.setattr(db_module, "DatabricksSDKConfig", _FakeConfig)
    monkeypatch.setattr(db_module, "oauth_service_principal", _fake_oauth_service_principal)
    monkeypatch.setattr(db_module.dbsql, "connect", _fake_connect)

    config = AppConfig(
        databricks_server_hostname="example.cloud.databricks.com",
        databricks_http_path="/sql/1.0/warehouses/abc",
        databricks_token="",
        databricks_client_id="client-id",
        databricks_client_secret="client-secret",
        use_local_db=False,
    )
    client = DatabricksSQLClient(config)
    result = client._connect_databricks()

    assert "credentials_provider" in result
    provider = result["credentials_provider"]
    header_factory = provider()
    assert callable(header_factory)
    assert header_factory()["Authorization"] == "Bearer sp-token"


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


def test_prepare_strips_bom_and_normalizes_percent_s_for_databricks() -> None:
    client = DatabricksSQLClient(_databricks_config())
    prepared = client._prepare("\ufeffSELECT * FROM table WHERE id = %s")
    assert prepared == "SELECT * FROM table WHERE id = ?"


def test_databricks_reuses_connection_between_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = type("Owner", (), {"executions": []})()
    connects = {"count": 0}

    def _fake_connect_databricks():
        connects["count"] += 1
        return _FakeConn(owner)

    monkeypatch.setenv("TVENDOR_QUERY_CACHE_ENABLED", "false")
    client = DatabricksSQLClient(_databricks_config())
    monkeypatch.setattr(client, "_connect_databricks", _fake_connect_databricks)

    client.query("SELECT 1")
    client.query("SELECT 2")

    assert connects["count"] == 1
    assert len(owner.executions) == 2


def test_databricks_query_cache_hit_and_execute_invalidation(monkeypatch: pytest.MonkeyPatch) -> None:
    owner = type("Owner", (), {"executions": []})()
    connects = {"count": 0}

    def _fake_connect_databricks():
        connects["count"] += 1
        return _FakeConn(owner)

    monkeypatch.setenv("TVENDOR_QUERY_CACHE_ENABLED", "true")
    monkeypatch.setenv("TVENDOR_QUERY_CACHE_TTL_SEC", "300")
    client = DatabricksSQLClient(_databricks_config())
    monkeypatch.setattr(client, "_connect_databricks", _fake_connect_databricks)

    client.query("SELECT 1 WHERE id = %s", params=(123,))
    client.query("SELECT 1 WHERE id = %s", params=(123,))
    assert len(owner.executions) == 1

    client.execute("UPDATE t SET id = %s WHERE id = %s", params=(1, 2))
    client.query("SELECT 1 WHERE id = %s", params=(123,))

    assert connects["count"] == 1
    assert len(owner.executions) == 3
