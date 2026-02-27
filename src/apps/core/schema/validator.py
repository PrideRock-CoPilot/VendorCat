from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CREATE_OBJECT_PATTERN = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?([`\"\[]?[A-Za-z0-9_\.]+[`\"\]]?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SchemaValidationResult:
    canonical_objects: tuple[str, ...]
    rendered_objects: dict[str, tuple[str, ...]]
    issues: tuple[str, ...]


def _strip_identifier_quotes(identifier: str) -> str:
    value = identifier.strip().strip("`").strip('"').strip("[").strip("]")
    return value


def _normalize_identifier(identifier: str) -> str:
    value = _strip_identifier_quotes(identifier)
    if "." in value:
        value = value.split(".")[-1]
    return value.lower()


def extract_object_names(sql_text: str) -> set[str]:
    names: set[str] = set()
    for match in CREATE_OBJECT_PATTERN.finditer(sql_text):
        names.add(_normalize_identifier(match.group(1)))
    return names


def collect_sql_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.sql"))


def collect_schema_objects(root: Path) -> set[str]:
    objects: set[str] = set()
    for file_path in collect_sql_files(root):
        text = file_path.read_text(encoding="utf-8")
        objects.update(extract_object_names(text))
    return objects


def validate_schema_contract(canonical_root: Path, rendered_roots: dict[str, Path]) -> SchemaValidationResult:
    canonical = collect_schema_objects(canonical_root)
    issues: list[str] = []

    if not canonical:
        issues.append("No canonical SQL objects were discovered")

    for object_name in sorted(canonical):
        if not object_name.startswith("vc_"):
            issues.append(f"Canonical object does not use vc_ prefix: {object_name}")

    rendered: dict[str, tuple[str, ...]] = {}
    for engine, root in rendered_roots.items():
        objects = collect_schema_objects(root)
        rendered[engine] = tuple(sorted(objects))
        missing = sorted(canonical.difference(objects))
        if missing:
            issues.append(f"Rendered schema missing canonical objects for {engine}: {', '.join(missing)}")

    return SchemaValidationResult(
        canonical_objects=tuple(sorted(canonical)),
        rendered_objects=rendered,
        issues=tuple(issues),
    )


def split_sql_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    chunks = sql_text.split(";")
    for chunk in chunks:
        statement = chunk.strip()
        if statement:
            statements.append(f"{statement};")
    return statements
