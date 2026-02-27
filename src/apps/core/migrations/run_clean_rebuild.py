from __future__ import annotations

from pathlib import Path

from apps.core.config.env import get_runtime_settings
from apps.core.schema.validator import split_sql_statements
from apps.core.sql.adapter import DuckDbAdapter


def run_clean_rebuild() -> None:
    settings = get_runtime_settings()
    if settings.runtime_profile != "local":
        raise RuntimeError("Clean rebuild runner currently supports local DuckDB profile only.")

    db_path = Path(settings.local_duckdb_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    adapter = DuckDbAdapter(str(db_path))
    rendered_root = Path("src/schema/rendered/duckdb")
    sql_files = sorted(rendered_root.glob("*.sql"))
    if not sql_files:
        raise RuntimeError(f"No rendered SQL files found at {rendered_root}")

    for sql_file in sql_files:
        statement_bundle = sql_file.read_text(encoding="utf-8")
        for statement in split_sql_statements(statement_bundle):
            adapter.execute(statement)


if __name__ == "__main__":
    run_clean_rebuild()
