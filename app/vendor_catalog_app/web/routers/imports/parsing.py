from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from vendor_catalog_app.web.routers.imports.config import (
    IMPORT_FILE_FORMAT_OPTIONS,
    IMPORT_LAYOUT_FIELD_TARGET_KEYS,
    IMPORT_LAYOUTS,
    IMPORT_MAX_ROWS,
    IMPORT_SOURCE_SYSTEM_OPTIONS,
    IMPORT_STAGING_AREAS,
    import_target_field_groups,
    import_target_field_options,
)
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


def safe_source_system(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned in set(IMPORT_SOURCE_SYSTEM_OPTIONS):
        return cleaned
    return "spreadsheet_manual"


def safe_format_hint(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    allowed = {str(option.get("key") or "").strip().lower() for option in IMPORT_FILE_FORMAT_OPTIONS}
    if cleaned in allowed:
        return cleaned
    return "auto"


def safe_delimiter(value: str) -> str:
    cleaned = str(value or "").strip()
    if cleaned == "\\t":
        return "\t"
    if not cleaned:
        return ","
    return cleaned[0]


def safe_flow_mode(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned == "wizard":
        return "wizard"
    return "quick"


def layout_options() -> list[dict[str, str]]:
    return [
        {"key": key, "label": str(spec.get("label") or key.title()), "description": str(spec.get("description") or "")}
        for key, spec in IMPORT_LAYOUTS.items()
    ]


def source_system_options() -> list[dict[str, str]]:
    return [{"key": code, "label": code.replace("_", " ").title()} for code in IMPORT_SOURCE_SYSTEM_OPTIONS]


def file_format_options() -> list[dict[str, str]]:
    return [{"key": str(item.get("key") or ""), "label": str(item.get("label") or "")} for item in IMPORT_FILE_FORMAT_OPTIONS]


def normalize_column_name(raw_name: str) -> str:
    cleaned = str(raw_name or "").strip().lower()
    cleaned = cleaned.replace(" ", "_").replace("-", "_")
    cleaned = cleaned.replace(".", "_").replace("/", "_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned


def normalize_source_key(raw_name: str) -> str:
    cleaned = str(raw_name or "").strip().lower()
    cleaned = cleaned.replace(" ", "_").replace("-", "_")
    cleaned = cleaned.replace("/", "_").replace(":", "_")
    cleaned = cleaned.replace("[", "_").replace("]", "")
    cleaned = cleaned.replace("@", "attr_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = ".".join([part.strip("._") for part in cleaned.split(".") if part.strip("._")])
    return cleaned.strip("._")


def _source_match_key(source_key: str) -> str:
    return normalize_column_name(str(source_key or "").replace(".", "_"))


def decode_upload_bytes(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except Exception:
            continue
    raise ValueError("Could not decode upload content.")


def detect_upload_format(file_name: str, raw_bytes: bytes) -> str:
    ext = Path(str(file_name or "")).suffix.lower()
    ext_map = {
        ".csv": "csv",
        ".tsv": "tsv",
        ".json": "json",
        ".xml": "xml",
        ".txt": "delimited",
        ".psv": "delimited",
    }
    if ext in ext_map:
        return ext_map[ext]

    sample = decode_upload_bytes(raw_bytes[:4096] if raw_bytes else b"").lstrip("\ufeff").strip()
    if not sample:
        return "csv"
    if sample.startswith("{") or sample.startswith("["):
        return "json"
    if sample.startswith("<"):
        return "xml"
    first_line = sample.splitlines()[0] if "\n" in sample else sample
    if first_line.count("\t") >= max(1, first_line.count(",")):
        return "tsv"
    if "," in first_line:
        return "csv"
    if "|" in first_line or ";" in first_line:
        return "delimited"
    return "csv"


def _row_has_data(row: dict[str, str]) -> bool:
    return any(str(value or "").strip() for key, value in row.items() if not str(key).startswith("_"))


def _normalize_row_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, default=str)
    return str(value).strip()


def _normalize_source_payload(source_payload: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_key, raw_value in source_payload.items():
        key = normalize_source_key(raw_key)
        if not key:
            continue
        value = _normalize_row_value(raw_value)
        if key not in out or (not out[key] and value):
            out[key] = value
    return out


def _parse_delimited_source_rows(*, text: str, delimiter: str) -> tuple[list[dict[str, str]], list[str]]:
    stream = io.StringIO(text)
    reader = csv.reader(stream, delimiter=delimiter)
    headers = next(reader, None)
    if headers is None:
        raise ValueError("Delimited files must include a header row.")

    source_keys: list[str] = []
    for index, header in enumerate(headers, start=1):
        normalized = normalize_source_key(str(header or ""))
        if not normalized:
            normalized = f"column_{index}"
        base = normalized
        suffix = 2
        while normalized in source_keys:
            normalized = f"{base}_{suffix}"
            suffix += 1
        source_keys.append(normalized)

    rows: list[dict[str, str]] = []
    for line_number, raw_row in enumerate(reader, start=2):
        source_row: dict[str, str] = {}
        has_data = False
        for idx, source_key in enumerate(source_keys):
            value = str(raw_row[idx] if idx < len(raw_row) else "").strip()
            source_row[source_key] = value
            if value:
                has_data = True
        if has_data:
            source_row["_line"] = str(line_number)
            rows.append(source_row)
    return rows, [str(name or "") for name in headers]


def _validate_strict_delimited_layout(
    *,
    header_names: list[str],
    allowed_fields: list[str],
    layout_key: str,
) -> None:
    normalized_headers = [normalize_column_name(name) for name in header_names]
    expected_headers = [normalize_column_name(name) for name in allowed_fields]
    if normalized_headers == expected_headers:
        return

    missing = [field for field in expected_headers if field not in normalized_headers]
    extras = [field for field in normalized_headers if field not in expected_headers]
    details: list[str] = []
    if missing:
        details.append(f"missing: {', '.join(missing)}")
    if extras:
        details.append(f"unexpected: {', '.join(extras)}")
    if not details:
        details.append("column order must match template exactly")
    raise ValueError(
        "Approved layout mismatch for quick upload "
        f"({layout_key}). {'; '.join(details)}. "
        "Download and use the official template for this layout."
    )


def _infer_delimiter_from_text(text: str) -> str:
    first_line = str(text or "").splitlines()[0] if str(text or "").strip() else ""
    if not first_line:
        return ","
    ranked = [
        ("\t", first_line.count("\t")),
        (",", first_line.count(",")),
        ("|", first_line.count("|")),
        (";", first_line.count(";")),
        (":", first_line.count(":")),
    ]
    ranked.sort(key=lambda item: item[1], reverse=True)
    if ranked[0][1] <= 0:
        return ","
    return ranked[0][0]


def _flatten_object(value: Any, prefix: str = "", out: dict[str, Any] | None = None) -> dict[str, Any]:
    if out is None:
        out = {}
    if isinstance(value, dict):
        for key, nested in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            _flatten_object(nested, next_prefix, out)
        return out
    if isinstance(value, list):
        if not value:
            out[prefix or "value"] = ""
            return out
        for index, item in enumerate(value, start=1):
            next_prefix = f"{prefix}_{index}" if prefix else f"value_{index}"
            if isinstance(item, (dict, list)):
                _flatten_object(item, next_prefix, out)
            else:
                out[next_prefix] = item
        if all(not isinstance(item, (dict, list)) for item in value):
            out[prefix or "value"] = "|".join(str(item) for item in value)
        return out
    out[prefix or "value"] = value
    return out


def _resolve_json_record_path(payload: Any, record_path: str) -> tuple[list[Any], str]:
    cleaned = str(record_path or "").strip()
    if cleaned:
        current = payload
        for token in [part for part in cleaned.split(".") if part]:
            if isinstance(current, dict):
                current = current.get(token)
            elif isinstance(current, list):
                try:
                    current = current[int(token)]
                except Exception as exc:
                    raise ValueError(f"JSON record path token '{token}' is not valid for list traversal.") from exc
            else:
                current = None
                break
        if current is None:
            raise ValueError(f"JSON record path '{cleaned}' did not resolve to data.")
        if isinstance(current, list):
            return current, cleaned
        return [current], cleaned

    if isinstance(payload, list):
        return payload, ""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, list):
                return value, key
        return [payload], ""
    return [payload], ""


def _parse_json_source_rows(*, text: str, record_path: str) -> tuple[list[dict[str, str]], list[str], str]:
    warnings: list[str] = []
    try:
        payload = json.loads(text)
    except Exception as exc:
        raise ValueError(f"JSON parse failed: {exc}") from exc

    records, resolved_path = _resolve_json_record_path(payload, record_path)
    if resolved_path and not record_path:
        warnings.append(f"Detected JSON record path '{resolved_path}'.")
    if not isinstance(records, list):
        records = [records]

    source_rows: list[dict[str, str]] = []
    for line_number, record in enumerate(records, start=1):
        source_payload = _flatten_object(record if isinstance(record, (dict, list)) else {"value": record})
        source_row = _normalize_source_payload(source_payload)
        if _row_has_data(source_row):
            source_row["_line"] = str(line_number)
            source_rows.append(source_row)
    return source_rows, warnings, resolved_path


def _xml_local_name(tag: str) -> str:
    return str(tag or "").split("}", 1)[-1]


def _flatten_xml_element(element: ET.Element) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in dict(element.attrib).items():
        out[f"attr_{_xml_local_name(key)}"] = value

    def walk(node: ET.Element, prefix: str) -> None:
        children = list(node)
        text = str(node.text or "").strip()
        if not children:
            if text:
                out[prefix] = text
            return
        if text:
            out[prefix] = text
        child_name_counts = Counter(_xml_local_name(child.tag) for child in children)
        child_seen: dict[str, int] = {}
        for child in children:
            base_name = _xml_local_name(child.tag)
            child_seen[base_name] = child_seen.get(base_name, 0) + 1
            if child_name_counts[base_name] > 1:
                child_prefix = f"{prefix}.{base_name}_{child_seen[base_name]}"
            else:
                child_prefix = f"{prefix}.{base_name}"
            walk(child, child_prefix)

    walk(element, _xml_local_name(element.tag))
    return out


def _resolve_xml_record_elements(root: ET.Element, record_tag: str) -> tuple[list[ET.Element], str]:
    cleaned = str(record_tag or "").strip()
    if cleaned:
        matched = [element for element in root.iter() if _xml_local_name(element.tag) == cleaned]
        if not matched:
            raise ValueError(f"XML record tag '{cleaned}' was not found.")
        return matched, cleaned

    direct_children = list(root)
    if not direct_children:
        return [root], ""

    direct_counts = Counter(_xml_local_name(child.tag) for child in direct_children)
    repeated = [name for name, count in direct_counts.items() if count > 1]
    if repeated:
        selected = repeated[0]
        return [child for child in direct_children if _xml_local_name(child.tag) == selected], selected

    if len(direct_children) == 1:
        nested_children = list(direct_children[0])
        nested_counts = Counter(_xml_local_name(child.tag) for child in nested_children)
        repeated_nested = [name for name, count in nested_counts.items() if count > 1]
        if repeated_nested:
            selected = repeated_nested[0]
            return [child for child in nested_children if _xml_local_name(child.tag) == selected], selected
    return direct_children, ""


def _parse_xml_source_rows(*, text: str, record_tag: str) -> tuple[list[dict[str, str]], list[str], str]:
    warnings: list[str] = []
    try:
        root = ET.fromstring(text)
    except Exception as exc:
        raise ValueError(f"XML parse failed: {exc}") from exc

    records, resolved_tag = _resolve_xml_record_elements(root, record_tag)
    if resolved_tag and not record_tag:
        warnings.append(f"Detected XML record tag '{resolved_tag}'.")

    source_rows: list[dict[str, str]] = []
    for line_number, element in enumerate(records, start=1):
        source_payload = _flatten_xml_element(element)
        source_row = _normalize_source_payload(source_payload)
        if _row_has_data(source_row):
            source_row["_line"] = str(line_number)
            source_rows.append(source_row)
    return source_rows, warnings, resolved_tag


def _build_source_fields(source_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    ordered_keys: list[str] = []
    samples: dict[str, str] = {}
    sample_values: dict[str, list[str]] = {}
    non_empty_counts: dict[str, int] = {}

    for row in source_rows:
        for key, raw_value in row.items():
            if str(key).startswith("_"):
                continue
            if key not in ordered_keys:
                ordered_keys.append(key)
                samples[key] = ""
                sample_values[key] = []
                non_empty_counts[key] = 0
            value = str(raw_value or "").strip()
            if value:
                non_empty_counts[key] = int(non_empty_counts.get(key, 0)) + 1
                if not samples.get(key):
                    samples[key] = value[:140]
                samples_for_key = sample_values.setdefault(key, [])
                if value not in samples_for_key and len(samples_for_key) < 3:
                    samples_for_key.append(value[:140])

    return [
        {
            "key": key,
            "label": key,
            "normalized_key": _source_match_key(key),
            "sample_value": str(samples.get(key) or ""),
            "sample_values": list(sample_values.get(key) or []),
            "non_empty_count": str(non_empty_counts.get(key, 0)),
        }
        for key in ordered_keys
    ]


def _mapping_candidate_score(target_field: str, source_key: str) -> int:
    alias_map = {
        "supplier": "vendor",
        "supplier_name": "vendor_name",
        "supplier_id": "vendor_id",
        "invoice_no": "invoice_number",
        "inv_no": "invoice_number",
        "remit_to": "payment_address",
        "pay_date": "payment_date",
        "pay_ref": "payment_reference",
    }

    def apply_alias(value: str) -> str:
        normalized = normalize_column_name(value)
        return str(alias_map.get(normalized, normalized))

    target_norm = apply_alias(target_field)
    source_match = apply_alias(_source_match_key(source_key))
    source_last = apply_alias(_source_match_key(str(source_key).split(".")[-1]))
    if not target_norm or not source_match:
        return 0
    if source_match == target_norm:
        return 100
    if source_last == target_norm:
        return 94
    if source_match.endswith(f"_{target_norm}"):
        return 88
    if source_last and (source_last in target_norm or target_norm in source_last):
        return 82

    target_tokens = [token for token in target_norm.split("_") if token]
    source_tokens = [token for token in source_match.split("_") if token]
    if target_tokens and all(token in source_tokens for token in target_tokens):
        return 76

    if "email" in target_norm and "email" in source_match:
        return 72
    if "phone" in target_norm and ("phone" in source_match or "tel" in source_match):
        return 72
    if "name" in target_norm and "name" in source_match:
        return 70
    if "id" in target_norm and source_last.endswith("_id"):
        return 68
    return 0


def _resolve_source_target_mapping(
    *,
    source_fields: list[dict[str, str]],
    requested_mapping: dict[str, str] | None = None,
) -> dict[str, str]:
    ordered_target_keys = [str(item.get("key") or "").strip() for item in import_target_field_options() if str(item.get("key") or "").strip()]
    valid_target_keys = set(ordered_target_keys)
    source_keys = [str(item.get("key") or "").strip() for item in source_fields if str(item.get("key") or "").strip()]
    selected: dict[str, str] = {}
    requested = dict(requested_mapping or {})
    for source_key in source_keys:
        explicit_target = str(requested.get(source_key) or "").strip()
        if explicit_target in valid_target_keys:
            selected[source_key] = explicit_target
            continue

        best_target = ""
        best_score = 0
        for target_key in ordered_target_keys:
            target_field = str(target_key.split(".", 1)[-1] if "." in target_key else target_key)
            score = _mapping_candidate_score(target_field, source_key)
            if score > best_score:
                best_score = score
                best_target = target_key
        selected[source_key] = best_target if best_score >= 68 else ""
    return selected


def _layout_field_mapping_from_source_targets(
    *,
    layout_key: str,
    source_target_mapping: dict[str, str],
) -> dict[str, str]:
    out: dict[str, str] = {}
    target_to_source: dict[str, str] = {}
    for source_key, target_key in dict(source_target_mapping or {}).items():
        source = str(source_key or "").strip()
        target = str(target_key or "").strip()
        if not source or not target or target in target_to_source:
            continue
        target_to_source[target] = source
    layout_target_map = dict(IMPORT_LAYOUT_FIELD_TARGET_KEYS.get(layout_key, {}) or {})
    for field, target_key in layout_target_map.items():
        out[str(field)] = str(target_to_source.get(str(target_key), "")).strip()
    return out


_REPEATING_SEGMENT_PATTERN = re.compile(r"(?:_\d+|[a-zA-Z]+\d+)$")


def _source_group_key(source_key: str) -> tuple[str, bool]:
    key = str(source_key or "").strip()
    if not key:
        return "__static__", False
    parts = [part for part in key.split(".") if str(part).strip()]
    if len(parts) <= 1:
        return "__static__", False
    parent_parts = parts[:-1]
    group_key = ".".join(parent_parts)
    is_repeating = any(bool(_REPEATING_SEGMENT_PATTERN.search(part)) for part in parent_parts)
    return group_key or "__static__", is_repeating


def _build_stage_area_rows(
    *,
    source_rows: list[dict[str, str]],
    source_target_mapping: dict[str, str],
) -> dict[str, list[dict[str, Any]]]:
    area_fields = {
        str(area): {str(field_key) for field_key, _ in list(spec.get("fields") or [])}
        for area, spec in IMPORT_STAGING_AREAS.items()
    }
    area_rows: dict[str, list[dict[str, Any]]] = {str(area): [] for area in IMPORT_STAGING_AREAS}
    for row_index, source_row in enumerate(source_rows, start=1):
        static_payload_by_area: dict[str, dict[str, str]] = {}
        repeating_payloads_by_area: dict[str, dict[str, dict[str, str]]] = {}
        for source_key, target_key in dict(source_target_mapping or {}).items():
            source = str(source_key or "").strip()
            target = str(target_key or "").strip()
            if not source or not target or "." not in target:
                continue
            area_key, field_key = target.split(".", 1)
            if area_key not in area_fields:
                continue
            if field_key not in area_fields[area_key]:
                continue
            value = str(source_row.get(source, "") or "").strip()
            if not value:
                continue
            group_key, is_repeating = _source_group_key(source)
            if is_repeating:
                repeating_payloads_by_area.setdefault(area_key, {}).setdefault(group_key, {})[field_key] = value
            else:
                static_payload_by_area.setdefault(area_key, {})[field_key] = value
        line_number = str(source_row.get("_line") or row_index)
        for area_key in IMPORT_STAGING_AREAS:
            static_payload = dict(static_payload_by_area.get(area_key) or {})
            repeating_payloads = dict(repeating_payloads_by_area.get(area_key) or {})
            if repeating_payloads:
                for group_key, repeating_payload in repeating_payloads.items():
                    payload = dict(static_payload)
                    payload.update(dict(repeating_payload or {}))
                    if not payload:
                        continue
                    area_rows.setdefault(area_key, []).append(
                        {
                            "row_index": row_index,
                            "line_number": line_number,
                            "source_group_key": str(group_key or "__static__"),
                            "payload": payload,
                        }
                    )
                continue
            payload = static_payload
            if not payload:
                continue
            area_rows.setdefault(area_key, []).append(
                {
                    "row_index": row_index,
                    "line_number": line_number,
                    "source_group_key": "__static__",
                    "payload": payload,
                }
            )
    return area_rows


def _resolve_field_mapping(
    *,
    allowed_fields: list[str],
    source_fields: list[dict[str, str]],
    requested_mapping: dict[str, str] | None = None,
) -> dict[str, str]:
    source_keys = [str(item.get("key") or "").strip() for item in source_fields if str(item.get("key") or "").strip()]
    source_key_set = set(source_keys)
    selected_mapping: dict[str, str] = {}
    raw_requested = dict(requested_mapping or {})
    for field in allowed_fields:
        requested = str(raw_requested.get(field) or "").strip()
        if requested and requested in source_key_set:
            selected_mapping[field] = requested
            continue

        best_source = ""
        best_score = 0
        for source_key in source_keys:
            score = _mapping_candidate_score(field, source_key)
            if score > best_score:
                best_score = score
                best_source = source_key
        selected_mapping[field] = best_source if best_score >= 68 else ""
    return selected_mapping


def _apply_field_mapping(
    *,
    source_rows: list[dict[str, str]],
    allowed_fields: list[str],
    field_mapping: dict[str, str],
) -> list[dict[str, str]]:
    mapped_rows: list[dict[str, str]] = []
    for row_index, source_row in enumerate(source_rows, start=1):
        mapped: dict[str, str] = {}
        for field in allowed_fields:
            source_key = str(field_mapping.get(field) or "").strip()
            mapped[field] = str(source_row.get(source_key, "") or "").strip() if source_key else ""
        mapped["_line"] = str(source_row.get("_line") or row_index)
        mapped_rows.append(mapped)
    return mapped_rows


def resolve_field_mapping(
    *,
    allowed_fields: list[str],
    source_fields: list[dict[str, str]],
    requested_mapping: dict[str, str] | None = None,
) -> dict[str, str]:
    return _resolve_field_mapping(
        allowed_fields=allowed_fields,
        source_fields=source_fields,
        requested_mapping=requested_mapping,
    )


def apply_field_mapping(
    *,
    source_rows: list[dict[str, str]],
    allowed_fields: list[str],
    field_mapping: dict[str, str],
) -> list[dict[str, str]]:
    return _apply_field_mapping(
        source_rows=source_rows,
        allowed_fields=allowed_fields,
        field_mapping=field_mapping,
    )


def resolve_source_target_mapping(
    *,
    source_fields: list[dict[str, str]],
    requested_mapping: dict[str, str] | None = None,
) -> dict[str, str]:
    return _resolve_source_target_mapping(
        source_fields=source_fields,
        requested_mapping=requested_mapping,
    )


def layout_field_mapping_from_source_targets(
    *,
    layout_key: str,
    source_target_mapping: dict[str, str],
) -> dict[str, str]:
    return _layout_field_mapping_from_source_targets(
        layout_key=layout_key,
        source_target_mapping=source_target_mapping,
    )


def build_stage_area_rows(
    *,
    source_rows: list[dict[str, str]],
    source_target_mapping: dict[str, str],
) -> dict[str, list[dict[str, Any]]]:
    return _build_stage_area_rows(
        source_rows=source_rows,
        source_target_mapping=source_target_mapping,
    )


def parse_layout_rows(
    layout_key: str,
    raw_bytes: bytes,
    *,
    file_name: str = "",
    format_hint: str = "auto",
    delimiter: str = ",",
    json_record_path: str = "",
    xml_record_tag: str = "",
    strict_layout: bool = False,
    field_mapping: dict[str, str] | None = None,
    source_target_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    spec = IMPORT_LAYOUTS[layout_key]
    allowed_fields = [str(field) for field in spec.get("fields", [])]
    text = decode_upload_bytes(raw_bytes)
    detected_format = detect_upload_format(file_name, raw_bytes)
    requested_format = safe_format_hint(format_hint)
    effective_format = detected_format if requested_format == "auto" else requested_format
    selected_delimiter = safe_delimiter(delimiter)
    used_delimiter = selected_delimiter
    warnings: list[str] = []
    resolved_json_path = str(json_record_path or "").strip()
    resolved_xml_tag = str(xml_record_tag or "").strip()
    source_rows: list[dict[str, str]] = []

    if effective_format == "tsv":
        source_rows, header_names = _parse_delimited_source_rows(text=text, delimiter="\t")
        if strict_layout:
            _validate_strict_delimited_layout(
                header_names=header_names,
                allowed_fields=allowed_fields,
                layout_key=layout_key,
            )
        used_delimiter = "\t"
    elif effective_format in {"csv", "delimited"}:
        active_delimiter = selected_delimiter
        if requested_format == "auto" and detected_format == "delimited" and selected_delimiter == ",":
            active_delimiter = _infer_delimiter_from_text(text)
        source_rows, header_names = _parse_delimited_source_rows(text=text, delimiter=active_delimiter)
        if strict_layout:
            _validate_strict_delimited_layout(
                header_names=header_names,
                allowed_fields=allowed_fields,
                layout_key=layout_key,
            )
        used_delimiter = active_delimiter
    elif effective_format == "json":
        if strict_layout:
            raise ValueError("Quick upload supports approved CSV/TSV layouts only. Use Advanced Wizard for JSON.")
        source_rows, warnings, resolved_json_path = _parse_json_source_rows(text=text, record_path=json_record_path)
    elif effective_format == "xml":
        if strict_layout:
            raise ValueError("Quick upload supports approved CSV/TSV layouts only. Use Advanced Wizard for XML.")
        source_rows, warnings, resolved_xml_tag = _parse_xml_source_rows(text=text, record_tag=xml_record_tag)
    else:
        raise ValueError(f"Unsupported file format '{effective_format}'.")

    if not source_rows:
        raise ValueError("No data rows were found in the upload.")
    if len(source_rows) > IMPORT_MAX_ROWS:
        raise ValueError(f"Upload is too large. Maximum {IMPORT_MAX_ROWS} rows per import.")
    source_fields = _build_source_fields(source_rows)
    resolved_source_target_mapping = _resolve_source_target_mapping(
        source_fields=source_fields,
        requested_mapping=source_target_mapping,
    )
    preferred_layout_mapping = _layout_field_mapping_from_source_targets(
        layout_key=layout_key,
        source_target_mapping=resolved_source_target_mapping,
    )
    combined_requested_layout_mapping = dict(preferred_layout_mapping)
    combined_requested_layout_mapping.update(dict(field_mapping or {}))
    resolved_layout_mapping = _resolve_field_mapping(
        allowed_fields=allowed_fields,
        source_fields=source_fields,
        requested_mapping=combined_requested_layout_mapping,
    )
    rows = _apply_field_mapping(
        source_rows=source_rows,
        allowed_fields=allowed_fields,
        field_mapping=resolved_layout_mapping,
    )
    stage_area_rows = _build_stage_area_rows(
        source_rows=source_rows,
        source_target_mapping=resolved_source_target_mapping,
    )
    return {
        "rows": rows,
        "source_rows": source_rows,
        "source_fields": source_fields,
        "field_mapping": resolved_layout_mapping,
        "source_target_mapping": resolved_source_target_mapping,
        "stage_area_rows": stage_area_rows,
        "target_field_options": import_target_field_options(),
        "detected_format": detected_format,
        "effective_format": effective_format,
        "warnings": warnings,
        "parser_options": {
            "format_hint": requested_format,
            "delimiter": used_delimiter,
            "json_record_path": resolved_json_path,
            "xml_record_tag": resolved_xml_tag,
        },
    }


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
    selected_flow_mode: str = "quick",
    selected_source_system: str = "spreadsheet_manual",
    source_object: str = "",
    source_file_name: str = "",
    detected_file_type: str = "",
    effective_file_type: str = "",
    parser_options: dict[str, str] | None = None,
    parser_warnings: list[str] | None = None,
    staging_job_id: str = "",
    staged_row_count: int = 0,
    staging_warning: str = "",
    preview_token: str = "",
    preview_rows: list[dict[str, Any]] | None = None,
    preview_total_rows: int = 0,
    preview_hidden_count: int = 0,
    source_field_map: list[dict[str, str]] | None = None,
    selected_source_target_mapping: dict[str, str] | None = None,
    mapping_profiles: list[dict[str, Any]] | None = None,
    selected_mapping_profile_id: str = "",
    mapping_profile_saved: str = "",
    import_results: list[dict[str, Any]] | None = None,
    import_reason: str = "",
) -> dict[str, Any]:
    selected_parser_options = {
        "format_hint": "auto",
        "delimiter": ",",
        "json_record_path": "",
        "xml_record_tag": "",
    }
    if parser_options:
        selected_parser_options.update(
            {
                "format_hint": safe_format_hint(str(parser_options.get("format_hint") or "auto")),
                "delimiter": safe_delimiter(str(parser_options.get("delimiter") or ",")),
                "json_record_path": str(parser_options.get("json_record_path") or "").strip(),
                "xml_record_tag": str(parser_options.get("xml_record_tag") or "").strip(),
            }
        )

    wizard_step = "upload"
    if preview_rows:
        wizard_step = "preview"
    if import_results:
        wizard_step = "complete"

    selected_layout_spec = IMPORT_LAYOUTS[selected_layout]
    source_target_values = {
        str(item.get("key") or ""): ""
        for item in list(source_field_map or [])
        if str(item.get("key") or "").strip()
    }
    if selected_source_target_mapping:
        for source_key in list(source_target_values):
            source_target_values[source_key] = str(selected_source_target_mapping.get(source_key) or "").strip()

    mapped_source_count = sum(1 for value in source_target_values.values() if str(value or "").strip())
    total_source_count = len(source_target_values)
    unmapped_source_count = max(0, total_source_count - mapped_source_count)
    layout_target_map = dict(IMPORT_LAYOUT_FIELD_TARGET_KEYS.get(selected_layout) or {})
    required_target_keys: list[str] = []
    seen_required: set[str] = set()
    for _field_name, target_key in layout_target_map.items():
        key = str(target_key or "").strip()
        if not key or key in seen_required:
            continue
        seen_required.add(key)
        required_target_keys.append(key)
    mapped_target_keys = {str(value or "").strip() for value in source_target_values.values() if str(value or "").strip()}
    required_mapped_count = sum(1 for key in required_target_keys if key in mapped_target_keys)
    required_remaining_count = max(0, len(required_target_keys) - required_mapped_count)

    initial_wizard_step = 1
    if preview_rows:
        initial_wizard_step = 3
    if import_results:
        initial_wizard_step = 5

    return {
        "layout_options": layout_options(),
        "source_system_options": source_system_options(),
        "file_format_options": file_format_options(),
        "selected_layout": selected_layout,
        "selected_flow_mode": safe_flow_mode(selected_flow_mode),
        "selected_source_system": safe_source_system(selected_source_system),
        "source_object": str(source_object or "").strip(),
        "source_file_name": str(source_file_name or "").strip(),
        "detected_file_type": str(detected_file_type or "").strip(),
        "effective_file_type": str(effective_file_type or "").strip(),
        "parser_options": selected_parser_options,
        "parser_warnings": list(parser_warnings or []),
        "staging_job_id": str(staging_job_id or "").strip(),
        "staged_row_count": int(staged_row_count or 0),
        "staging_warning": str(staging_warning or "").strip(),
        "wizard_step": wizard_step,
        "selected_layout_spec": selected_layout_spec,
        "preview_token": preview_token,
        "preview_rows": preview_rows or [],
        "preview_total_rows": int(preview_total_rows or 0),
        "preview_hidden_count": int(preview_hidden_count or 0),
        "source_field_map": source_field_map or [],
        "selected_source_target_mapping": source_target_values,
        "target_field_groups": import_target_field_groups(),
        "mapping_profiles": mapping_profiles or [],
        "selected_mapping_profile_id": str(selected_mapping_profile_id or "").strip(),
        "mapping_profile_saved": str(mapping_profile_saved or "").strip(),
        "import_results": import_results or [],
        "import_reason": import_reason,
        "import_merge_reason_options": IMPORT_MERGE_REASON_OPTIONS,
        "has_preview_rows": bool(preview_rows),
        "has_import_results": bool(import_results),
        "wizard_initial_step": initial_wizard_step,
        "mapping_total_source_fields": total_source_count,
        "mapping_mapped_source_fields": mapped_source_count,
        "mapping_unmapped_source_fields": unmapped_source_count,
        "mapping_required_target_keys": required_target_keys,
        "mapping_required_count": len(required_target_keys),
        "mapping_required_mapped_count": required_mapped_count,
        "mapping_required_remaining_count": required_remaining_count,
    }

