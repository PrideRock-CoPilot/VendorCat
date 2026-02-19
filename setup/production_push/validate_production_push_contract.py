from __future__ import annotations

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


OBJECT_PREFIXES: tuple[str, ...] = (
    "core_",
    "app_",
    "sec_",
    "audit_",
    "hist_",
    "src_",
    "lkp_",
    "vendor_help_",
    "vw_",
    "rpt_",
)

KNOWN_NON_OBJECT_PLACEHOLDERS: set[str] = {
    "limit",
    "offset",
    "group_placeholders",
    "vendor_clause",
    "vendor_ids_placeholders",
    "area_stage_table",
    "employee_directory_view",
    "table_name",
    "where_clause",
    "note_type_clause",
    "offering_ids_placeholders",
    "status_filter_disabled",
    "months_back",
    "org_clause",
    "horizon_days",
    "limit_rows",
    "sort_dir",
    "sort_expr",
    "state_clause",
    "set_clause",
}

CREATE_TABLE_START_RE = re.compile(
    r"(?is)\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`\"\w\.\${}]+)\s*\("
)
CREATE_VIEW_RE = re.compile(
    r"(?is)\bCREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?([`\"\w\.\${}]+)"
)
PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")
TABLE_REF_RE = re.compile(r"_table\(\s*['\"]([a-zA-Z0-9_]+)['\"]\s*\)")
FROM_JOIN_ALIAS_RE = re.compile(
    r"(?is)\b(?:FROM|JOIN)\s+\{([a-zA-Z0-9_]+)\}\s+(?:AS\s+)?([a-zA-Z_][a-zA-Z0-9_]*)"
)
ALIAS_COLUMN_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\b")
SELECT_HEAD_RE = re.compile(r"(?is)\bSELECT\s+(.*?)\bFROM\b")


@dataclass
class TableContract:
    required_columns: set[str]
    files: set[str]


@dataclass
class ValidationResult:
    required_objects: set[str]
    missing_objects: list[str]
    missing_columns: dict[str, list[str]]
    unresolved_placeholders: dict[str, set[str]]
    table_contracts: dict[str, TableContract]
    production_tables: dict[str, set[str]]
    production_views: set[str]
    script_object_counts: dict[str, tuple[int, int]]


def _repo_root() -> Path:
    # setup/production_push/validate_production_push_contract.py -> repo root
    return Path(__file__).resolve().parents[2]


def _normalize_object_name(raw: str) -> str:
    token = str(raw or "").strip().replace("`", "").replace('"', "")
    if "." in token:
        token = token.split(".")[-1]
    return token.strip().lower()


