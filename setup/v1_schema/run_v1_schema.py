from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
import re
import sys
from typing import Iterable


ORDERED_SQL_FILES: tuple[str, ...] = (
    "00_create_v1_schema.sql",
    "01_create_lookup_tables.sql",
    "02_create_core_tables.sql",
    "03_create_assignment_tables.sql",
    "04_create_governance_tables.sql",
    "05_create_functional_parity_bridge.sql",
    "06_create_functional_runtime_compat.sql",
    "07_create_reporting_views.sql",
    "90_create_indexes.sql",
)

TOKEN_PATTERN = re.compile(r"\$\{(CATALOG|SCHEMA)\}")


def _require_file(path: Path) -> Path:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Required SQL file not found: {path}")
    return path


def _ordered_files(base_dir: Path) -> list[Path]:
    return [_require_file(base_dir / name) for name in ORDERED_SQL_FILES]


def _run_sqlite(sql_files: Iterable[Path], db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        for file_path in sql_files:
            sql_text = file_path.read_text(encoding="utf-8")
            conn.executescript(sql_text)
            print(f"Applied (local): {file_path.name}")
        conn.commit()


def _recreate_sqlite_db(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()


def _render_databricks_sql(sql_text: str, catalog: str, schema: str) -> str:
    context = {
        "CATALOG": catalog,
        "SCHEMA": schema,
    }
    return TOKEN_PATTERN.sub(lambda m: context[m.group(1)], sql_text)


def _write_rendered_bundle(sql_files: Iterable[Path], catalog: str, schema: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    chunks: list[str] = [
        f"-- Rendered V1 schema bundle for catalog={catalog}, schema={schema}",
        "",
    ]
    for file_path in sql_files:
        raw_text = file_path.read_text(encoding="utf-8")
        rendered = _render_databricks_sql(raw_text, catalog=catalog, schema=schema)
        chunks.append(f"-- BEGIN: {file_path.name}")
        chunks.append(rendered.strip())
        chunks.append(f"-- END: {file_path.name}")
        chunks.append("")
    output_path.write_text("\n".join(chunks), encoding="utf-8")


def _render_recreate_prefix(*, catalog: str, schema: str) -> str:
    return "\n".join(
        [
            f"DROP SCHEMA IF EXISTS `{catalog}`.`{schema}` CASCADE;",
            f"CREATE CATALOG IF NOT EXISTS `{catalog}`;",
            f"CREATE SCHEMA `{catalog}`.`{schema}`;",
            f"USE CATALOG `{catalog}`;",
            f"USE SCHEMA `{schema}`;",
        ]
    )


def _run_databricks(
    sql_files: Iterable[Path],
    *,
    catalog: str,
    schema: str,
    server_hostname: str,
    http_path: str,
    token: str,
    recreate: bool,
) -> None:
    try:
        from databricks import sql  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Databricks SQL connector is required for --execute. Install databricks-sql-connector."
        ) from exc

    hostname = str(server_hostname or "").strip()
    http_path = str(http_path or "").strip()
    token = str(token or "").strip()

    if not hostname or not http_path or not token:
        raise ValueError(
            "For Databricks execution, provide --databricks-server-hostname, --databricks-http-path, and --databricks-token."
        )

    connection = sql.connect(
        server_hostname=hostname,
        http_path=http_path,
        access_token=token,
    )
    try:
        with connection.cursor() as cursor:
            if recreate:
                recreate_sql = _render_recreate_prefix(catalog=catalog, schema=schema)
                for stmt in [part.strip() for part in recreate_sql.split(";") if part.strip()]:
                    cursor.execute(stmt)
                print(f"Applied (databricks): clean recreate for {catalog}.{schema}")
            for file_path in sql_files:
                rendered = _render_databricks_sql(
                    file_path.read_text(encoding="utf-8"),
                    catalog=catalog,
                    schema=schema,
                )
                statements = [stmt.strip() for stmt in rendered.split(";") if stmt.strip()]
                for stmt in statements:
                    cursor.execute(stmt)
                print(f"Applied (databricks): {file_path.name}")
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run V1 schema scripts for local DB or Databricks.")
    parser.add_argument(
        "--target",
        required=True,
        choices=("local", "databricks"),
        help="Execution target.",
    )

    parser.add_argument(
        "--base-dir",
        default=str(Path(__file__).resolve().parent),
        help="Base V1 schema directory.",
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute scripts on target. If omitted for databricks, only render output SQL bundle.",
    )

    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Destructive clean rebuild. Local: delete DB file first. Databricks: DROP SCHEMA CASCADE then recreate.",
    )

    parser.add_argument(
        "--rendered-output",
        default="",
        help="Optional rendered SQL bundle path for databricks target.",
    )

    parser.add_argument(
        "--db-path",
        default=str(Path(__file__).resolve().parents[1] / "local_db" / "twvendor_local_v1.db"),
        help="SQLite DB path for local target.",
    )

    parser.add_argument("--catalog", default="vendorcat_dev", help="Databricks catalog.")
    parser.add_argument("--schema", default="vendorcat_v1", help="Databricks schema.")

    parser.add_argument("--databricks-server-hostname", default="", help="Databricks server hostname.")
    parser.add_argument("--databricks-http-path", default="", help="Databricks SQL warehouse HTTP path.")
    parser.add_argument("--databricks-token", default="", help="Databricks PAT token.")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    base_dir = Path(args.base_dir).resolve()

    if args.target == "local":
        sql_dir = base_dir / "local_db"
        sql_files = _ordered_files(sql_dir)
        local_db_path = Path(args.db_path).resolve()
        if args.recreate:
            _recreate_sqlite_db(local_db_path)
            print(f"Recreated (local): removed existing DB at {local_db_path}")
        _run_sqlite(sql_files, db_path=local_db_path)
        print("Local V1 schema bootstrap complete.")
        raise SystemExit(0)

    sql_dir = base_dir / "databricks"
    sql_files = _ordered_files(sql_dir)

    rendered_output = Path(args.rendered_output).resolve() if args.rendered_output else (
        Path(__file__).resolve().parents[1] / "databricks" / "rendered" / "v1_schema_bundle.sql"
    )

    _write_rendered_bundle(sql_files, catalog=args.catalog, schema=args.schema, output_path=rendered_output)
    if args.recreate:
        prefix = _render_recreate_prefix(catalog=args.catalog, schema=args.schema)
        existing = rendered_output.read_text(encoding="utf-8")
        rendered_output.write_text(prefix + "\n\n" + existing, encoding="utf-8")
    print(f"Rendered Databricks bundle: {rendered_output}")

    if args.execute:
        _run_databricks(
            sql_files,
            catalog=args.catalog,
            schema=args.schema,
            server_hostname=args.databricks_server_hostname,
            http_path=args.databricks_http_path,
            token=args.databricks_token,
            recreate=args.recreate,
        )
        print("Databricks V1 schema execution complete.")
    else:
        print("Databricks execution skipped (--execute not set).")
