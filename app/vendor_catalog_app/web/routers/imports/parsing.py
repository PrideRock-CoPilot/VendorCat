from __future__ import annotations

import csv
import io
from typing import Any

from vendor_catalog_app.web.routers.imports.config import IMPORT_LAYOUTS, IMPORT_MAX_ROWS
from vendor_catalog_app.web.routers.vendors.constants import IMPORT_MERGE_REASON_OPTIONS


def can_manage_imports(user) -> bool:
    return bool(getattr(user, "can_edit", False))


def write_blocked(user) -> bool:
    return bool(getattr(getattr(user, "config", None), "locked_mode", False))


def safe_layout(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned in IMPORT_LAYOUTS:
        return cleaned
    return "vendors"


def layout_options() -> list[dict[str, str]]:
    return [
        {"key": key, "label": str(spec.get("label") or key.title()), "description": str(spec.get("description") or "")}
        for key, spec in IMPORT_LAYOUTS.items()
    ]


def normalize_column_name(raw_name: str) -> str:
    cleaned = str(raw_name or "").strip().lower()
    cleaned = cleaned.replace(" ", "_").replace("-", "_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned


def decode_upload_bytes(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except Exception:
            continue
    raise ValueError("Could not decode upload. Use UTF-8 CSV.")


def parse_layout_rows(layout_key: str, raw_bytes: bytes) -> list[dict[str, str]]:
    spec = IMPORT_LAYOUTS[layout_key]
    text = decode_upload_bytes(raw_bytes)
    stream = io.StringIO(text)
    reader = csv.DictReader(stream)
    if not reader.fieldnames:
        raise ValueError("CSV must include a header row.")

    normalized_fields = [normalize_column_name(name) for name in reader.fieldnames]
    field_lookup: dict[str, str] = {}
    for idx, normalized in enumerate(normalized_fields):
        if normalized and idx < len(reader.fieldnames):
            field_lookup[normalized] = reader.fieldnames[idx]

    allowed_fields = [str(field) for field in spec.get("fields", [])]
    rows: list[dict[str, str]] = []
    for line_number, row in enumerate(reader, start=2):
        normalized_row: dict[str, str] = {}
        for field in allowed_fields:
            header_name = field_lookup.get(field, "")
            value = row.get(header_name, "") if header_name else ""
            normalized_row[field] = str(value or "").strip()
        if any(str(value).strip() for value in normalized_row.values()):
            normalized_row["_line"] = str(line_number)
            rows.append(normalized_row)
    if not rows:
        raise ValueError("No data rows were found in the upload.")
    if len(rows) > IMPORT_MAX_ROWS:
        raise ValueError(f"Upload is too large. Maximum {IMPORT_MAX_ROWS} rows per import.")
    return rows


def import_template_csv(layout_key: str) -> tuple[str, str]:
    selected_layout = safe_layout(layout_key)
    spec = IMPORT_LAYOUTS[selected_layout]
    fields = [str(field) for field in spec.get("fields", [])]
    sample_rows = list(spec.get("sample_rows") or [])
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for sample in sample_rows:
        writer.writerow({field: str(sample.get(field, "") or "") for field in fields})
    filename = f"vendorcat_{selected_layout}_template.csv"
    return filename, stream.getvalue()


def render_context(
    *,
    selected_layout: str,
    preview_token: str = "",
    preview_rows: list[dict[str, Any]] | None = None,
    preview_total_rows: int = 0,
    preview_hidden_count: int = 0,
    import_results: list[dict[str, Any]] | None = None,
    import_reason: str = "",
) -> dict[str, Any]:
    return {
        "layout_options": layout_options(),
        "selected_layout": selected_layout,
        "selected_layout_spec": IMPORT_LAYOUTS[selected_layout],
        "preview_token": preview_token,
        "preview_rows": preview_rows or [],
        "preview_total_rows": int(preview_total_rows or 0),
        "preview_hidden_count": int(preview_hidden_count or 0),
        "import_results": import_results or [],
        "import_reason": import_reason,
        "import_merge_reason_options": IMPORT_MERGE_REASON_OPTIONS,
    }

