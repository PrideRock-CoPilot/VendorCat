from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


TOKEN_PATTERN = re.compile(r"\{(catalog|fq_schema)\}")


def _parse_fq_schema(value: str) -> tuple[str, str]:
    raw = str(value or "").strip()
    parts = [item.strip() for item in raw.split(".", 1)]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("Expected schema in '<catalog>.<schema>' format.")
    return parts[0], parts[1]


def _build_context(args: argparse.Namespace) -> dict[str, str]:
    if args.fq_schema:
        catalog, schema = _parse_fq_schema(args.fq_schema)
    else:
        catalog = str(args.catalog or "").strip()
        schema = str(args.schema or "").strip()
    if not catalog or not schema:
        raise ValueError("Provide --fq-schema or both --catalog and --schema.")
    return {
        "catalog": catalog,
        "fq_schema": f"{catalog}.{schema}",
    }


def _render_template(path: Path, context: dict[str, str]) -> str:
    text = path.read_text(encoding="utf-8")
    return TOKEN_PATTERN.sub(lambda match: context[match.group(1)], text).strip()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a single, full Databricks DDL SQL file for Vendor Catalog."
        )
    )
    parser.add_argument(
        "--input-dir",
        default=str(Path(__file__).resolve().parent),
        help="Directory containing Databricks SQL templates.",
    )
    parser.add_argument(
        "--output-path",
        default=str(Path(__file__).resolve().parent / "rendered" / "000_full_databricks_ddl.sql"),
        help="Output file path for the single rendered DDL script.",
    )
    parser.add_argument("--catalog", default="", help="Target Unity Catalog name.")
    parser.add_argument("--schema", default="", help="Target schema name.")
    parser.add_argument(
        "--fq-schema",
        default="",
        help="Target '<catalog>.<schema>' value (overrides --catalog/--schema).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        context = _build_context(args)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    input_dir = Path(args.input_dir).resolve()
    output_path = Path(args.output_path).resolve()
    base_ddl = input_dir / "001_create_databricks_schema.sql"

    if not base_ddl.exists():
        print(f"ERROR: Base DDL template not found: {base_ddl}", file=sys.stderr)
        return 2

    parts: list[str] = []
    parts.append(
        "-- AUTO-GENERATED FILE. Do not edit directly.\n"
        "-- Source templates: setup/v1_schema/databricks/*.sql"
    )
    parts.append(_render_template(base_ddl, context))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n".join(parts).strip() + "\n", encoding="utf-8")

    print(f"Rendered full DDL to: {output_path}")
    print(f"Target schema: {context['fq_schema']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
