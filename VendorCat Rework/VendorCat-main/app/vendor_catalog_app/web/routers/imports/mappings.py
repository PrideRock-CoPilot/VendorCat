from __future__ import annotations

import hashlib
from datetime import datetime
import time
import uuid
from typing import Any

from vendor_catalog_app.web.routers.imports.config import IMPORT_LAYOUTS
from vendor_catalog_app.web.routers.imports.parsing import normalize_column_name

IMPORT_MAPPING_SETTING_KEY = "imports.mapping_profiles.v1"
IMPORT_MAPPING_PROFILE_LIMIT = 120


def _safe_layout_key(layout_key: str) -> str:
    cleaned = str(layout_key or "").strip().lower()
    if cleaned in IMPORT_LAYOUTS:
        return cleaned
    return "vendors"


def _safe_mapping_profile_records(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = list((payload or {}).get("profiles") or [])
    return [dict(item) for item in rows if isinstance(item, dict)]


def _source_signature(source_fields: list[dict[str, str]]) -> str:
    keys = [
        normalize_column_name(str(item.get("key") or "").replace(".", "_"))
        for item in source_fields
        if str(item.get("key") or "").strip()
    ]
    canonical = "|".join(sorted(set([key for key in keys if key])))
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest() if canonical else ""


def _profile_updated_sort_value(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _normalize_profile_row(row: dict[str, Any], *, layout_key: str) -> dict[str, Any]:
    return {
        "profile_id": str(row.get("profile_id") or "").strip(),
        "profile_name": str(row.get("profile_name") or "").strip(),
        "layout_key": layout_key,
        "file_format": str(row.get("file_format") or "").strip().lower(),
        "source_signature": str(row.get("source_signature") or "").strip(),
        "source_fields": list(row.get("source_fields") or []),
        "source_target_mapping": dict(row.get("source_target_mapping") or {}),
        "field_mapping": dict(row.get("field_mapping") or {}),
        "parser_options": dict(row.get("parser_options") or {}),
        "updated_at": row.get("updated_at"),
    }


def load_mapping_profiles(repo, *, user_principal: str, layout_key: str) -> list[dict[str, Any]]:
    try:
        if hasattr(repo, "migrate_legacy_import_mapping_profiles"):
            repo.migrate_legacy_import_mapping_profiles(
                user_principal=str(user_principal or "").strip(),
                actor_user_principal=str(user_principal or "").strip(),
            )
    except Exception:
        pass

    safe_layout = _safe_layout_key(layout_key)
    if hasattr(repo, "list_import_mapping_profiles"):
        try:
            shared = list(repo.list_import_mapping_profiles(layout_key=safe_layout, include_inactive=False) or [])
            profiles = [
                _normalize_profile_row(dict(item), layout_key=safe_layout)
                for item in shared
                if isinstance(item, dict) and _safe_layout_key(str(item.get("layout_key") or "")) == safe_layout
            ]
            if profiles:
                profiles.sort(
                    key=lambda item: _profile_updated_sort_value(item.get("updated_at")),
                    reverse=True,
                )
                return profiles
        except Exception:
            pass

    if not hasattr(repo, "get_user_setting"):
        return []
    try:
        payload = repo.get_user_setting(user_principal, IMPORT_MAPPING_SETTING_KEY)
    except Exception:
        return []

    profiles = []
    for row in _safe_mapping_profile_records(payload):
        if _safe_layout_key(str(row.get("layout_key") or "")) != safe_layout:
            continue
        profiles.append(_normalize_profile_row(row, layout_key=safe_layout))
    profiles.sort(key=lambda item: _profile_updated_sort_value(item.get("updated_at")), reverse=True)
    return profiles


def find_profile_by_id(profiles: list[dict[str, Any]], profile_id: str) -> dict[str, Any] | None:
    key = str(profile_id or "").strip()
    if not key:
        return None
    for item in profiles:
        if str(item.get("profile_id") or "").strip() == key:
            return dict(item)
    return None


def compatible_profiles(
    *,
    profiles: list[dict[str, Any]],
    file_format: str,
    source_fields: list[dict[str, str]],
) -> list[dict[str, Any]]:
    fmt = str(file_format or "").strip().lower()
    signature = _source_signature(source_fields)
    matches: list[dict[str, Any]] = []
    for item in profiles:
        item_format = str(item.get("file_format") or "").strip().lower()
        if item_format and fmt and item_format != fmt:
            continue
        item_signature = str(item.get("source_signature") or "").strip()
        if signature and item_signature and item_signature != signature:
            continue
        matches.append(dict(item))
    matches.sort(key=lambda row: _profile_updated_sort_value(row.get("updated_at")), reverse=True)
    return matches


def save_mapping_profile(
    repo,
    *,
    user_principal: str,
    layout_key: str,
    profile_name: str,
    file_format: str,
    source_fields: list[dict[str, str]],
    source_target_mapping: dict[str, str] | None = None,
    field_mapping: dict[str, str] | None = None,
    parser_options: dict[str, Any] | None = None,
    profile_id: str = "",
) -> str:
    cleaned_name = str(profile_name or "").strip()
    if not cleaned_name:
        return ""
    safe_layout = _safe_layout_key(layout_key)
    safe_format = str(file_format or "").strip().lower()
    cleaned_source_target_mapping = {
        str(k): str(v)
        for k, v in dict(source_target_mapping or {}).items()
        if str(k).strip()
    }
    cleaned_mapping = {str(k): str(v) for k, v in dict(field_mapping or {}).items() if str(k).strip()}
    normalized_source_fields = [
        {
            "key": str(item.get("key") or "").strip(),
            "label": str(item.get("label") or "").strip(),
            "normalized_key": str(item.get("normalized_key") or "").strip(),
            "sample_value": str(item.get("sample_value") or "").strip(),
            "sample_values": list(item.get("sample_values") or []),
            "non_empty_count": str(item.get("non_empty_count") or "").strip(),
        }
        for item in list(source_fields or [])
        if str(item.get("key") or "").strip()
    ]
    signature = _source_signature(normalized_source_fields)

    if hasattr(repo, "save_import_mapping_profile"):
        try:
            return str(
                repo.save_import_mapping_profile(
                    profile_id=str(profile_id or "").strip(),
                    layout_key=safe_layout,
                    profile_name=cleaned_name,
                    file_format=safe_format,
                    source_signature=signature,
                    source_fields=normalized_source_fields,
                    source_target_mapping=cleaned_source_target_mapping,
                    field_mapping=cleaned_mapping,
                    parser_options=dict(parser_options or {}),
                    active_flag=True,
                    actor_user_principal=str(user_principal or "").strip() or "system",
                )
                or ""
            ).strip()
        except Exception:
            # Fall back to legacy settings persistence when shared profile storage is unavailable.
            pass

    if not hasattr(repo, "get_user_setting") or not hasattr(repo, "save_user_setting"):
        return ""
    now_ts = time.time()
    setting_payload = {}
    try:
        setting_payload = repo.get_user_setting(user_principal, IMPORT_MAPPING_SETTING_KEY) or {}
    except Exception:
        setting_payload = {}
    rows = _safe_mapping_profile_records(setting_payload)
    target_profile_id = str(profile_id or "").strip() or f"imap-{uuid.uuid4()}"
    updated = False
    for item in rows:
        if str(item.get("profile_id") or "").strip() != target_profile_id:
            continue
        item["profile_name"] = cleaned_name
        item["layout_key"] = safe_layout
        item["file_format"] = safe_format
        item["source_signature"] = signature
        item["source_fields"] = normalized_source_fields
        item["source_target_mapping"] = cleaned_source_target_mapping
        item["field_mapping"] = cleaned_mapping
        item["parser_options"] = dict(parser_options or {})
        item["updated_at"] = now_ts
        updated = True
        break
    if not updated:
        rows.append(
            {
                "profile_id": target_profile_id,
                "profile_name": cleaned_name,
                "layout_key": safe_layout,
                "file_format": safe_format,
                "source_signature": signature,
                "source_fields": normalized_source_fields,
                "source_target_mapping": cleaned_source_target_mapping,
                "field_mapping": cleaned_mapping,
                "parser_options": dict(parser_options or {}),
                "updated_at": now_ts,
            }
        )
    rows.sort(key=lambda row: float(row.get("updated_at") or 0.0), reverse=True)
    rows = rows[:IMPORT_MAPPING_PROFILE_LIMIT]
    try:
        repo.save_user_setting(
            user_principal,
            IMPORT_MAPPING_SETTING_KEY,
            {"profiles": rows},
        )
        return target_profile_id
    except Exception:
        return ""
