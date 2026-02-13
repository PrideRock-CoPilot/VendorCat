from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.core.config import AppConfig
from vendor_catalog_app.repository import SchemaBootstrapRequiredError, VendorRepository


def _create_legacy_lookup_table(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_lookup_option (
              option_id TEXT PRIMARY KEY,
              lookup_type TEXT NOT NULL,
              option_code TEXT NOT NULL,
              option_label TEXT NOT NULL,
              sort_order INTEGER NOT NULL DEFAULT 100,
              active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
              updated_at TEXT NOT NULL,
              updated_by TEXT NOT NULL
            );
            """
        )
        conn.commit()

def _create_lookup_table_with_scd(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_lookup_option (
              option_id TEXT PRIMARY KEY,
              lookup_type TEXT NOT NULL,
              option_code TEXT NOT NULL,
              option_label TEXT NOT NULL,
              sort_order INTEGER NOT NULL DEFAULT 100,
              active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
              valid_from_ts TEXT NOT NULL,
              valid_to_ts TEXT,
              is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
              deleted_flag INTEGER NOT NULL DEFAULT 0 CHECK (deleted_flag IN (0, 1)),
              updated_at TEXT NOT NULL,
              updated_by TEXT NOT NULL
            );
            """
        )
        conn.commit()


def test_lookup_options_use_scd_history_with_validity_dates(tmp_path: Path) -> None:
    db_path = tmp_path / "lookup.db"
    _create_lookup_table_with_scd(db_path)
    repo = VendorRepository(
        AppConfig(
            databricks_server_hostname="",
            databricks_http_path="",
            databricks_token="",
            use_local_db=True,
            local_db_path=str(db_path),
        )
    )

    repo.save_lookup_option(
        option_id=None,
        lookup_type="doc_tag",
        option_code="contract",
        option_label="Contract",
        sort_order=1,
        valid_from_ts="2026-01-01",
        valid_to_ts="9999-12-31",
        updated_by="tester@example.com",
    )
    repo.save_lookup_option(
        option_id=None,
        lookup_type="doc_tag",
        option_code="contract",
        option_label="Contract Updated",
        sort_order=1,
        valid_from_ts="2026-01-01",
        valid_to_ts="9999-12-31",
        updated_by="tester@example.com",
    )

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT option_label, is_current, valid_from_ts, valid_to_ts
            FROM app_lookup_option
            WHERE lookup_type = 'doc_tag' AND option_code = 'contract'
            ORDER BY valid_from_ts
            """
        ).fetchall()

    assert len(rows) >= 2
    current_rows = [row for row in rows if int(row[1] or 0) == 1]
    historical_rows = [row for row in rows if int(row[1] or 0) == 0]
    assert len(current_rows) == 1
    assert len(historical_rows) >= 1
    assert current_rows[0][0] == "Contract Updated"
    assert str(current_rows[0][3]).startswith("9999-12-31")
    assert all(str(row[3] or "").strip() != "" for row in historical_rows)

    active_visible = repo.list_lookup_options("doc_tag", active_only=True)
    contract_rows = active_visible[active_visible["option_code"].astype(str) == "contract"]
    assert len(contract_rows) >= 1
    assert "Contract Updated" in contract_rows["option_label"].astype(str).tolist()


def test_lookup_option_legacy_schema_requires_bootstrap(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_lookup.db"
    _create_legacy_lookup_table(db_path)
    repo = VendorRepository(
        AppConfig(
            databricks_server_hostname="",
            databricks_http_path="",
            databricks_token="",
            use_local_db=True,
            local_db_path=str(db_path),
        )
    )

    with pytest.raises(SchemaBootstrapRequiredError):
        repo.list_lookup_options("doc_tag", active_only=False)
