from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


SCHEMA_SQL_FILES: tuple[str, ...] = (
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

CREATE_TABLE_RE = re.compile(
    r"(?is)\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`\"\w\.\${}]+)"
)
CREATE_VIEW_RE = re.compile(
    r"(?is)\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?([`\"\w\.\${}]+)"
)
TABLE_REF_RE = re.compile(r"_table\(\s*['\"]([a-zA-Z0-9_]+)['\"]\s*\)")


@dataclass(frozen=True)
class BundleSpec:
    key: str
    path: Path
    enforce_schema_file_order: bool


@dataclass
class BundleInventory:
    tables: set[str]
    views: set[str]
    file_objects: dict[str, set[str]]

    @property
    def all_objects(self) -> set[str]:
        return set(self.tables) | set(self.views)


def _normalize_object_name(raw: str) -> str:
    token = str(raw or "").strip().replace("`", "").replace('"', "")
    if "." in token:
        token = token.split(".")[-1]
    return token.strip().lower()


def _resolve_repo_root() -> Path:
    # setup/v1_schema/validate_sql_object_coverage.py -> repo root
    return Path(__file__).resolve().parents[2]


def _runtime_object_references(app_root: Path) -> set[str]:
    objects: set[str] = set()
    py_files = list(app_root.rglob("*.py"))
    for file_path in py_files:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for item in TABLE_REF_RE.findall(text):
            cleaned = _normalize_object_name(item)
            if cleaned:
                objects.add(cleaned)
        if "_employee_directory_view(" in text:
            objects.add("vw_employee_directory")
    return objects


def _collect_bundle_inventory(bundle_path: Path) -> BundleInventory:
    tables: set[str] = set()
    views: set[str] = set()
    file_objects: dict[str, set[str]] = {}

    for file_path in sorted(bundle_path.glob("*.sql")):
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        file_set: set[str] = set()
        for token in CREATE_TABLE_RE.findall(text):
            obj = _normalize_object_name(token)
            if obj:
                tables.add(obj)
                file_set.add(obj)
        for token in CREATE_VIEW_RE.findall(text):
            obj = _normalize_object_name(token)
            if obj:
                views.add(obj)
                file_set.add(obj)
        file_objects[file_path.name] = file_set

    return BundleInventory(tables=tables, views=views, file_objects=file_objects)


def _missing_schema_files(bundle_path: Path) -> list[str]:
    missing: list[str] = []
    for file_name in SCHEMA_SQL_FILES:
        if not (bundle_path / file_name).is_file():
            missing.append(file_name)
    return missing


def _print_bundle_summary(
    *,
    spec: BundleSpec,
    inv: BundleInventory,
    runtime_refs: set[str],
) -> tuple[list[str], list[str]]:
    missing_refs = sorted(runtime_refs - inv.all_objects)
    extra_defs = sorted(inv.all_objects - runtime_refs)

    print(f"\n[{spec.key}]")
    print(f"path={spec.path}")
    print(f"tables={len(inv.tables)} views={len(inv.views)} total={len(inv.all_objects)}")
    print(f"runtime_refs_missing={len(missing_refs)}")
    if missing_refs:
        print("  " + ", ".join(missing_refs))
    print(f"extra_definitions={len(extra_defs)}")

    non_empty_files = sum(1 for objects in inv.file_objects.values() if objects)
    print(f"sql_files={len(inv.file_objects)} files_with_create_objects={non_empty_files}")
    return missing_refs, extra_defs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate that app runtime SQL object references are covered by schema SQL bundles "
            "(v1 databricks/local + production push)."
        )
    )
    parser.add_argument(
        "--no-fail-on-error",
        action="store_true",
        help="Always exit 0 and only print validation findings.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = _resolve_repo_root()
    app_root = repo_root / "app" / "vendor_catalog_app"

    bundles = (
        BundleSpec(
            key="v1_databricks",
            path=repo_root / "setup" / "v1_schema" / "databricks",
            enforce_schema_file_order=True,
        ),
        BundleSpec(
            key="v1_local_db",
            path=repo_root / "setup" / "v1_schema" / "local_db",
            enforce_schema_file_order=True,
        ),
        BundleSpec(
            key="production_push",
            path=repo_root / "setup" / "production_push" / "sql",
            enforce_schema_file_order=True,
        ),
    )

    runtime_refs = _runtime_object_references(app_root)
    print(f"runtime_references={len(runtime_refs)}")
    print(", ".join(sorted(runtime_refs)))

    has_errors = False
    inventories: dict[str, BundleInventory] = {}

    for spec in bundles:
        if not spec.path.is_dir():
            print(f"\n[{spec.key}] ERROR: bundle path not found: {spec.path}")
            has_errors = True
            continue

        if spec.enforce_schema_file_order:
            missing_files = _missing_schema_files(spec.path)
            if missing_files:
                print(f"\n[{spec.key}] ERROR: missing required schema files")
                print("  " + ", ".join(missing_files))
                has_errors = True

        inv = _collect_bundle_inventory(spec.path)
        inventories[spec.key] = inv
        missing_refs, _extra_defs = _print_bundle_summary(
            spec=spec,
            inv=inv,
            runtime_refs=runtime_refs,
        )
        if missing_refs:
            has_errors = True

    # Strong parity gate for Databricks bundles used in deployment.
    if "v1_databricks" in inventories and "production_push" in inventories:
        v1 = inventories["v1_databricks"].all_objects
        prod = inventories["production_push"].all_objects
        missing_in_prod = sorted(v1 - prod)
        missing_in_v1 = sorted(prod - v1)
        print("\n[parity:v1_databricks<->production_push]")
        print(f"missing_in_production_push={len(missing_in_prod)}")
        if missing_in_prod:
            print("  " + ", ".join(missing_in_prod))
        print(f"missing_in_v1_databricks={len(missing_in_v1)}")
        if missing_in_v1:
            print("  " + ", ".join(missing_in_v1))
        if missing_in_prod or missing_in_v1:
            has_errors = True

    if has_errors:
        print("\nRESULT=FAIL")
        return 0 if args.no_fail_on_error else 1

    print("\nRESULT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
