from __future__ import annotations

import argparse
import importlib.util
import re
import sqlite3
from pathlib import Path
from typing import Iterable


TOKEN_PATTERN = re.compile(r"\$\{(CATALOG|SCHEMA)\}")

BASELINE_LOCAL_SEED_FILES: tuple[str, ...] = (
    "001_seed_reference_data.sql",
    "002_seed_help_center.sql",
)

DATABRICKS_SEED_FILES: tuple[str, ...] = (
    "95_seed_reference_data.sql",
    "96_seed_help_center.sql",
)


def _render_tokens(sql_text: str, *, catalog: str, schema: str) -> str:
    context = {"CATALOG": catalog, "SCHEMA": schema}
    return TOKEN_PATTERN.sub(lambda m: context[m.group(1)], sql_text)


def _require_file(path: Path) -> Path:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Required SQL file not found: {path}")
    return path


def _ordered_files(base_dir: Path, names: Iterable[str]) -> list[Path]:
    return [_require_file(base_dir / name) for name in names]


def _run_local_seed_files(*, db_path: Path, seed_files: Iterable[Path]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        for file_path in seed_files:
            conn.executescript(file_path.read_text(encoding="utf-8"))
            print(f"Applied (local): {file_path.name}")
        conn.commit()


def _run_local_full_corporate_seed(*, db_path: Path) -> None:
    local_db_dir = Path(__file__).resolve().parents[1] / "local_db"
    module_path = local_db_dir / "seed_full_corporate.py"
    if not module_path.exists():
        raise FileNotFoundError(f"Corporate seed module not found: {module_path}")

    spec = importlib.util.spec_from_file_location("seed_full_corporate", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load corporate seed module spec from: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seed_full_corporate_obj = getattr(module, "seed_full_corporate", None)
    if seed_full_corporate_obj is None or not callable(seed_full_corporate_obj):
        raise RuntimeError("seed_full_corporate function not found in corporate seed module")

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        counts = getattr(seed_full_corporate_obj, "__call__")(conn)
        conn.commit()
    print(
        "Applied (local): full corporate synthetic seed "
        f"(largest table row count={max(counts.values()) if counts else 0})"
    )


def _write_rendered_bundle(*, seed_files: Iterable[Path], catalog: str, schema: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    chunks: list[str] = [
        f"-- Rendered V1 seed bundle for catalog={catalog}, schema={schema}",
        "",
    ]
    for file_path in seed_files:
        rendered = _render_tokens(file_path.read_text(encoding="utf-8"), catalog=catalog, schema=schema)
        chunks.append(f"-- BEGIN: {file_path.name}")
        chunks.append(rendered.strip())
        chunks.append(f"-- END: {file_path.name}")
        chunks.append("")
    output_path.write_text("\n".join(chunks), encoding="utf-8")


def _run_databricks_seed(
    *,
    seed_files: Iterable[Path],
    catalog: str,
    schema: str,
    server_hostname: str,
    http_path: str,
    token: str,
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

    connection = sql.connect(server_hostname=hostname, http_path=http_path, access_token=token)
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"USE CATALOG `{catalog}`")
            cursor.execute(f"USE SCHEMA `{schema}`")
            for file_path in seed_files:
                rendered = _render_tokens(file_path.read_text(encoding="utf-8"), catalog=catalog, schema=schema)
                statements = [stmt.strip() for stmt in rendered.split(";") if stmt.strip()]
                for statement in statements:
                    cursor.execute(statement)
                print(f"Applied (databricks): {file_path.name}")
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run V1 seed scripts for local DB or Databricks.")
    parser.add_argument("--target", required=True, choices=("local", "databricks"), help="Execution target.")
    parser.add_argument(
        "--base-dir",
        default=str(Path(__file__).resolve().parent),
        help="Base V1 schema directory.",
    )
    parser.add_argument(
        "--seed-profile",
        default="baseline",
        choices=("baseline", "full"),
        help="Seed profile. 'full' currently applies only to local target.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute on target. Databricks defaults to render-only unless set.",
    )
    parser.add_argument(
        "--rendered-output",
        default="",
        help="Optional rendered SQL bundle output path for databricks target.",
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
        db_path = Path(args.db_path).resolve()
        seed_dir = base_dir.parents[0] / "local_db" / "sql" / "seed"
        baseline_files = _ordered_files(seed_dir, BASELINE_LOCAL_SEED_FILES)
        _run_local_seed_files(db_path=db_path, seed_files=baseline_files)
        if args.seed_profile == "full":
            _run_local_full_corporate_seed(db_path=db_path)
        print("Local V1 seed complete.")
        raise SystemExit(0)

    databricks_seed_dir = base_dir / "databricks"
    seed_files = _ordered_files(databricks_seed_dir, DATABRICKS_SEED_FILES)

    rendered_output = (
        Path(args.rendered_output).resolve()
        if args.rendered_output
        else Path(__file__).resolve().parents[1] / "databricks" / "rendered" / "v1_seed_bundle.sql"
    )
    _write_rendered_bundle(seed_files=seed_files, catalog=args.catalog, schema=args.schema, output_path=rendered_output)
    print(f"Rendered Databricks seed bundle: {rendered_output}")

    if args.execute:
        _run_databricks_seed(
            seed_files=seed_files,
            catalog=args.catalog,
            schema=args.schema,
            server_hostname=args.databricks_server_hostname,
            http_path=args.databricks_http_path,
            token=args.databricks_token,
        )
        print("Databricks V1 seed execution complete.")
    else:
        print("Databricks execution skipped (--execute not set).")
