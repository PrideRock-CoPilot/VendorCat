from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.core.config import AppConfig
from vendor_catalog_app.repository import VendorRepository


def _create_user_directory_table(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_user_directory (
              user_id TEXT PRIMARY KEY,
              login_identifier TEXT NOT NULL UNIQUE,
              email TEXT,
              network_id TEXT,
              first_name TEXT,
              last_name TEXT,
              display_name TEXT NOT NULL,
              active_flag INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              last_seen_at TEXT NOT NULL
            );
            """
        )
        conn.commit()


def test_actor_ref_persists_user_directory_entry_for_local_db(tmp_path: Path) -> None:
    db_path = tmp_path / "users.db"
    _create_user_directory_table(db_path)
    repo = VendorRepository(
        AppConfig(
            databricks_server_hostname="",
            databricks_http_path="",
            databricks_token="",
            use_local_db=True,
            local_db_path=str(db_path),
        )
    )

    first = repo._actor_ref("jane.doe@example.com")
    second = repo._actor_ref("jane.doe@example.com")

    assert first.startswith("usr-")
    assert second == first

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT login_identifier, network_id, display_name, first_name, last_name FROM app_user_directory WHERE user_id = ?",
            (first,),
        ).fetchone()
    assert row is not None
    assert row[0] == "jane.doe@example.com"
    assert row[1] == "jane.doe"
    assert row[2] == "Jane Doe"
    assert row[3] == "Jane"
    assert row[4] == "Doe"


def test_decorate_user_columns_resolves_user_id_to_display_name(tmp_path: Path) -> None:
    db_path = tmp_path / "users.db"
    _create_user_directory_table(db_path)
    repo = VendorRepository(
        AppConfig(
            databricks_server_hostname="",
            databricks_http_path="",
            databricks_token="",
            use_local_db=True,
            local_db_path=str(db_path),
        )
    )
    user_id = repo._actor_ref("john_smith@example.com")

    df = pd.DataFrame([{"actor_user_principal": user_id}, {"actor_user_principal": "alice.jones@example.com"}])
    out = repo._decorate_user_columns(df, ["actor_user_principal"])

    assert out.iloc[0]["actor_user_principal"] == "John Smith"
    assert out.iloc[1]["actor_user_principal"] == "Alice Jones"
