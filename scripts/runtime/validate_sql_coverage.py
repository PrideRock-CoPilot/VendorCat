from __future__ import annotations

from pathlib import Path

from apps.core.schema.validator import validate_schema_contract

MINIMUM_CANONICAL_OBJECTS = 12


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    canonical_root = repo_root / "src" / "schema" / "canonical"
    rendered_roots = {
        "duckdb": repo_root / "src" / "schema" / "rendered" / "duckdb",
        "databricks": repo_root / "src" / "schema" / "rendered" / "databricks",
    }

    result = validate_schema_contract(canonical_root, rendered_roots)

    if len(result.canonical_objects) < MINIMUM_CANONICAL_OBJECTS:
        print(
            f"SQL coverage validation failed: expected at least {MINIMUM_CANONICAL_OBJECTS} canonical objects, "
            f"found {len(result.canonical_objects)}"
        )
        return 1

    if result.issues:
        print("SQL coverage validation failed:")
        for issue in result.issues:
            print(f"- {issue}")
        return 1

    print(
        "SQL coverage validation passed: "
        f"canonical={len(result.canonical_objects)} "
        f"duckdb={len(result.rendered_objects.get('duckdb', ()))} "
        f"databricks={len(result.rendered_objects.get('databricks', ()))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
