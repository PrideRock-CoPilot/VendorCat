from __future__ import annotations

from pathlib import Path

import pytest

from apps.core.schema.validator import split_sql_statements, validate_schema_contract


@pytest.mark.parametrize(
    "sql_text, expected_count",
    [
        ("SELECT 1;", 1),
        ("SELECT 1;\nSELECT 2;", 2),
        ("\n\n", 0),
    ],
)
def test_split_sql_statements(sql_text: str, expected_count: int) -> None:
    assert len(split_sql_statements(sql_text)) == expected_count


def test_schema_contract_validation_passes() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    canonical_root = repo_root / "src" / "schema" / "canonical"
    rendered_roots = {
        "duckdb": repo_root / "src" / "schema" / "rendered" / "duckdb",
        "databricks": repo_root / "src" / "schema" / "rendered" / "databricks",
    }

    result = validate_schema_contract(canonical_root, rendered_roots)
    assert result.canonical_objects
    assert not result.issues