def _split_top_level_commas(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    in_single = False
    idx = 0

    while idx < len(text):
        ch = text[idx]
        nxt = text[idx + 1] if idx + 1 < len(text) else ""

        if ch == "'":
            current.append(ch)
            if in_single and nxt == "'":
                current.append(nxt)
                idx += 1
            else:
                in_single = not in_single
        elif not in_single and ch == "(":
            depth += 1
            current.append(ch)
        elif not in_single and ch == ")":
            depth = max(0, depth - 1)
            current.append(ch)
        elif not in_single and depth == 0 and ch == ",":
            token = "".join(current).strip()
            if token:
                parts.append(token)
            current = []
        else:
            current.append(ch)
        idx += 1

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_create_table_columns(statement_text: str) -> set[str]:
    columns: set[str] = set()
    for part in _split_top_level_commas(statement_text):
        candidate = part.strip()
        if not candidate:
            continue
        upper = candidate.upper()
        if upper.startswith(
            ("CONSTRAINT ", "PRIMARY KEY", "FOREIGN KEY", "UNIQUE ", "CHECK ", "INDEX ")
        ):
            continue
        first = candidate.split()[0].strip('`"')
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", first):
            columns.add(first.lower())
    return columns


def _parse_production_push_inventory(
    production_sql_dir: Path,
) -> tuple[dict[str, set[str]], set[str], dict[str, tuple[int, int]]]:
    tables: dict[str, set[str]] = {}
    views: set[str] = set()
    script_counts: dict[str, tuple[int, int]] = {}

    for file_path in sorted(production_sql_dir.glob("*.sql")):
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        file_table_count = 0
        file_view_count = 0

        for raw_view in CREATE_VIEW_RE.findall(text):
            views.add(_normalize_object_name(raw_view))
            file_view_count += 1

        index = 0
        while True:
            match = CREATE_TABLE_START_RE.search(text, index)
            if not match:
                break
            obj_name = _normalize_object_name(match.group(1))
            open_idx = match.end() - 1
            depth = 0
            in_single = False
            close_idx = -1
            i = open_idx
            while i < len(text):
                ch = text[i]
                nxt = text[i + 1] if i + 1 < len(text) else ""
                if ch == "'":
                    if in_single and nxt == "'":
                        i += 1
                    else:
                        in_single = not in_single
                elif not in_single and ch == "(":
                    depth += 1
                elif not in_single and ch == ")":
                    depth -= 1
                    if depth == 0:
                        close_idx = i
                        break
                i += 1
            if close_idx < 0:
                index = match.end()
                continue
            body = text[open_idx + 1 : close_idx]
            tables.setdefault(obj_name, set()).update(_parse_create_table_columns(body))
            file_table_count += 1
            index = close_idx + 1

        script_counts[file_path.name] = (file_table_count, file_view_count)

    return tables, views, script_counts


def _extract_simple_select_columns(text: str) -> set[str]:
    """Extract unqualified column references from SELECT head for simple one-object SQL files."""
    out: set[str] = set()
    match = SELECT_HEAD_RE.search(text)
    if not match:
        return out
    select_head = match.group(1)
    for expr in _split_top_level_commas(select_head):
        cleaned = str(expr or "").strip()
        if not cleaned:
            continue
        # Drop SELECT aliases and inspect the source expression side only.
        source_expr = re.split(r"(?is)\s+AS\s+", cleaned, maxsplit=1)[0].strip()
        if not source_expr:
            continue
        # Skip literals/constants (for example: SELECT 1 AS present).
        if re.match(r"^[0-9]+(?:\.[0-9]+)?$", source_expr):
            continue
        if source_expr.startswith("'") and source_expr.endswith("'"):
            continue
        # Keep only direct single-column references from simple SELECT heads.
        if "." in source_expr:
            source_expr = source_expr.split(".", 1)[1].strip()
        if "(" in source_expr or ")" in source_expr:
            continue
        token = source_expr.strip('`"')
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", token):
            out.add(token.lower())
    return out


def _collect_app_contract(
    app_sql_root: Path,
    app_py_root: Path,
) -> tuple[set[str], dict[str, TableContract], dict[str, set[str]]]:
    required_objects: set[str] = set()
    contracts: dict[str, TableContract] = {}
    unresolved_placeholders: dict[str, set[str]] = defaultdict(set)

    def _contract_for(obj: str) -> TableContract:
        entry = contracts.get(obj)
        if entry is None:
            entry = TableContract(required_columns=set(), files=set())
            contracts[obj] = entry
        return entry

    for py_file in app_py_root.rglob("*.py"):
        py_text = py_file.read_text(encoding="utf-8", errors="ignore")
        for token in TABLE_REF_RE.findall(py_text):
            name = _normalize_object_name(token)
            if name:
                required_objects.add(name)

        if "_employee_directory_view(" in py_text:
            required_objects.add("vw_employee_directory")

    for sql_file in sorted(app_sql_root.rglob("*.sql")):
        rel = str(sql_file.relative_to(_repo_root()))
        text = sql_file.read_text(encoding="utf-8", errors="ignore")
        placeholders = set(PLACEHOLDER_RE.findall(text))

        file_objects = sorted({p for p in placeholders if p.startswith(OBJECT_PREFIXES)})
        for obj in file_objects:
            required_objects.add(obj.lower())
            _contract_for(obj.lower()).files.add(rel)

        unresolved = sorted(
            token
            for token in placeholders
            if token not in file_objects and token not in KNOWN_NON_OBJECT_PLACEHOLDERS
        )
        if unresolved:
            unresolved_placeholders[rel].update(unresolved)

        alias_map: dict[str, str] = {}
        for object_token, alias in FROM_JOIN_ALIAS_RE.findall(text):
            if object_token.startswith(OBJECT_PREFIXES):
                alias_map[alias.lower()] = object_token.lower()

        for alias, column in ALIAS_COLUMN_RE.findall(text):
            mapped = alias_map.get(alias.lower())
            if mapped:
                _contract_for(mapped).required_columns.add(column.lower())

        for obj in file_objects:
            obj_l = obj.lower()
            insert_re = re.compile(
                rf"(?is)\bINSERT\s+INTO\s+\{{{re.escape(obj)}\}}\s*\((.*?)\)"
            )
            for block in insert_re.findall(text):
                for token in _split_top_level_commas(block):
                    col = token.strip().strip('`"')
                    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", col):
                        _contract_for(obj_l).required_columns.add(col.lower())

            update_re = re.compile(
                rf"(?is)\bUPDATE\s+\{{{re.escape(obj)}\}}(?:\s+(?:AS\s+)?([a-zA-Z_][a-zA-Z0-9_]*))?\s+SET\s+(.*?)(?:\bWHERE\b|$)"
            )
            for alias, set_block in update_re.findall(text):
                for assignment in _split_top_level_commas(set_block):
                    if "=" not in assignment:
                        continue
                    lhs = assignment.split("=", 1)[0].strip()
                    if "." in lhs:
                        lhs_alias, lhs_col = [part.strip().strip('`"') for part in lhs.split(".", 1)]
                        if alias and lhs_alias.lower() != alias.lower():
                            continue
                        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", lhs_col):
                            _contract_for(obj_l).required_columns.add(lhs_col.lower())
                    else:
                        lhs_col = lhs.strip('`"')
                        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", lhs_col):
                            _contract_for(obj_l).required_columns.add(lhs_col.lower())

        # For simple one-object SELECT SQL files, include direct select-column references.
        if len(file_objects) == 1 and "JOIN" not in text.upper():
            obj_l = file_objects[0].lower()
            for col in _extract_simple_select_columns(text):
                _contract_for(obj_l).required_columns.add(col.lower())

    return required_objects, contracts, unresolved_placeholders


def validate_contract() -> ValidationResult:
    repo_root = _repo_root()
    app_root = repo_root / "app" / "vendor_catalog_app"
    app_sql_root = app_root / "sql"
    production_sql_root = repo_root / "setup" / "production_push" / "sql"

    production_tables, production_views, script_counts = _parse_production_push_inventory(
        production_sql_root
    )
    required_objects, contracts, unresolved_placeholders = _collect_app_contract(
        app_sql_root,
        app_root,
    )

    production_objects = set(production_tables) | set(production_views)
    missing_objects = sorted(required_objects - production_objects)

    missing_columns: dict[str, list[str]] = {}
    for obj_name, contract in sorted(contracts.items()):
        if obj_name not in production_tables:
            continue
        missing = sorted(contract.required_columns - production_tables[obj_name])
        if missing:
            missing_columns[obj_name] = missing

    return ValidationResult(
        required_objects=required_objects,
        missing_objects=missing_objects,
        missing_columns=missing_columns,
        unresolved_placeholders=unresolved_placeholders,
        table_contracts=contracts,
        production_tables=production_tables,
        production_views=production_views,
        script_object_counts=script_counts,
    )


def _render_report(result: ValidationResult) -> str:
    lines: list[str] = []
    lines.append("# Production Push Contract Validation")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Required app objects: {len(result.required_objects)}")
    lines.append(
        f"- Production push objects: {len(result.production_tables) + len(result.production_views)} "
        f"(tables={len(result.production_tables)}, views={len(result.production_views)})"
    )
    lines.append(f"- Missing objects: {len(result.missing_objects)}")
    lines.append(f"- Objects with missing required columns: {len(result.missing_columns)}")
    lines.append(
        f"- SQL files with unresolved placeholders: {len(result.unresolved_placeholders)}"
    )
    lines.append("")

    if result.missing_objects:
        lines.append("## Missing Objects")
        for name in result.missing_objects:
            lines.append(f"- `{name}`")
        lines.append("")

    if result.missing_columns:
        lines.append("## Missing Columns")
        for obj, cols in sorted(result.missing_columns.items()):
            lines.append(f"- `{obj}`: {', '.join(f'`{c}`' for c in cols)}")
        lines.append("")

    if result.unresolved_placeholders:
        lines.append("## Unresolved Placeholders")
        lines.append(
            "- These placeholders are not object tokens and not in the approved dynamic placeholder allow-list."
        )
        for file_name, placeholders in sorted(result.unresolved_placeholders.items()):
            lines.append(f"- `{file_name}`: {', '.join(f'`{p}`' for p in sorted(placeholders))}")
        lines.append("")

    lines.append("## Script Object Creation Matrix (production push)")
    for script_name, (table_count, view_count) in sorted(result.script_object_counts.items()):
        lines.append(
            f"- `{script_name}`: tables={table_count}, views={view_count}, total={table_count + view_count}"
        )
    lines.append("")

    lines.append("## Required Objects and Column Contract")
    for obj in sorted(result.required_objects):
        kind = "table" if obj in result.production_tables else ("view" if obj in result.production_views else "missing")
        contract = result.table_contracts.get(obj, TableContract(required_columns=set(), files=set()))
        req_cols = sorted(contract.required_columns)
        lines.append(
            f"- `{obj}` [{kind}] required_cols={len(req_cols)} defined_cols="
            f"{len(result.production_tables.get(obj, set())) if kind == 'table' else 'n/a'}"
        )
        if req_cols:
            lines.append(f"  - required: {', '.join(f'`{c}`' for c in req_cols)}")
        if kind == "table":
            defined_cols = sorted(result.production_tables.get(obj, set()))
            lines.append(f"  - defined: {', '.join(f'`{c}`' for c in defined_cols)}")
        if contract.files:
            lines.append(f"  - files: {', '.join(f'`{f}`' for f in sorted(contract.files))}")
    lines.append("")

    status = "PASS" if not result.missing_objects and not result.missing_columns else "FAIL"
    lines.append(f"## Result: {status}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate that production push SQL creates all app-required tables/views "
            "and required columns referenced by app SQL."
        )
    )
    parser.add_argument(
        "--report-path",
        default="setup/production_push/production_push_contract_report.md",
        help="Path to write markdown report.",
    )
    parser.add_argument(
        "--no-fail-on-error",
        action="store_true",
        help="Always exit 0 and only print findings.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = validate_contract()
    report = _render_report(result)
    report_path = _repo_root() / str(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"\nReport written: {report_path}")

    has_errors = bool(result.missing_objects or result.missing_columns)
    if has_errors and not args.no_fail_on_error:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
