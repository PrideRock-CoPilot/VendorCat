from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

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


def test_databricks_validate_rejects_missing_auth() -> None:
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
