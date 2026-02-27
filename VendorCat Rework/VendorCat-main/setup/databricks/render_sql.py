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


def _render_file(source_path: Path, target_path: Path, context: dict[str, str]) -> None:
    text = source_path.read_text(encoding="utf-8")
    rendered = TOKEN_PATTERN.sub(lambda match: context[match.group(1)], text)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(rendered, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render Databricks bootstrap SQL templates with catalog/schema values."
    )
    parser.add_argument(
        "--input-dir",
        default=str(Path(__file__).resolve().parent),
        help="Directory containing template SQL files.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent / "rendered"),
        help="Directory where rendered SQL files will be written.",
    )
    parser.add_argument("--catalog", default="", help="Target Unity Catalog name.")
    parser.add_argument("--schema", default="", help="Target schema name.")
    parser.add_argument(
        "--fq-schema",
        default="",
        help="Target '<catalog>.<schema>' value (overrides --catalog/--schema).",
    )
    args = parser.parse_args()

    try:
        context = _build_context(args)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    if not input_dir.exists():
        print(f"ERROR: Input directory not found: {input_dir}", file=sys.stderr)
        return 2

    sql_files = sorted(path for path in input_dir.glob("*.sql") if path.is_file())
    if not sql_files:
        print(f"ERROR: No SQL files found in {input_dir}", file=sys.stderr)
        return 2

    for source_path in sql_files:
        target_path = output_dir / source_path.name
        _render_file(source_path, target_path, context)
        print(f"Rendered {source_path.name} -> {target_path}")

    print(
        f"Done. Rendered {len(sql_files)} file(s) with fq_schema={context['fq_schema']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
