from __future__ import annotations

import sys
from pathlib import Path

from apps.core.schema.validator import validate_schema_contract


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    canonical_root = repo_root / "src" / "schema" / "canonical"
    rendered_roots = {
        "duckdb": repo_root / "src" / "schema" / "rendered" / "duckdb",
        "databricks": repo_root / "src" / "schema" / "rendered" / "databricks",
    }

    result = validate_schema_contract(canonical_root, rendered_roots)

    print(f"Canonical objects: {len(result.canonical_objects)}")
    for engine, objects in result.rendered_objects.items():
        print(f"Rendered objects ({engine}): {len(objects)}")

    if result.issues:
        print("Schema validation failed:")
        for issue in result.issues:
            print(f"- {issue}")
        return 1

    print("Schema validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
