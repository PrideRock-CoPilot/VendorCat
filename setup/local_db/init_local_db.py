from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable


REQUIRED_SCHEMA: dict[str, tuple[str, ...]] = {
    "core_vendor": ("vendor_id", "display_name", "lifecycle_state", "owner_org_id"),
    "sec_user_role_map": ("user_principal", "role_code", "active_flag"),
    "app_user_settings": ("user_principal", "setting_key", "setting_value_json"),
    "app_user_directory": (
        "user_id",
        "login_identifier",
        "display_name",
        "first_name",
        "last_name",
    ),
    "app_lookup_option": (
        "option_id",
        "lookup_type",
        "option_code",
        "option_label",
        "sort_order",
        "active_flag",
        "valid_from_ts",
        "valid_to_ts",
        "is_current",
        "deleted_flag",
    ),
    "core_vendor_offering": ("offering_id", "vendor_id", "lob", "service_type"),
    "app_offering_profile": (
        "offering_id",
        "vendor_id",
        "estimated_monthly_cost",
        "implementation_notes",
        "data_sent",
        "data_received",
        "integration_method",
        "inbound_method",
        "outbound_method",
    ),
    "app_offering_ticket": (
        "ticket_id",
        "offering_id",
        "vendor_id",
        "ticket_system",
        "external_ticket_id",
        "title",
        "status",
    ),
    "app_offering_data_flow": (
        "data_flow_id",
        "offering_id",
        "vendor_id",
        "direction",
        "flow_name",
        "method",
        "data_description",
        "endpoint_details",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize a local SQLite DB with full twvendor schema and seed data.")
    parser.add_argument(
        "--db-path",
        default=str(Path(__file__).resolve().parent / "twvendor_local.db"),
        help="Output SQLite database path.",
    )
    parser.add_argument(
        "--sql-root",
        default=str(Path(__file__).resolve().parent / "sql"),
        help="Root SQL folder path (contains schema/, seed/, queries/).",
    )
    parser.add_argument(
        "--schema-path",
        default="",
        help="Optional single schema SQL file path. Overrides --sql-root/schema/*.sql.",
    )
    parser.add_argument(
        "--seed-path",
        default="",
        help="Optional single seed SQL file path. Overrides --sql-root/seed/*.sql.",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip running seed scripts.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing database file before creating.",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip post-bootstrap schema verification.",
    )
    return parser.parse_args()


def _sql_files_from_dir(directory: Path) -> list[Path]:
    if not directory.exists():
        raise FileNotFoundError(f"SQL directory not found: {directory}")
    files = sorted([item for item in directory.iterdir() if item.is_file() and item.suffix.lower() == ".sql"])
    if not files:
        raise FileNotFoundError(f"No SQL files found in: {directory}")
    return files


def _apply_sql_files(conn: sqlite3.Connection, files: Iterable[Path]) -> int:
    count = 0
    for sql_file in files:
        conn.executescript(sql_file.read_text(encoding="utf-8"))
        count += 1
    return count


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    rows = cursor.fetchall()
    columns = {str(row[1]).strip().lower() for row in rows if len(row) > 1 and str(row[1]).strip()}
    return columns


def verify_required_schema(conn: sqlite3.Connection) -> list[str]:
    errors: list[str] = []
    for table_name, required_columns in REQUIRED_SCHEMA.items():
        present = _table_columns(conn, table_name)
        if not present:
            errors.append(f"missing table: {table_name}")
            continue
        missing = [column for column in required_columns if column.lower() not in present]
        if missing:
            errors.append(f"{table_name} missing columns: {', '.join(missing)}")
    return errors


def count_objects(conn: sqlite3.Connection, object_type: str, count_query_path: Path) -> int:
    if count_query_path.exists():
        statement = count_query_path.read_text(encoding="utf-8")
    else:
        statement = """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = ?
          AND name NOT LIKE 'sqlite_%'
        """
    cursor = conn.execute(statement, (object_type,))
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def main() -> None:
    args = parse_args()
    db_path = Path(args.db_path).resolve()
    sql_root = Path(args.sql_root).resolve()
    count_query_path = sql_root / "queries" / "count_objects.sql"

    schema_files: list[Path]
    if args.schema_path.strip():
        schema_path = Path(args.schema_path).resolve()
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema SQL not found: {schema_path}")
        schema_files = [schema_path]
    else:
        schema_files = _sql_files_from_dir(sql_root / "schema")

    seed_files: list[Path] = []
    if not args.skip_seed:
        if args.seed_path.strip():
            seed_path = Path(args.seed_path).resolve()
            if not seed_path.exists():
                raise FileNotFoundError(f"Seed SQL not found: {seed_path}")
            seed_files = [seed_path]
        else:
            seed_dir = sql_root / "seed"
            if seed_dir.exists():
                seed_files = _sql_files_from_dir(seed_dir)

    if args.reset and db_path.exists():
        db_path.unlink()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        schema_script_count = _apply_sql_files(conn, schema_files)
        seed_script_count = _apply_sql_files(conn, seed_files) if seed_files else 0
        conn.commit()
        if not args.skip_verify:
            schema_errors = verify_required_schema(conn)
            if schema_errors:
                details = "; ".join(schema_errors)
                raise RuntimeError(
                    "Local schema validation failed. "
                    "The database is out of date for current app requirements. "
                    "Run with --reset to rebuild the database. "
                    f"Details: {details}"
                )
        table_count = count_objects(conn, "table", count_query_path)
        view_count = count_objects(conn, "view", count_query_path)

    print(f"Local database ready: {db_path}")
    print(f"Schema scripts applied: {schema_script_count}")
    print(f"Seed scripts applied: {seed_script_count}")
    print(f"Tables: {table_count}")
    print(f"Views: {view_count}")


if __name__ == "__main__":
    main()
