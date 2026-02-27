from __future__ import annotations

import hashlib
import io
from collections import Counter
from typing import Any
import zipfile

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.imports.apply_ops import apply_import_row
from vendor_catalog_app.web.routers.imports.config import (
    IMPORT_LAYOUTS,
    IMPORT_PREVIEW_RENDER_LIMIT,
    IMPORT_SOURCE_SYSTEM_OPTIONS,
    import_dynamic_field_catalog,
    import_target_field_groups,
)
from vendor_catalog_app.web.routers.imports.guided import dismiss_imports_guided_tour, log_imports_guided_event
from vendor_catalog_app.web.routers.imports.mappings import compatible_profiles, find_profile_by_id, load_mapping_profiles
from vendor_catalog_app.web.routers.imports.matching import build_preview_rows
from vendor_catalog_app.web.routers.imports.parsing import (
    apply_field_mapping,
    build_stage_area_rows,
    can_manage_imports,
    file_format_options,
    import_template_csv,
    layout_field_mapping_from_source_targets,
    layout_options,
    normalize_column_name,
    parse_layout_rows,
    resolve_field_mapping,
    resolve_source_target_mapping,
    safe_delimiter,
    safe_format_hint,
    safe_layout,
    safe_source_system,
    source_system_options,
    write_blocked,
)
from vendor_catalog_app.web.routers.imports.store import load_preview_payload
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter()

REVIEW_AREA_ORDER = (
    "vendor",
    "vendor_identifier",
    "vendor_owner",
    "vendor_contact",
    "offering",
    "offering_owner",
    "offering_contact",
    "contract",
    "project",
    "invoice",
    "payment",
)

REVIEW_AREA_LABELS = {
    "vendor": "Vendor",
    "vendor_identifier": "Vendor Identifier",
    "vendor_owner": "Vendor Owner",
    "vendor_contact": "Vendor Contact",
    "offering": "Offering",
    "offering_owner": "Offering Owner",
    "offering_contact": "Offering Contact",
    "contract": "Contract",
    "project": "Project",
    "invoice": "Invoice",
    "payment": "Payment",
}

LAYOUT_BY_REVIEW_AREA = {
    "vendor": "vendors",
    "offering": "offerings",
    "project": "projects",
    "invoice": "invoices",
    "payment": "payments",
}

AREAS_WITH_VENDOR_CONTEXT = {
    "vendor_identifier",
    "vendor_owner",
    "vendor_contact",
    "offering",
    "offering_owner",
    "offering_contact",
    "contract",
    "project",
    "invoice",
    "payment",
}

AREAS_WITH_OFFERING_CONTEXT = {
    "offering",
    "offering_owner",
    "offering_contact",
    "contract",
    "invoice",
    "payment",
}


def _imports_module():
    from vendor_catalog_app.web.routers import imports as imports_module

    return imports_module


def _profile_source_target_mapping(profile: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(profile, dict):
        return {}
    direct = {
        str(k): str(v)
        for k, v in dict(profile.get("source_target_mapping") or {}).items()
        if str(k).strip()
    }
    if direct:
        return direct
    legacy_target_to_source = dict(profile.get("field_mapping") or {})
    converted: dict[str, str] = {}
    for target_key, source_key in legacy_target_to_source.items():
        source = str(source_key or "").strip()
        target = str(target_key or "").strip()
        if source and source not in converted:
            converted[source] = target
    return converted


def _source_signature(source_fields: list[dict[str, Any]]) -> str:
    keys = [
        normalize_column_name(str(item.get("key") or "").replace(".", "_"))
        for item in list(source_fields or [])
        if str(item.get("key") or "").strip()
    ]
    canonical = "|".join(sorted(set([key for key in keys if key])))
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest() if canonical else ""


def _normalize_mapping(mapping: dict[str, str]) -> dict[str, str]:
    return {
        str(k): str(v)
        for k, v in dict(mapping or {}).items()
        if str(k).strip() and str(v).strip()
    }


def _source_target_mapping_from_form(form: Any) -> dict[str, str]:
    sources = [str(item or "").strip() for item in form.getlist("source_field_keys")]
    targets = [str(item or "").strip() for item in form.getlist("source_target_keys")]
    mapping: dict[str, str] = {}
    for index, source_key in enumerate(sources):
        if not source_key:
            continue
        target_key = str(targets[index] if index < len(targets) else "").strip()
        mapping[source_key] = target_key
    return mapping


def _resolve_user_principal(user) -> str:
    return str(getattr(user, "user_principal", "") or "").strip() or "system"


def _mapping_gate(
    repo,
    *,
    job: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, str, dict[str, Any] | None]:
    approval_status = str(context.get("mapping_approval_status") or "").strip().lower()
    request_status = str(context.get("mapping_request_status") or "").strip().lower()
    request_payload: dict[str, Any] | None = None
    mapping_request_id = str(job.get("mapping_request_id") or context.get("mapping_request_id") or "").strip()
    if mapping_request_id and hasattr(repo, "get_import_mapping_profile_request"):
        request_payload = repo.get_import_mapping_profile_request(mapping_request_id) or None
        if isinstance(request_payload, dict):
            request_status = str(request_payload.get("status") or "").strip().lower()

    profile_id = str(job.get("mapping_profile_id") or context.get("selected_mapping_profile_id") or "").strip()
    if request_status == "pending":
        return "pending", request_status, request_payload
    if request_status == "approved":
        return "approved", request_status, request_payload
    if profile_id:
        return "approved", request_status, request_payload
    if request_status == "rejected":
        return "rejected", request_status, request_payload
    if approval_status in {"approved", "pending", "rejected"}:
        return approval_status, request_status, request_payload
    return "required", request_status, request_payload


def _preview_summary(preview_rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for row in list(preview_rows or []):
        status = str(row.get("row_status") or "review").strip().lower()
        if status not in {"ready", "review", "blocked", "error"}:
            status = "review"
        counts[status] += 1
    return {
        "ready": int(counts.get("ready", 0)),
        "review": int(counts.get("review", 0)),
        "blocked": int(counts.get("blocked", 0)),
        "error": int(counts.get("error", 0)),
        "total": int(len(preview_rows or [])),
    }


def _status_for_row(*, errors: list[str], notes: list[str]) -> str:
    if errors:
        return "error"
    if notes:
        return "review"
    return "ready"


async def _event_payload(request: Request) -> dict[str, Any]:
    content_type = str(request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            payload = await request.json()
            if isinstance(payload, dict):
                return dict(payload)
        except Exception:
            return {}
    try:
        form = await request.form()
        return {str(key): value for key, value in form.items()}
    except Exception:
        return {}


async def _read_upload_bytes(upload: Any) -> bytes:
    if upload is None or not hasattr(upload, "read"):
        return b""
    return await upload.read()


def _extract_zip_members(raw_bytes: bytes) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not raw_bytes:
        return out
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                member_name = str(info.filename or "").strip()
                if not member_name:
                    continue
                member_bytes = archive.read(info)
                if not member_bytes:
                    continue
                out.append({"file_name": member_name.split("/")[-1], "raw_bytes": member_bytes})
    except Exception:
        return []
    return out


async def _collect_import_uploads(form: Any) -> list[dict[str, Any]]:
    uploads: list[dict[str, Any]] = []
    candidates: list[Any] = []
    primary = form.get("file")
    if primary is not None:
        candidates.append(primary)
    for item in form.getlist("files"):
        candidates.append(item)
    bundle_file = form.get("bundle_file")
    if bundle_file is not None:
        candidates.append(bundle_file)
    seen: set[str] = set()
    for upload in candidates:
        if upload is None or not hasattr(upload, "filename"):
            continue
        file_name = str(getattr(upload, "filename", "") or "").strip()
        if not file_name:
            continue
        raw_bytes = await _read_upload_bytes(upload)
        if not raw_bytes:
            continue
        lower_name = file_name.lower()
        if lower_name.endswith(".zip"):
            for member in _extract_zip_members(raw_bytes):
                member_name = str(member.get("file_name") or "").strip()
                dedupe = member_name.lower()
                if not member_name or dedupe in seen:
                    continue
                seen.add(dedupe)
                uploads.append(member)
            continue
        if lower_name in seen:
            continue
        seen.add(lower_name)
        uploads.append({"file_name": file_name, "raw_bytes": raw_bytes})
    return uploads


def _serialize_sample_rows(source_rows: list[dict[str, str]], *, limit: int = 5) -> list[dict[str, str]]:
    sample: list[dict[str, str]] = []
    for row in list(source_rows or [])[: max(1, int(limit or 5))]:
        sample.append({str(k): str(v or "") for k, v in dict(row).items() if not str(k).startswith("_")})
    return sample


def _stage_preview_rows(repo, *, import_job_id: str) -> list[dict[str, Any]]:
    rows = list(repo.list_import_stage_rows(import_job_id=import_job_id) or [])
    out: list[dict[str, Any]] = []
    for row in rows:
        area_key = str(row.get("area_key") or "").strip().lower()
        if area_key:
            continue
        payload = dict(row.get("row_payload") or {})
        out.append(
            {
                "import_stage_row_id": str(row.get("import_stage_row_id") or "").strip(),
                "row_index": int(row.get("row_index") or 0),
                "line_number": str(payload.get("line_number") or row.get("line_number") or "").strip(),
                "row_data": dict(payload.get("row_data") or {}),
                "row_status": str(payload.get("row_status") or "review").strip().lower(),
                "notes": list(payload.get("notes") or []),
                "errors": list(payload.get("errors") or []),
            }
        )
    out.sort(key=lambda item: int(item.get("row_index") or 0))
    return out


def _source_rows_from_stage(repo, *, import_job_id: str) -> list[dict[str, str]]:
    rows = list(repo.list_import_stage_rows(import_job_id=import_job_id) or [])
    out: list[dict[str, str]] = []
    for row in rows:
        area_key = str(row.get("area_key") or "").strip().lower()
        if area_key:
            continue
        payload = dict(row.get("row_payload") or {})
        source = dict(payload.get("source_row_raw") or {})
        if not source:
            source = dict(payload.get("row_data") or {})
        source["_line"] = str(payload.get("line_number") or row.get("line_number") or row.get("row_index") or "")
        out.append({str(k): str(v or "").strip() for k, v in source.items() if str(k).strip()})
    out.sort(key=lambda item: int(str(item.get("_line") or "0") or 0))
    return out


def _clean_area_payload(payload: dict[str, Any]) -> dict[str, str]:
    return {
        str(key): str(value or "").strip()
        for key, value in dict(payload or {}).items()
        if str(key).strip() and not str(key).startswith("__")
    }


def _lookup_offering_vendor_id(repo, *, offering_id: str) -> str:
    candidate = str(offering_id or "").strip()
    if not candidate or not hasattr(repo, "get_offerings_by_ids"):
        return ""
    try:
        rows = repo.get_offerings_by_ids([candidate])
    except Exception:
        return ""
    if rows.empty:
        return ""
    return str(rows.iloc[0].to_dict().get("vendor_id") or "").strip()


def _build_layout_area_review_rows(
    repo,
    *,
    area_key: str,
    stage_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    layout_key = str(LAYOUT_BY_REVIEW_AREA.get(area_key) or "").strip()
    if not layout_key:
        return []
    mapped_rows: list[dict[str, str]] = []
    source_rows: list[dict[str, str]] = []
    for row in stage_rows:
        payload = _clean_area_payload(dict(row.get("payload") or {}))
        line_number = str(row.get("line_number") or row.get("row_index") or "").strip()
        row_with_line = dict(payload)
        row_with_line["_line"] = line_number
        mapped_rows.append(row_with_line)
        source_rows.append(row_with_line)
    preview_rows = build_preview_rows(
        repo,
        layout_key,
        mapped_rows,
        source_rows=source_rows,
        source_target_mapping={},
        mapping_profile_id="",
        resolved_record_selector="",
    )
    out: list[dict[str, Any]] = []
    for index, preview in enumerate(preview_rows):
        source_meta = dict(stage_rows[index] if index < len(stage_rows) else {})
        payload = _clean_area_payload(dict(source_meta.get("payload") or {}))
        out.append(
            {
                "line_number": str(source_meta.get("line_number") or preview.get("line_number") or "").strip(),
                "source_group_key": str(source_meta.get("source_group_key") or "__static__"),
                "source_row_index": int(source_meta.get("row_index") or 0),
                "row_data": payload,
                "suggested_action": str(preview.get("suggested_action") or "new").strip().lower(),
                "suggested_target_id": str(preview.get("suggested_target_id") or "").strip(),
                "notes": list(preview.get("notes") or []),
                "errors": list(preview.get("errors") or []),
                "row_status": str(preview.get("row_status") or "review").strip().lower(),
                "merge_options": list(preview.get("merge_options") or []),
                "source_row_raw": dict(preview.get("source_row_raw") or payload),
                "unmapped_source_fields": dict(preview.get("unmapped_source_fields") or {}),
            }
        )
    return out


def _build_custom_area_review_rows(
    repo,
    *,
    area_key: str,
    stage_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in stage_rows:
        payload = _clean_area_payload(dict(row.get("payload") or {}))
        source_group_key = str(row.get("source_group_key") or "__static__")
        line_number = str(row.get("line_number") or row.get("row_index") or "").strip()
        source_row_index = int(row.get("row_index") or 0)
        errors: list[str] = []
        notes: list[str] = []
        merge_options: list[dict[str, str]] = []
        suggested_action = "new"
        suggested_target_id = ""

        if area_key == "vendor_identifier":
            vendor_id = str(payload.get("vendor_id") or "").strip()
            identifier_type = str(payload.get("identifier_type") or "").strip()
            identifier_value = str(payload.get("identifier_value") or "").strip()
            if not identifier_type or not identifier_value:
                errors.append("identifier_type and identifier_value are required.")
            if not vendor_id:
                notes.append("Select target vendor before apply.")
            if vendor_id:
                suggested_action = "merge"
                suggested_target_id = vendor_id
                merge_options.append({"id": vendor_id, "label": vendor_id})

        elif area_key == "vendor_owner":
            vendor_id = str(payload.get("vendor_id") or "").strip()
            owner_principal = str(payload.get("owner_user_principal") or "").strip()
            if not owner_principal:
                errors.append("owner_user_principal is required.")
            if not vendor_id:
                notes.append("Select target vendor before apply.")
            if vendor_id:
                suggested_action = "merge"
                suggested_target_id = vendor_id
                merge_options.append({"id": vendor_id, "label": vendor_id})

        elif area_key == "vendor_contact":
            vendor_id = str(payload.get("vendor_id") or "").strip()
            contact_name = str(payload.get("full_name") or "").strip()
            email = str(payload.get("email") or "").strip().lower()
            phone = "".join([ch for ch in str(payload.get("phone") or "") if ch.isdigit()])
            if not vendor_id:
                notes.append("Select target vendor before apply.")
            if not contact_name and not email and not phone:
                errors.append("full_name, email, or phone is required.")
            if vendor_id and hasattr(repo, "get_vendor_contacts"):
                try:
                    contacts = repo.get_vendor_contacts(vendor_id).to_dict("records")
                except Exception:
                    contacts = []
                for item in contacts[:25]:
                    option_id = str(item.get("vendor_contact_id") or "").strip()
                    label = str(item.get("full_name") or item.get("email") or option_id).strip()
                    if option_id:
                        merge_options.append({"id": option_id, "label": label})
                for item in contacts:
                    existing_email = str(item.get("email") or "").strip().lower()
                    existing_phone = "".join([ch for ch in str(item.get("phone") or "") if ch.isdigit()])
                    existing_name = str(item.get("full_name") or "").strip().lower()
                    if email and existing_email and email == existing_email:
                        suggested_action = "merge"
                        suggested_target_id = str(item.get("vendor_contact_id") or "").strip()
                        notes.append("Matched existing contact by email.")
                        break
                    if phone and existing_phone and phone[-7:] == existing_phone[-7:] and len(phone) >= 7 and len(existing_phone) >= 7:
                        suggested_action = "merge"
                        suggested_target_id = str(item.get("vendor_contact_id") or "").strip()
                        notes.append("Matched existing contact by phone.")
                        break
                    if contact_name and existing_name and contact_name.lower() == existing_name:
                        suggested_action = "merge"
                        suggested_target_id = str(item.get("vendor_contact_id") or "").strip()
                        notes.append("Matched existing contact by name.")
                        break

        elif area_key == "offering_owner":
            offering_id = str(payload.get("offering_id") or "").strip()
            vendor_id = str(payload.get("vendor_id") or "").strip() or _lookup_offering_vendor_id(repo, offering_id=offering_id)
            owner_principal = str(payload.get("owner_user_principal") or "").strip()
            if not owner_principal:
                errors.append("owner_user_principal is required.")
            if not offering_id:
                notes.append("Select target offering before apply.")
            if offering_id:
                suggested_action = "merge"
                suggested_target_id = offering_id
                merge_options.append({"id": offering_id, "label": offering_id})
            if vendor_id:
                payload["vendor_id"] = vendor_id

        elif area_key == "offering_contact":
            offering_id = str(payload.get("offering_id") or "").strip()
            vendor_id = str(payload.get("vendor_id") or "").strip() or _lookup_offering_vendor_id(repo, offering_id=offering_id)
            contact_name = str(payload.get("full_name") or "").strip()
            email = str(payload.get("email") or "").strip().lower()
            phone = "".join([ch for ch in str(payload.get("phone") or "") if ch.isdigit()])
            if not offering_id:
                notes.append("Select target offering before apply.")
            if not contact_name and not email and not phone:
                errors.append("full_name, email, or phone is required.")
            if vendor_id:
                payload["vendor_id"] = vendor_id

        elif area_key == "contract":
            contract_number = str(payload.get("contract_number") or "").strip()
            contract_id = str(payload.get("contract_id") or "").strip()
            offering_id = str(payload.get("offering_id") or "").strip()
            vendor_id = str(payload.get("vendor_id") or "").strip() or _lookup_offering_vendor_id(repo, offering_id=offering_id)
            if not contract_number and not contract_id:
                errors.append("contract_number or contract_id is required.")
            if not vendor_id:
                notes.append("Select or resolve vendor before apply.")
            if vendor_id:
                payload["vendor_id"] = vendor_id

        row_status = _status_for_row(errors=errors, notes=notes)
        out.append(
            {
                "line_number": line_number,
                "source_group_key": source_group_key,
                "source_row_index": source_row_index,
                "row_data": payload,
                "suggested_action": suggested_action,
                "suggested_target_id": suggested_target_id,
                "notes": notes,
                "errors": errors,
                "row_status": row_status,
                "merge_options": merge_options,
                "source_row_raw": dict(payload),
                "unmapped_source_fields": {},
            }
        )
    return out


def _build_review_rows_for_area(
    repo,
    *,
    area_key: str,
    stage_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if area_key in LAYOUT_BY_REVIEW_AREA:
        return _build_layout_area_review_rows(repo, area_key=area_key, stage_rows=stage_rows)
    return _build_custom_area_review_rows(repo, area_key=area_key, stage_rows=stage_rows)


def _materialize_review_rows(repo, *, import_job_id: str) -> dict[str, int]:
    current_rows = list(repo.list_import_stage_rows(import_job_id=import_job_id) or [])
    max_row_index = max([int(item.get("row_index") or 0) for item in current_rows], default=0)
    review_rows: list[dict[str, Any]] = []
    area_counts: dict[str, int] = {}
    for area_key in REVIEW_AREA_ORDER:
        stage_rows = list(repo.list_import_stage_area_rows(import_job_id=import_job_id, area_key=area_key) or [])
        if not stage_rows:
            area_counts[area_key] = 0
            continue
        built_rows = _build_review_rows_for_area(repo, area_key=area_key, stage_rows=stage_rows)
        for built in built_rows:
            max_row_index += 1
            review_rows.append(
                {
                    "row_index": max_row_index,
                    "line_number": str(built.get("line_number") or "").strip(),
                    "area_key": area_key,
                    "source_group_key": str(built.get("source_group_key") or "__static__"),
                    "row_data": dict(built.get("row_data") or {}),
                    "suggested_action": str(built.get("suggested_action") or "new").strip().lower(),
                    "suggested_target_id": str(built.get("suggested_target_id") or "").strip(),
                    "notes": list(built.get("notes") or []),
                    "errors": list(built.get("errors") or []),
                    "row_status": str(built.get("row_status") or "review").strip().lower(),
                    "merge_options": list(built.get("merge_options") or []),
                    "source_row_raw": dict(built.get("source_row_raw") or {}),
                    "unmapped_source_fields": dict(built.get("unmapped_source_fields") or {}),
                    "decision_payload": {
                        "source_row_index": int(built.get("source_row_index") or 0),
                        "source_group_key": str(built.get("source_group_key") or "__static__"),
                    },
                }
            )
        area_counts[area_key] = len(built_rows)
    repo.clear_import_stage_rows(import_job_id=import_job_id, exclude_area_keys=[""])
    if review_rows:
        repo.create_import_stage_rows(import_job_id=import_job_id, preview_rows=review_rows)
    return area_counts


def _area_states(repo, *, import_job_id: str) -> list[dict[str, Any]]:
    if not hasattr(repo, "list_import_review_area_states"):
        return []
    return list(repo.list_import_review_area_states(import_job_id=import_job_id) or [])


def _next_locked_area(area_states: list[dict[str, Any]]) -> str:
    for row in area_states:
        if str(row.get("status") or "").strip().lower() == "locked":
            return str(row.get("area_key") or "").strip().lower()
    return ""


def _current_area(area_states: list[dict[str, Any]]) -> str:
    for row in area_states:
        if str(row.get("status") or "").strip().lower() == "in_progress":
            return str(row.get("area_key") or "").strip().lower()
    for row in area_states:
        if str(row.get("status") or "").strip().lower() == "locked":
            return str(row.get("area_key") or "").strip().lower()
    return ""


def _area_status_map(area_states: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in area_states:
        out[str(row.get("area_key") or "").strip().lower()] = str(row.get("status") or "").strip().lower()
    return out


def _option_label_for_target(options: list[dict[str, Any]], target_id: str) -> str:
    target = str(target_id or "").strip()
    if not target:
        return ""
    for option in list(options or []):
        option_id = str(option.get("id") or "").strip()
        if option_id and option_id == target:
            return str(option.get("label") or option_id).strip() or option_id
    return target


def _review_area_context_defaults(*, area_key: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    show_vendor_selector = area_key in AREAS_WITH_VENDOR_CONTEXT
    show_offering_selector = area_key in AREAS_WITH_OFFERING_CONTEXT
    default_vendor_id = ""
    default_vendor_label = ""
    default_offering_id = ""
    default_offering_label = ""
    for row in list(rows or []):
        payload = dict(row.get("decision_payload") or {})
        if not default_vendor_id:
            default_vendor_id = str(payload.get("default_vendor_id") or "").strip()
            default_vendor_label = str(payload.get("default_vendor_label") or "").strip()
        if not default_offering_id:
            default_offering_id = str(payload.get("default_offering_id") or "").strip()
            default_offering_label = str(payload.get("default_offering_label") or "").strip()
        if default_vendor_id and default_offering_id:
            break
    if show_vendor_selector and not default_vendor_id:
        for row in list(rows or []):
            candidate = str(dict(row.get("row_data") or {}).get("vendor_id") or "").strip()
            if candidate:
                default_vendor_id = candidate
                default_vendor_label = candidate
                break
    if show_offering_selector and not default_offering_id:
        for row in list(rows or []):
            candidate = str(dict(row.get("row_data") or {}).get("offering_id") or "").strip()
            if candidate:
                default_offering_id = candidate
                default_offering_label = candidate
                break
    if default_vendor_id and not default_vendor_label:
        default_vendor_label = default_vendor_id
    if default_offering_id and not default_offering_label:
        default_offering_label = default_offering_id
    return {
        "show_vendor_selector": show_vendor_selector,
        "show_offering_selector": show_offering_selector,
        "default_vendor_id": default_vendor_id,
        "default_vendor_label": default_vendor_label,
        "default_offering_id": default_offering_id,
        "default_offering_label": default_offering_label,
    }


def _serialize_review_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in list(rows or []):
        payload = dict(row.get("row_payload") or {})
        row_data = dict(payload.get("row_data") or {})
        notes = list(payload.get("notes") or [])
        errors = list(payload.get("errors") or [])
        merge_options = list(payload.get("merge_options") or [])
        decision_payload = dict(row.get("decision_payload") or {})
        if not decision_payload:
            decision_payload = dict(payload.get("decision_payload") or {})
        source_row_index = int(decision_payload.get("source_row_index") or 0)
        source_group_key = str(row.get("source_group_key") or decision_payload.get("source_group_key") or "__static__")
        row_status = str(payload.get("row_status") or "review").strip().lower()
        if row_status not in {"ready", "review", "blocked", "error"}:
            row_status = "review"
        suggested_action = str(row.get("suggested_action") or payload.get("suggested_action") or "new").strip().lower()
        decision_action = str(row.get("decision_action") or "").strip().lower() or suggested_action or "new"
        suggested_target_id = str(row.get("suggested_target_id") or payload.get("suggested_target_id") or "").strip()
        decision_target_id = str(row.get("decision_target_id") or "").strip()
        suggested_target_label = _option_label_for_target(merge_options, suggested_target_id)
        decision_target_label = str(decision_payload.get("decision_target_label") or "").strip()
        if decision_target_id and not decision_target_label:
            decision_target_label = _option_label_for_target(merge_options, decision_target_id)
        out.append(
            {
                "import_stage_row_id": str(row.get("import_stage_row_id") or "").strip(),
                "row_index": int(row.get("row_index") or 0),
                "line_number": str(payload.get("line_number") or row.get("line_number") or "").strip(),
                "source_row_index": source_row_index,
                "source_group_key": source_group_key,
                "row_data": row_data,
                "notes": notes,
                "errors": errors,
                "row_status": row_status,
                "merge_options": merge_options,
                "suggested_action": suggested_action or "new",
                "suggested_target_id": suggested_target_id,
                "suggested_target_label": suggested_target_label,
                "decision_action": decision_action,
                "decision_target_id": decision_target_id,
                "decision_target_label": decision_target_label,
                "decision_payload": decision_payload,
            }
        )
    return out


def _save_area_decisions_from_form(repo, *, import_job_id: str, form: Any, actor_user_principal: str) -> int:
    decisions: list[dict[str, Any]] = []
    default_vendor_id = str(form.get("default_vendor_id") or "").strip()
    default_vendor_label = str(form.get("default_vendor_label") or "").strip()
    default_offering_id = str(form.get("default_offering_id") or "").strip()
    default_offering_label = str(form.get("default_offering_label") or "").strip()
    for row_id in form.getlist("row_ids"):
        stage_row_id = str(row_id or "").strip()
        if not stage_row_id:
            continue
        action = str(form.get(f"decision_action_{stage_row_id}") or "new").strip().lower()
        if action not in {"merge", "new", "skip"}:
            action = "new"
        target_id = str(form.get(f"decision_target_{stage_row_id}") or "").strip()
        target_label = str(form.get(f"decision_target_label_{stage_row_id}") or "").strip()
        source_row_index = int(str(form.get(f"source_row_index_{stage_row_id}") or "0").strip() or 0)
        source_group_key = str(form.get(f"source_group_key_{stage_row_id}") or "__static__").strip() or "__static__"
        decisions.append(
            {
                "import_stage_row_id": stage_row_id,
                "decision_action": action,
                "decision_target_id": target_id,
                "decision_payload": {
                    "source_row_index": source_row_index,
                    "source_group_key": source_group_key,
                    "default_vendor_id": default_vendor_id,
                    "default_vendor_label": default_vendor_label,
                    "default_offering_id": default_offering_id,
                    "default_offering_label": default_offering_label,
                    "decision_target_label": target_label,
                },
            }
        )
    if not decisions:
        return 0
    return int(
        repo.save_import_review_decisions(
            import_job_id=import_job_id,
            decisions=decisions,
            actor_user_principal=actor_user_principal,
        )
        or 0
    )


def _workflow_note(*, job: dict[str, Any], actor: str, message: str) -> str:
    source_system = str(job.get("source_system") or "").strip() or "unknown"
    source_object = str(job.get("source_object") or "").strip() or "-"
    return (
        f"job={str(job.get('import_job_id') or '').strip()} "
        f"source_system={source_system} source_object={source_object} actor={actor}; {message}"
    )


def _log_workflow_transition(
    repo,
    *,
    job: dict[str, Any],
    old_status: str,
    new_status: str,
    actor_user_principal: str,
    message: str,
) -> None:
    if not hasattr(repo, "log_import_workflow_event"):
        return
    try:
        repo.log_import_workflow_event(
            import_job_id=str(job.get("import_job_id") or "").strip(),
            old_status=str(old_status or "").strip(),
            new_status=str(new_status or "").strip(),
            actor_user_principal=actor_user_principal,
            notes=_workflow_note(job=job, actor=actor_user_principal, message=message),
        )
    except Exception:
        return


def _mapping_preview_context(
    *,
    repo,
    user,
    job: dict[str, Any],
) -> dict[str, Any]:
    context = dict(job.get("context") or {})
    source_fields = list(context.get("source_fields") or [])
    source_target_mapping = dict(context.get("source_target_mapping") or {})
    selected_layout = safe_layout(str(job.get("layout_key") or context.get("selected_layout") or "vendors"))
    effective_file_type = str(context.get("effective_file_type") or job.get("detected_format") or "").strip().lower()
    mapping_profiles = load_mapping_profiles(repo, user_principal=user.user_principal, layout_key=selected_layout)
    compatible = compatible_profiles(
        profiles=mapping_profiles,
        file_format=effective_file_type,
        source_fields=source_fields,
    )
    preview_rows = _stage_preview_rows(repo, import_job_id=str(job.get("import_job_id") or "").strip())
    mapping_gate_status, mapping_request_status, request_payload = _mapping_gate(repo, job=job, context=context)
    my_requests: list[dict[str, Any]] = []
    if hasattr(repo, "list_import_mapping_profile_requests"):
        my_requests = list(
            repo.list_import_mapping_profile_requests(
                submitted_by=user.user_principal,
                include_all=False,
                limit=50,
            )
            or []
        )
    return {
        "import_job_id": str(job.get("import_job_id") or "").strip(),
        "workflow_state": str(job.get("status") or "").strip().lower(),
        "selected_layout": selected_layout,
        "selected_source_system": safe_source_system(str(job.get("source_system") or "spreadsheet_manual")),
        "source_object": str(job.get("source_object") or "").strip(),
        "source_file_name": str(job.get("file_name") or "").strip(),
        "detected_file_type": str(job.get("detected_format") or "").strip(),
        "effective_file_type": effective_file_type,
        "parser_options": dict(context.get("parser_options") or {}),
        "parser_warnings": list(context.get("parser_warnings") or []),
        "source_fields": source_fields,
        "source_target_mapping": source_target_mapping,
        "sample_rows": list(context.get("sample_rows") or []),
        "target_field_groups": import_target_field_groups(dynamic_field_catalog=import_dynamic_field_catalog(repo)),
        "mapping_profiles": mapping_profiles,
        "compatible_profile_ids": {
            str(item.get("profile_id") or "").strip() for item in list(compatible or [])
        },
        "selected_mapping_profile_id": str(context.get("selected_mapping_profile_id") or job.get("mapping_profile_id") or "").strip(),
        "mapping_approval_status": mapping_gate_status,
        "mapping_request_status": mapping_request_status,
        "mapping_request_id": str(job.get("mapping_request_id") or context.get("mapping_request_id") or "").strip(),
        "active_mapping_request": request_payload if isinstance(request_payload, dict) else {},
        "preview_rows": list(preview_rows or [])[:IMPORT_PREVIEW_RENDER_LIMIT],
        "preview_summary": _preview_summary(preview_rows),
        "preview_total_rows": int(len(preview_rows or [])),
        "stage_area_counts": dict(context.get("stage_area_counts") or {}),
        "my_mapping_requests": my_requests,
    }


def _render_upload_page(
    request: Request,
    *,
    repo,
    user,
    selected_layout: str = "vendors",
) -> Response:
    mapping_profiles = load_mapping_profiles(repo, user_principal=user.user_principal, layout_key=selected_layout)
    my_requests: list[dict[str, Any]] = []
    if hasattr(repo, "list_import_mapping_profile_requests"):
        my_requests = list(
            repo.list_import_mapping_profile_requests(
                submitted_by=user.user_principal,
                include_all=False,
                limit=50,
            )
            or []
        )
    imports_module = _imports_module()
    context = imports_module.base_template_context(
        request,
        user,
        title="Data Imports",
        active_nav="imports",
        extra={
            "workflow_state": "uploaded",
            "layout_options": layout_options(),
            "source_system_options": source_system_options(),
            "file_format_options": file_format_options(),
            "selected_layout": selected_layout,
            "selected_source_system": "spreadsheet_manual",
            "source_object": "",
            "mapping_profiles": mapping_profiles,
            "selected_mapping_profile_id": "",
            "my_mapping_requests": my_requests,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "imports_v4_upload.html", context)


def _render_mapping_page(
    request: Request,
    *,
    repo,
    user,
    job: dict[str, Any],
) -> Response:
    payload = _mapping_preview_context(repo=repo, user=user, job=job)
    imports_module = _imports_module()
    context = imports_module.base_template_context(
        request,
        user,
        title="Data Imports - Map Columns",
        active_nav="imports",
        extra=payload,
    )
    return request.app.state.templates.TemplateResponse(request, "imports_v4_mapping.html", context)


def _render_review_page(
    request: Request,
    *,
    repo,
    user,
    job: dict[str, Any],
    area_key: str,
) -> Response:
    job_id = str(job.get("import_job_id") or "").strip()
    area_states = _area_states(repo, import_job_id=job_id)
    status_by_area = _area_status_map(area_states)
    current_area_key = _current_area(area_states) or area_key
    if status_by_area and status_by_area.get(area_key) == "locked":
        return RedirectResponse(url=f"/imports/jobs/{job_id}/review/{current_area_key}", status_code=303)
    rows_raw = list(repo.list_import_review_rows(import_job_id=job_id, area_key=area_key) or [])
    rows = _serialize_review_rows(rows_raw)
    area_context = _review_area_context_defaults(area_key=area_key, rows=rows)
    imports_module = _imports_module()
    context = imports_module.base_template_context(
        request,
        user,
        title=f"Data Imports - Review {REVIEW_AREA_LABELS.get(area_key, area_key.title())}",
        active_nav="imports",
        extra={
            "import_job_id": job_id,
            "workflow_state": str(job.get("status") or "").strip().lower(),
            "selected_layout": safe_layout(str(job.get("layout_key") or "vendors")),
            "current_area_key": area_key,
            "current_area_label": REVIEW_AREA_LABELS.get(area_key, area_key.title()),
            "review_area_order": REVIEW_AREA_ORDER,
            "review_area_labels": REVIEW_AREA_LABELS,
            "review_area_states": status_by_area,
            "next_locked_area_key": _next_locked_area(area_states),
            "area_rows": rows,
            "area_review_counts": {
                "total": len(rows),
                "ready": sum(1 for row in rows if str(row.get("row_status") or "") == "ready"),
                "review": sum(1 for row in rows if str(row.get("row_status") or "") == "review"),
                "error": sum(1 for row in rows if str(row.get("row_status") or "") == "error"),
            },
            "area_context": area_context,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "imports_v4_review_area.html", context)


def _render_final_page(
    request: Request,
    *,
    repo,
    user,
    job: dict[str, Any],
) -> Response:
    job_id = str(job.get("import_job_id") or "").strip()
    area_states = _area_states(repo, import_job_id=job_id)
    status_by_area = _area_status_map(area_states)
    area_rows: dict[str, list[dict[str, Any]]] = {}
    area_summaries: dict[str, dict[str, int]] = {}
    for area_key in REVIEW_AREA_ORDER:
        rows = _serialize_review_rows(
            list(repo.list_import_review_rows(import_job_id=job_id, area_key=area_key) or [])
        )
        area_rows[area_key] = rows
        counts = Counter()
        for row in rows:
            action = str(row.get("decision_action") or row.get("suggested_action") or "new").strip().lower()
            if action not in {"merge", "new", "skip"}:
                action = "new"
            counts[action] += 1
        area_summaries[area_key] = {
            "total": len(rows),
            "new": int(counts.get("new", 0)),
            "merge": int(counts.get("merge", 0)),
            "skip": int(counts.get("skip", 0)),
        }
    context_payload = dict(job.get("context") or {})
    apply_results = list(context_payload.get("apply_results") or [])
    imports_module = _imports_module()
    context = imports_module.base_template_context(
        request,
        user,
        title="Data Imports - Final Apply",
        active_nav="imports",
        extra={
            "import_job_id": job_id,
            "workflow_state": str(job.get("status") or "").strip().lower(),
            "selected_layout": safe_layout(str(job.get("layout_key") or "vendors")),
            "review_area_order": REVIEW_AREA_ORDER,
            "review_area_labels": REVIEW_AREA_LABELS,
            "review_area_states": status_by_area,
            "area_rows": area_rows,
            "area_summaries": area_summaries,
            "area_review_counts": {
                area_key: int(area_summaries.get(area_key, {}).get("total", 0))
                for area_key in REVIEW_AREA_ORDER
            },
            "next_locked_area_key": _next_locked_area(area_states),
            "mapping_approval_status": str(context_payload.get("mapping_approval_status") or ""),
            "mapping_request_status": str(context_payload.get("mapping_request_status") or ""),
            "apply_results": apply_results,
            "apply_totals": dict(context_payload.get("apply_totals") or {}),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "imports_v4_final.html", context)


def _coerce_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _resolve_stage_approval_or_message(
    repo,
    *,
    job: dict[str, Any],
    context: dict[str, Any],
) -> tuple[bool, str, str, str]:
    mapping_status, mapping_request_status, _request_payload = _mapping_gate(repo, job=job, context=context)
    if mapping_status == "approved":
        return True, mapping_status, mapping_request_status, ""
    if mapping_status == "pending":
        return (
            False,
            mapping_status,
            mapping_request_status,
            "Mapping request is pending admin approval. Stage and apply are blocked until approved.",
        )
    if mapping_status == "rejected":
        return (
            False,
            mapping_status,
            mapping_request_status,
            "Mapping request was rejected. Update mapping and submit a new request.",
        )
    return (
        False,
        mapping_status,
        mapping_request_status,
        "No approved mapping profile is linked to this import. Submit mapping for approval first.",
    )


@router.post("/imports/tour/dismiss")
@require_permission("import_preview")
async def imports_tour_dismiss(request: Request):
    imports_module = _imports_module()
    repo = imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    _ = await _event_payload(request)
    try:
        dismiss_imports_guided_tour(repo, user_principal=user.user_principal)
        return JSONResponse({"ok": True, "dismissed": True})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.post("/imports/ux/event")
@require_permission("import_preview")
async def imports_ux_event(request: Request):
    imports_module = _imports_module()
    repo = imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    payload = await _event_payload(request)
    event_type = str(payload.get("event_type") or "").strip()
    event_payload = payload.get("payload")
    if not isinstance(event_payload, dict):
        event_payload = {}
    log_imports_guided_event(
        repo,
        user_principal=user.user_principal,
        event_type=event_type,
        payload=event_payload,
    )
    return JSONResponse({"ok": True})


@router.get("/imports")
def imports_home(request: Request):
    imports_module = _imports_module()
    repo = imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    imports_module.log_page_view(request, user, "Imports")
    if not can_manage_imports(user):
        add_flash(request, "You do not have permission to access Imports.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)
    selected_layout = safe_layout(str(request.query_params.get("layout") or "vendors"))
    return _render_upload_page(request, repo=repo, user=user, selected_layout=selected_layout)


@router.get("/imports/templates/{layout_key}.csv")
def imports_template_download(layout_key: str):
    selected_layout = safe_layout(layout_key)
    filename, content = import_template_csv(selected_layout)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename=\"{filename}\"'},
    )


@router.post("/imports/preview")
@require_permission("import_preview")
async def imports_preview(request: Request):
    imports_module = _imports_module()
    repo = imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    imports_module.log_page_view(request, user, "Imports")
    if not can_manage_imports(user):
        add_flash(request, "You do not have permission to run imports.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)
    if write_blocked(user):
        add_flash(request, "Application is in locked mode. Import actions are disabled.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    form = await request.form()
    selected_layout = safe_layout(str(form.get("layout") or "vendors"))
    source_system_raw = str(form.get("source_system") or "").strip().lower()
    if source_system_raw not in set(IMPORT_SOURCE_SYSTEM_OPTIONS):
        add_flash(request, "Select a valid Source System before continuing.", "error")
        return RedirectResponse(url=f"/imports?layout={selected_layout}", status_code=303)
    source_system = safe_source_system(source_system_raw)
    source_object = str(form.get("source_object") or "").strip()
    selected_mapping_profile_id = str(form.get("mapping_profile_id") or "").strip()
    format_hint = safe_format_hint(str(form.get("format_hint") or "auto"))
    delimiter = safe_delimiter(str(form.get("delimiter") or ","))
    json_record_path = str(form.get("json_record_path") or "").strip()
    xml_record_path = str(form.get("xml_record_path") or "").strip()
    xml_record_tag = str(form.get("xml_record_tag") or "").strip()

    uploads = await _collect_import_uploads(form)
    if not uploads:
        add_flash(request, "Upload at least one file.", "error")
        return RedirectResponse(url=f"/imports?layout={selected_layout}", status_code=303)
    if len(uploads) > 1:
        add_flash(request, f"Processing {len(uploads)} file(s) in one import job.", "info")

    available_profiles = load_mapping_profiles(repo, user_principal=user.user_principal, layout_key=selected_layout)
    selected_profile = find_profile_by_id(available_profiles, selected_mapping_profile_id)
    requested_mapping: dict[str, str] = {}
    if selected_profile is not None:
        requested_mapping.update(_profile_source_target_mapping(selected_profile))
    requested_mapping.update(_source_target_mapping_from_form(form))
    dynamic_field_catalog = import_dynamic_field_catalog(repo)
    source_rows: list[dict[str, Any]] = []
    source_field_map: dict[str, dict[str, Any]] = {}
    resolved_source_target_mapping: dict[str, str] = {}
    mapped_rows: list[dict[str, Any]] = []
    stage_area_rows: dict[str, list[dict[str, Any]]] = {}
    parser_options: dict[str, Any] = {}
    parser_warnings: list[str] = []
    effective_formats: list[str] = []
    detected_formats: list[str] = []
    resolved_selectors: list[str] = []
    source_file_names: list[str] = []

    for file_index, upload in enumerate(uploads, start=1):
        source_file_name = str(upload.get("file_name") or "").strip()
        raw_bytes = bytes(upload.get("raw_bytes") or b"")
        if not source_file_name or not raw_bytes:
            continue
        try:
            parse_result = parse_layout_rows(
                selected_layout,
                raw_bytes,
                file_name=source_file_name,
                format_hint=format_hint,
                delimiter=delimiter,
                json_record_path=json_record_path,
                xml_record_path=xml_record_path,
                xml_record_tag=xml_record_tag,
                strict_layout=False,
                source_target_mapping=requested_mapping,
                dynamic_field_catalog=dynamic_field_catalog,
            )
        except Exception as exc:
            add_flash(request, f"Could not parse upload '{source_file_name}': {exc}", "error")
            return RedirectResponse(url=f"/imports?layout={selected_layout}", status_code=303)

        file_source_rows = list(parse_result.get("source_rows") or [])
        file_source_fields = list(parse_result.get("source_fields") or [])
        file_source_target_mapping = dict(parse_result.get("source_target_mapping") or {})
        file_mapped_rows = list(parse_result.get("rows") or [])
        file_stage_area_rows = {
            str(area): list(rows or [])
            for area, rows in dict(parse_result.get("stage_area_rows") or {}).items()
        }

        source_rows.extend(file_source_rows)
        mapped_rows.extend(file_mapped_rows)
        for source_key, target_key in file_source_target_mapping.items():
            normalized_source = str(source_key or "").strip()
            normalized_target = str(target_key or "").strip()
            if normalized_source and normalized_target and normalized_source not in resolved_source_target_mapping:
                resolved_source_target_mapping[normalized_source] = normalized_target

        for field in file_source_fields:
            key = str(field.get("key") or "").strip()
            if not key:
                continue
            existing = source_field_map.get(key)
            if existing is None:
                source_field_map[key] = dict(field)
                continue
            existing_samples = [
                str(value).strip()
                for value in list(existing.get("sample_values") or [])
                if str(value).strip()
            ]
            for candidate in list(field.get("sample_values") or []):
                normalized_candidate = str(candidate or "").strip()
                if not normalized_candidate or normalized_candidate in existing_samples:
                    continue
                if len(existing_samples) >= 3:
                    break
                existing_samples.append(normalized_candidate)
            existing["sample_values"] = existing_samples
            if not str(existing.get("sample_value") or "").strip():
                existing["sample_value"] = str(field.get("sample_value") or "").strip()
            existing["non_empty_count"] = int(existing.get("non_empty_count") or 0) + int(
                field.get("non_empty_count") or 0
            )

        group_prefix = f"file{file_index}"
        for area_key, rows in file_stage_area_rows.items():
            area_rows = stage_area_rows.setdefault(area_key, [])
            for row in rows:
                row_payload = dict(row)
                source_group_key = str(row_payload.get("source_group_key") or "__static__").strip() or "__static__"
                source_group_key = f"{group_prefix}:{source_group_key}"
                row_payload["source_group_key"] = source_group_key
                payload_data = dict(row_payload.get("payload") or {})
                payload_data["__source_group_key"] = source_group_key
                row_payload["payload"] = payload_data
                area_rows.append(row_payload)

        parser_options = dict(parse_result.get("parser_options") or parser_options)
        parser_warnings.extend([str(warning) for warning in list(parse_result.get("warnings") or []) if str(warning)])
        effective_formats.append(str(parse_result.get("effective_format") or "").strip().lower())
        detected_formats.append(str(parse_result.get("detected_format") or "").strip().lower())
        selector = str(parse_result.get("resolved_record_selector") or "").strip()
        if selector:
            resolved_selectors.append(selector)
        source_file_names.append(source_file_name)

    if not source_file_names:
        add_flash(request, "Uploaded file is empty.", "error")
        return RedirectResponse(url=f"/imports?layout={selected_layout}", status_code=303)

    source_fields = list(source_field_map.values())
    if not source_fields:
        keys: list[str] = []
        for row in source_rows:
            for key in row:
                key_name = str(key or "").strip()
                if not key_name or key_name.startswith("_"):
                    continue
                if key_name not in keys:
                    keys.append(key_name)
        source_fields = [{"key": key, "label": key, "normalized_key": normalize_column_name(key)} for key in keys]
    effective_file_type = (
        effective_formats[0]
        if len({value for value in effective_formats if value}) <= 1 and effective_formats
        else "mixed"
    )
    detected_file_type = (
        detected_formats[0]
        if len({value for value in detected_formats if value}) <= 1 and detected_formats
        else "mixed"
    )
    resolved_record_selector = ""
    if resolved_selectors:
        unique_selectors = sorted(set(resolved_selectors))
        resolved_record_selector = unique_selectors[0] if len(unique_selectors) == 1 else "multiple"
    source_file_name = (
        source_file_names[0]
        if len(source_file_names) == 1
        else f"{source_file_names[0]} (+{len(source_file_names) - 1} more)"
    )
    parser_options["file_count"] = len(source_file_names)

    preview_rows = build_preview_rows(
        repo,
        selected_layout,
        mapped_rows,
        source_rows=source_rows,
        source_target_mapping=resolved_source_target_mapping,
        mapping_profile_id=selected_mapping_profile_id,
        resolved_record_selector=resolved_record_selector,
    )

    actor = _resolve_user_principal(user)
    import_job_id = repo.create_import_stage_job(
        layout_key=selected_layout,
        source_system=source_system,
        source_object=source_object or None,
        file_name=source_file_name,
        file_type=str(source_file_name.rsplit(".", 1)[-1].lower() if "." in source_file_name else ""),
        detected_format=effective_file_type,
        parser_config=parser_options,
        row_count=len(preview_rows),
        actor_user_principal=actor,
    )
    repo.clear_import_stage_rows(import_job_id=import_job_id)
    repo.create_import_stage_rows(import_job_id=import_job_id, preview_rows=preview_rows)
    repo.clear_import_stage_area_rows(import_job_id=import_job_id)
    repo.create_import_stage_area_rows(import_job_id=import_job_id, stage_area_rows=stage_area_rows)

    mapping_approval_status = "approved" if selected_profile is not None else "required"
    if selected_profile is not None:
        repo.set_import_job_mapping_links(
            import_job_id=import_job_id,
            mapping_profile_id=selected_mapping_profile_id,
            mapping_request_id="",
            actor_user_principal=actor,
        )
    else:
        repo.set_import_job_mapping_links(
            import_job_id=import_job_id,
            mapping_profile_id="",
            mapping_request_id="",
            actor_user_principal=actor,
        )

    context_payload = {
        "selected_layout": selected_layout,
        "selected_source_system": source_system,
        "source_object": source_object,
        "source_file_name": source_file_name,
        "detected_file_type": detected_file_type,
        "effective_file_type": effective_file_type,
        "parser_options": parser_options,
        "parser_warnings": parser_warnings,
        "source_fields": source_fields,
        "source_target_mapping": resolved_source_target_mapping,
        "sample_rows": _serialize_sample_rows(source_rows, limit=5),
        "selected_mapping_profile_id": selected_mapping_profile_id,
        "resolved_record_selector": resolved_record_selector,
        "mapping_approval_status": mapping_approval_status,
        "mapping_request_status": "",
        "stage_area_counts": {key: len(value) for key, value in stage_area_rows.items()},
    }
    repo.update_import_job_context(
        import_job_id=import_job_id,
        context=context_payload,
        actor_user_principal=actor,
    )
    next_status = "ready_to_stage" if mapping_approval_status == "approved" else "mapping_preview"
    repo.update_import_job_status(
        import_job_id=import_job_id,
        status=next_status,
        actor_user_principal=actor,
    )
    job = repo.get_import_job(import_job_id) or {"import_job_id": import_job_id, "source_system": source_system, "source_object": source_object}
    _log_workflow_transition(
        repo,
        job=job,
        old_status="uploaded",
        new_status=next_status,
        actor_user_principal=actor,
        message="preview created",
    )
    return RedirectResponse(url=f"/imports/jobs/{import_job_id}/mapping", status_code=303)


def _mapping_page_guard(repo, *, request: Request, import_job_id: str):
    job = repo.get_import_job(import_job_id)
    if job is None:
        add_flash(request, "Import job was not found.", "error")
        return None, RedirectResponse(url="/imports", status_code=303)
    return job, None


@router.get("/imports/jobs/{job_id}/mapping")
@require_permission("import_preview")
async def imports_job_mapping(request: Request, job_id: str):
    imports_module = _imports_module()
    repo = imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    imports_module.log_page_view(request, user, "Imports")
    job, redirect = _mapping_page_guard(repo, request=request, import_job_id=job_id)
    if redirect is not None:
        return redirect
    return _render_mapping_page(request, repo=repo, user=user, job=job)


@router.post("/imports/jobs/{job_id}/mapping/rebuild")
@require_permission("import_preview")
async def imports_job_mapping_rebuild(request: Request, job_id: str):
    imports_module = _imports_module()
    repo = imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    imports_module.log_page_view(request, user, "Imports")
    if write_blocked(user):
        add_flash(request, "Application is in locked mode. Import actions are disabled.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)
    job, redirect = _mapping_page_guard(repo, request=request, import_job_id=job_id)
    if redirect is not None:
        return redirect

    workflow_state = str(job.get("status") or "").strip().lower()
    if workflow_state in {"staged", "review_in_progress", "ready_to_apply", "applied", "applied_with_errors"}:
        add_flash(request, "Mapping cannot be rebuilt after staging has started.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)

    form = await request.form()
    selected_layout = safe_layout(str(job.get("layout_key") or "vendors"))
    source_rows = _source_rows_from_stage(repo, import_job_id=job_id)
    if not source_rows:
        add_flash(request, "Source rows are unavailable for rebuild. Upload again.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    context_payload = dict(job.get("context") or {})
    source_fields = list(context_payload.get("source_fields") or [])
    if not source_fields:
        keys: list[str] = []
        for row in source_rows:
            for key in row:
                if key.startswith("_"):
                    continue
                if key not in keys:
                    keys.append(key)
        source_fields = [{"key": key, "label": key, "normalized_key": normalize_column_name(key)} for key in keys]

    available_profiles = load_mapping_profiles(repo, user_principal=user.user_principal, layout_key=selected_layout)
    selected_mapping_profile_id = str(form.get("mapping_profile_id") or context_payload.get("selected_mapping_profile_id") or "").strip()
    selected_profile = find_profile_by_id(available_profiles, selected_mapping_profile_id)
    requested_mapping: dict[str, str] = {}
    normalized_profile_mapping: dict[str, str] = {}
    if selected_profile is not None:
        normalized_profile_mapping = _normalize_mapping(_profile_source_target_mapping(selected_profile))
        requested_mapping.update(_profile_source_target_mapping(selected_profile))
    requested_mapping.update(_source_target_mapping_from_form(form))
    resolved_source_target_mapping = resolve_source_target_mapping(
        source_fields=source_fields,
        requested_mapping=requested_mapping,
        dynamic_field_catalog=import_dynamic_field_catalog(repo),
    )
    resolved_layout_mapping = layout_field_mapping_from_source_targets(
        layout_key=selected_layout,
        source_target_mapping=resolved_source_target_mapping,
    )
    resolved_layout_mapping = resolve_field_mapping(
        allowed_fields=[str(field) for field in IMPORT_LAYOUTS.get(selected_layout, {}).get("fields", [])],
        source_fields=source_fields,
        requested_mapping=resolved_layout_mapping,
    )
    mapped_rows = apply_field_mapping(
        source_rows=source_rows,
        allowed_fields=[str(field) for field in IMPORT_LAYOUTS.get(selected_layout, {}).get("fields", [])],
        field_mapping=resolved_layout_mapping,
    )
    stage_area_rows = build_stage_area_rows(
        source_rows=source_rows,
        source_target_mapping=resolved_source_target_mapping,
    )
    preview_rows = build_preview_rows(
        repo,
        selected_layout,
        mapped_rows,
        source_rows=source_rows,
        source_target_mapping=resolved_source_target_mapping,
        mapping_profile_id=selected_mapping_profile_id,
        resolved_record_selector=str(context_payload.get("resolved_record_selector") or ""),
    )

    repo.clear_import_stage_rows(import_job_id=job_id)
    repo.create_import_stage_rows(import_job_id=job_id, preview_rows=preview_rows)
    repo.clear_import_stage_area_rows(import_job_id=job_id)
    repo.create_import_stage_area_rows(import_job_id=job_id, stage_area_rows=stage_area_rows)

    normalized_requested = _normalize_mapping(dict(requested_mapping or {}))
    mapping_approval_status = "required"
    if selected_profile is not None and normalized_requested == normalized_profile_mapping:
        mapping_approval_status = "approved"
    if mapping_approval_status == "approved":
        repo.set_import_job_mapping_links(
            import_job_id=job_id,
            mapping_profile_id=selected_mapping_profile_id,
            mapping_request_id="",
            actor_user_principal=_resolve_user_principal(user),
        )
    else:
        repo.set_import_job_mapping_links(
            import_job_id=job_id,
            mapping_profile_id="",
            mapping_request_id="",
            actor_user_principal=_resolve_user_principal(user),
        )
    context_payload.update(
        {
            "source_fields": source_fields,
            "source_target_mapping": resolved_source_target_mapping,
            "sample_rows": _serialize_sample_rows(source_rows, limit=5),
            "selected_mapping_profile_id": selected_mapping_profile_id,
            "mapping_approval_status": mapping_approval_status,
            "mapping_request_status": "",
            "stage_area_counts": {key: len(value) for key, value in stage_area_rows.items()},
        }
    )
    repo.update_import_job_context(
        import_job_id=job_id,
        context=context_payload,
        actor_user_principal=_resolve_user_principal(user),
    )
    repo.update_import_job_status(
        import_job_id=job_id,
        status="ready_to_stage" if mapping_approval_status == "approved" else "mapping_preview",
        actor_user_principal=_resolve_user_principal(user),
    )
    add_flash(request, "Mapping preview updated.", "success")
    return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)


@router.post("/imports/jobs/{job_id}/mapping/submit")
@require_permission("import_preview")
async def imports_job_mapping_submit(request: Request, job_id: str):
    imports_module = _imports_module()
    repo = imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    imports_module.log_page_view(request, user, "Imports")
    if write_blocked(user):
        add_flash(request, "Application is in locked mode. Import actions are disabled.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)
    if not hasattr(repo, "create_import_mapping_profile_request"):
        add_flash(request, "Mapping request queue is not available in this environment.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)
    job = repo.get_import_job(job_id)
    if job is None:
        add_flash(request, "Import job was not found.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    form = await request.form()
    proposed_profile_name = str(form.get("proposed_profile_name") or "").strip()
    if not proposed_profile_name:
        add_flash(request, "Mapping profile name is required for approval submission.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)

    context_payload = dict(job.get("context") or {})
    source_fields = list(context_payload.get("source_fields") or [])
    source_target_mapping = dict(context_payload.get("source_target_mapping") or {})
    parser_options = dict(context_payload.get("parser_options") or {})
    sample_rows = list(context_payload.get("sample_rows") or [])
    file_format = str(context_payload.get("effective_file_type") or job.get("detected_format") or "").strip().lower()
    source_signature = _source_signature(source_fields)
    actor = _resolve_user_principal(user)
    request_id = repo.create_import_mapping_profile_request(
        import_job_id=job_id,
        submitted_by=actor,
        layout_key=str(job.get("layout_key") or "vendors"),
        proposed_profile_name=proposed_profile_name,
        file_format=file_format,
        source_system=str(job.get("source_system") or "").strip(),
        source_object=str(job.get("source_object") or "").strip(),
        source_signature=source_signature,
        source_fields=source_fields,
        source_target_mapping=source_target_mapping,
        parser_options=parser_options,
        sample_rows=sample_rows,
    )
    if not request_id:
        add_flash(request, "Could not submit mapping request.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)

    repo.set_import_job_mapping_links(
        import_job_id=job_id,
        mapping_profile_id="",
        mapping_request_id=request_id,
        actor_user_principal=actor,
    )
    old_status = str(job.get("status") or "").strip().lower()
    repo.update_import_job_status(
        import_job_id=job_id,
        status="mapping_pending_approval",
        actor_user_principal=actor,
    )
    context_payload.update(
        {
            "mapping_approval_status": "pending",
            "mapping_request_status": "pending",
            "mapping_request_id": request_id,
            "proposed_profile_name": proposed_profile_name,
        }
    )
    repo.update_import_job_context(
        import_job_id=job_id,
        context=context_payload,
        actor_user_principal=actor,
    )
    refreshed_job = repo.get_import_job(job_id) or job
    _log_workflow_transition(
        repo,
        job=refreshed_job,
        old_status=old_status,
        new_status="mapping_pending_approval",
        actor_user_principal=actor,
        message=f"mapping submitted for approval ({request_id})",
    )
    add_flash(request, "Mapping submitted for admin approval.", "success")
    return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)


@router.post("/imports/jobs/{job_id}/stage")
@require_permission("import_preview")
async def imports_job_stage(request: Request, job_id: str):
    imports_module = _imports_module()
    repo = imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    imports_module.log_page_view(request, user, "Imports")
    if write_blocked(user):
        add_flash(request, "Application is in locked mode. Import actions are disabled.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)
    job = repo.get_import_job(job_id)
    if job is None:
        add_flash(request, "Import job was not found.", "error")
        return RedirectResponse(url="/imports", status_code=303)
    context_payload = dict(job.get("context") or {})
    allowed, mapping_status, mapping_request_status, blocked_message = _resolve_stage_approval_or_message(
        repo,
        job=job,
        context=context_payload,
    )
    if not allowed:
        add_flash(request, blocked_message, "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)

    area_counts = _materialize_review_rows(repo, import_job_id=job_id)
    if hasattr(repo, "initialize_import_review_area_states"):
        repo.initialize_import_review_area_states(
            import_job_id=job_id,
            actor_user_principal=_resolve_user_principal(user),
        )
    old_status = str(job.get("status") or "").strip().lower()
    repo.update_import_job_status(
        import_job_id=job_id,
        status="review_in_progress",
        actor_user_principal=_resolve_user_principal(user),
    )
    context_payload.update(
        {
            "mapping_approval_status": mapping_status,
            "mapping_request_status": mapping_request_status,
            "area_review_counts": area_counts,
            "current_area_key": REVIEW_AREA_ORDER[0],
            "next_locked_area_key": REVIEW_AREA_ORDER[1] if len(REVIEW_AREA_ORDER) > 1 else "",
        }
    )
    repo.update_import_job_context(
        import_job_id=job_id,
        context=context_payload,
        actor_user_principal=_resolve_user_principal(user),
    )
    refreshed_job = repo.get_import_job(job_id) or job
    _log_workflow_transition(
        repo,
        job=refreshed_job,
        old_status=old_status,
        new_status="review_in_progress",
        actor_user_principal=_resolve_user_principal(user),
        message="rows staged for sequential area review",
    )
    add_flash(request, "Rows staged. Review areas in sequence before final apply.", "success")
    return RedirectResponse(url=f"/imports/jobs/{job_id}/review/{REVIEW_AREA_ORDER[0]}", status_code=303)


@router.get("/imports/jobs/{job_id}/review/{area_key}")
@require_permission("import_preview")
async def imports_job_review_area(request: Request, job_id: str, area_key: str):
    imports_module = _imports_module()
    repo = imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    imports_module.log_page_view(request, user, "Imports")
    normalized_area = str(area_key or "").strip().lower()
    if normalized_area not in set(REVIEW_AREA_ORDER):
        add_flash(request, "Unknown review area.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)
    job = repo.get_import_job(job_id)
    if job is None:
        add_flash(request, "Import job was not found.", "error")
        return RedirectResponse(url="/imports", status_code=303)
    return _render_review_page(request, repo=repo, user=user, job=job, area_key=normalized_area)


@router.post("/imports/jobs/{job_id}/review/{area_key}/save")
@require_permission("import_preview")
async def imports_job_review_area_save(request: Request, job_id: str, area_key: str):
    imports_module = _imports_module()
    repo = imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    imports_module.log_page_view(request, user, "Imports")
    if write_blocked(user):
        add_flash(request, "Application is in locked mode. Import actions are disabled.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/review/{area_key}", status_code=303)
    normalized_area = str(area_key or "").strip().lower()
    if normalized_area not in set(REVIEW_AREA_ORDER):
        add_flash(request, "Unknown review area.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)
    form = await request.form()
    saved_count = _save_area_decisions_from_form(
        repo,
        import_job_id=job_id,
        form=form,
        actor_user_principal=_resolve_user_principal(user),
    )
    add_flash(request, f"Saved {saved_count} decision(s).", "success")
    return RedirectResponse(url=f"/imports/jobs/{job_id}/review/{normalized_area}", status_code=303)


@router.post("/imports/jobs/{job_id}/review/{area_key}/confirm")
@require_permission("import_preview")
async def imports_job_review_area_confirm(request: Request, job_id: str, area_key: str):
    imports_module = _imports_module()
    repo = imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    imports_module.log_page_view(request, user, "Imports")
    if write_blocked(user):
        add_flash(request, "Application is in locked mode. Import actions are disabled.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/review/{area_key}", status_code=303)
    normalized_area = str(area_key or "").strip().lower()
    if normalized_area not in set(REVIEW_AREA_ORDER):
        add_flash(request, "Unknown review area.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)
    job = repo.get_import_job(job_id)
    if job is None:
        add_flash(request, "Import job was not found.", "error")
        return RedirectResponse(url="/imports", status_code=303)
    form = await request.form()
    _save_area_decisions_from_form(
        repo,
        import_job_id=job_id,
        form=form,
        actor_user_principal=_resolve_user_principal(user),
    )
    confirmed_rows = _serialize_review_rows(
        list(repo.list_import_review_rows(import_job_id=job_id, area_key=normalized_area) or [])
    )
    missing_merge_targets = [
        row
        for row in confirmed_rows
        if str(row.get("decision_action") or "").strip().lower() == "merge"
        and not _merge_target_present(area_key=normalized_area, row=row)
    ]
    if missing_merge_targets:
        add_flash(
            request,
            "One or more merge rows are missing a selected target. Select targets before confirming this area.",
            "error",
        )
        return RedirectResponse(url=f"/imports/jobs/{job_id}/review/{normalized_area}", status_code=303)
    try:
        result = repo.confirm_import_review_area(
            import_job_id=job_id,
            area_key=normalized_area,
            actor_user_principal=_resolve_user_principal(user),
        )
    except Exception as exc:
        add_flash(request, f"Could not confirm area: {exc}", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/review/{normalized_area}", status_code=303)
    old_status = str(job.get("status") or "").strip().lower()
    next_area = str(result.get("next_area_key") or "").strip().lower()
    repo.update_import_job_status(
        import_job_id=job_id,
        status="review_in_progress" if next_area else "ready_to_apply",
        actor_user_principal=_resolve_user_principal(user),
    )
    refreshed_job = repo.get_import_job(job_id) or job
    _log_workflow_transition(
        repo,
        job=refreshed_job,
        old_status=old_status,
        new_status=str(refreshed_job.get("status") or "").strip().lower(),
        actor_user_principal=_resolve_user_principal(user),
        message=f"review area confirmed ({normalized_area})",
    )
    add_flash(request, f"Confirmed {REVIEW_AREA_LABELS.get(normalized_area, normalized_area.title())}.", "success")
    if next_area:
        return RedirectResponse(url=f"/imports/jobs/{job_id}/review/{next_area}", status_code=303)
    return RedirectResponse(url=f"/imports/jobs/{job_id}/final", status_code=303)


@router.get("/imports/jobs/{job_id}/final")
@require_permission("import_preview")
async def imports_job_final(request: Request, job_id: str):
    imports_module = _imports_module()
    repo = imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    imports_module.log_page_view(request, user, "Imports")
    job = repo.get_import_job(job_id)
    if job is None:
        add_flash(request, "Import job was not found.", "error")
        return RedirectResponse(url="/imports", status_code=303)
    return _render_final_page(request, repo=repo, user=user, job=job)


def _match_reason_required(repo, *, import_job_id: str) -> bool:
    for area_key in REVIEW_AREA_ORDER:
        rows = list(repo.list_import_review_rows(import_job_id=import_job_id, area_key=area_key) or [])
        for row in rows:
            action = str(row.get("decision_action") or row.get("suggested_action") or "").strip().lower()
            if action == "merge":
                return True
    return False


def _merge_target_present(*, area_key: str, row: dict[str, Any]) -> bool:
    target_id = str(row.get("decision_target_id") or "").strip()
    if target_id:
        return True
    payload = dict(row.get("decision_payload") or {})
    default_vendor_id = str(payload.get("default_vendor_id") or "").strip()
    default_offering_id = str(payload.get("default_offering_id") or "").strip()
    if area_key in {"vendor", "vendor_identifier", "vendor_owner"} and default_vendor_id:
        return True
    if area_key == "offering" and default_offering_id:
        return True
    return False


def _resolve_parent_id(
    *,
    cache: dict[tuple[int, str], str],
    source_row_index: int,
    source_group_key: str,
    explicit_value: str,
) -> str:
    explicit = str(explicit_value or "").strip()
    if explicit:
        return explicit
    direct = str(cache.get((source_row_index, source_group_key)) or "").strip()
    if direct:
        return direct
    for (row_index, _group), value in cache.items():
        if int(row_index) == int(source_row_index):
            candidate = str(value or "").strip()
            if candidate:
                return candidate
    return ""


def _apply_area_row(
    repo,
    *,
    area_key: str,
    row: dict[str, Any],
    actor_user_principal: str,
    reason: str,
    vendor_cache: dict[tuple[int, str], str],
    offering_cache: dict[tuple[int, str], str],
) -> tuple[str, str, dict[str, str]]:
    payload = dict(row.get("row_data") or {})
    decision_payload = dict(row.get("decision_payload") or {})
    action = str(row.get("decision_action") or row.get("suggested_action") or "new").strip().lower()
    target_id = str(row.get("decision_target_id") or row.get("suggested_target_id") or "").strip()
    source_row_index = int(row.get("source_row_index") or 0)
    source_group_key = str(row.get("source_group_key") or "__static__")
    default_vendor_id = str(decision_payload.get("default_vendor_id") or "").strip()
    default_offering_id = str(decision_payload.get("default_offering_id") or "").strip()
    key = (source_row_index, source_group_key)

    if action == "skip":
        return "skipped", "Skipped by reviewer decision.", {}

    if area_key == "vendor":
        legal_name = str(payload.get("legal_name") or "").strip()
        if action == "new":
            if not legal_name:
                raise ValueError("legal_name is required for new vendor rows.")
            vendor_id = repo.create_vendor_profile(
                actor_user_principal=actor_user_principal,
                legal_name=legal_name,
                display_name=str(payload.get("display_name") or "").strip() or None,
                lifecycle_state=str(payload.get("lifecycle_state") or "").strip() or "draft",
                owner_org_id=str(payload.get("owner_org_id") or "").strip() or None,
                risk_tier=str(payload.get("risk_tier") or "").strip() or None,
                source_system=str(payload.get("source_system") or "manual").strip() or "manual",
            )
            vendor_cache[key] = str(vendor_id or "").strip()
            return "created", f"Vendor created ({vendor_id}).", {"vendor_id": str(vendor_id or "").strip()}
        if not target_id and default_vendor_id:
            target_id = default_vendor_id
        if not target_id:
            raise ValueError("Target vendor is required for merge.")
        updates = {
            field: str(payload.get(field) or "").strip()
            for field in ("legal_name", "display_name", "lifecycle_state", "owner_org_id", "risk_tier")
            if str(payload.get(field) or "").strip()
        }
        if updates:
            repo.apply_vendor_profile_update(
                vendor_id=target_id,
                actor_user_principal=actor_user_principal,
                updates=updates,
                reason=reason,
            )
        vendor_cache[key] = target_id
        return "merged", f"Vendor merged into {target_id}.", {"vendor_id": target_id}

    if area_key == "vendor_identifier":
        vendor_id = _resolve_parent_id(
            cache=vendor_cache,
            source_row_index=source_row_index,
            source_group_key=source_group_key,
            explicit_value=str(payload.get("vendor_id") or target_id or default_vendor_id),
        )
        if not vendor_id:
            raise ValueError("Vendor target is required for vendor identifier row.")
        identifier_type = str(payload.get("identifier_type") or "").strip()
        identifier_value = str(payload.get("identifier_value") or "").strip()
        if not identifier_type or not identifier_value:
            raise ValueError("identifier_type and identifier_value are required.")
        identifier_id = repo.upsert_vendor_identifier(
            vendor_id=vendor_id,
            identifier_type=identifier_type,
            identifier_value=identifier_value,
            is_primary=_coerce_bool(payload.get("is_primary")),
            country_code=str(payload.get("country_code") or "").strip() or None,
            actor_user_principal=actor_user_principal,
        )
        return (
            "merged" if action == "merge" else "created",
            f"Vendor identifier upserted ({identifier_id}).",
            {"vendor_id": vendor_id},
        )

    if area_key == "vendor_owner":
        vendor_id = _resolve_parent_id(
            cache=vendor_cache,
            source_row_index=source_row_index,
            source_group_key=source_group_key,
            explicit_value=str(payload.get("vendor_id") or target_id or default_vendor_id),
        )
        if not vendor_id:
            raise ValueError("Vendor target is required for vendor owner row.")
        owner_user_principal = str(payload.get("owner_user_principal") or "").strip()
        owner_role = str(payload.get("owner_role") or "business_owner").strip() or "business_owner"
        if not owner_user_principal:
            raise ValueError("owner_user_principal is required.")
        owner_id = repo.upsert_vendor_owner(
            vendor_id=vendor_id,
            owner_user_principal=owner_user_principal,
            owner_role=owner_role,
            actor_user_principal=actor_user_principal,
        )
        return (
            "merged" if action == "merge" else "created",
            f"Vendor owner upserted ({owner_id}).",
            {"vendor_id": vendor_id},
        )

    if area_key == "vendor_contact":
        vendor_id = _resolve_parent_id(
            cache=vendor_cache,
            source_row_index=source_row_index,
            source_group_key=source_group_key,
            explicit_value=str(payload.get("vendor_id") or default_vendor_id),
        )
        if not vendor_id:
            raise ValueError("Vendor target is required for vendor contact row.")
        updates = {
            "contact_type": str(payload.get("contact_type") or "business").strip() or "business",
            "full_name": str(payload.get("full_name") or "").strip(),
            "email": str(payload.get("email") or "").strip(),
            "phone": str(payload.get("phone") or "").strip(),
        }
        if action == "merge" and target_id and hasattr(repo, "update_vendor_contact"):
            repo.update_vendor_contact(
                vendor_id=vendor_id,
                vendor_contact_id=target_id,
                updates=updates,
                actor_user_principal=actor_user_principal,
                reason=reason,
            )
            return "merged", f"Vendor contact merged ({target_id}).", {"vendor_id": vendor_id}
        contact_id = repo.add_vendor_contact(
            vendor_id=vendor_id,
            full_name=updates["full_name"] or updates["email"] or "Imported Contact",
            contact_type=updates["contact_type"],
            email=updates["email"] or None,
            phone=updates["phone"] or None,
            actor_user_principal=actor_user_principal,
        )
        return "created", f"Vendor contact added ({contact_id}).", {"vendor_id": vendor_id}

    if area_key == "offering":
        vendor_id = _resolve_parent_id(
            cache=vendor_cache,
            source_row_index=source_row_index,
            source_group_key=source_group_key,
            explicit_value=str(payload.get("vendor_id") or default_vendor_id),
        )
        if action == "new":
            offering_name = str(payload.get("offering_name") or "").strip()
            if not vendor_id:
                raise ValueError("vendor_id is required for new offering rows.")
            if not offering_name:
                raise ValueError("offering_name is required for new offering rows.")
            offering_id = repo.create_offering(
                vendor_id=vendor_id,
                actor_user_principal=actor_user_principal,
                offering_name=offering_name,
                offering_type=str(payload.get("offering_type") or "").strip() or None,
                business_unit=str(payload.get("business_unit") or "").strip() or None,
                service_type=str(payload.get("service_type") or "").strip() or None,
                lifecycle_state=str(payload.get("lifecycle_state") or "").strip() or "draft",
                criticality_tier=str(payload.get("criticality_tier") or "").strip() or None,
            )
            offering_cache[key] = str(offering_id or "").strip()
            return "created", f"Offering created ({offering_id}).", {"vendor_id": vendor_id, "offering_id": str(offering_id or "").strip()}
        if not target_id and default_offering_id:
            target_id = default_offering_id
        if not target_id:
            raise ValueError("Target offering is required for merge.")
        resolved_vendor_id = vendor_id or _lookup_offering_vendor_id(repo, offering_id=target_id)
        updates = {
            field: str(payload.get(field) or "").strip()
            for field in ("offering_name", "offering_type", "business_unit", "service_type", "lifecycle_state", "criticality_tier")
            if str(payload.get(field) or "").strip()
        }
        if updates:
            repo.update_offering_fields(
                vendor_id=resolved_vendor_id,
                offering_id=target_id,
                actor_user_principal=actor_user_principal,
                updates=updates,
                reason=reason,
            )
        offering_cache[key] = target_id
        if resolved_vendor_id:
            vendor_cache[key] = resolved_vendor_id
        return "merged", f"Offering merged into {target_id}.", {"vendor_id": resolved_vendor_id, "offering_id": target_id}

    if area_key == "offering_owner":
        offering_id = _resolve_parent_id(
            cache=offering_cache,
            source_row_index=source_row_index,
            source_group_key=source_group_key,
            explicit_value=str(payload.get("offering_id") or default_offering_id or target_id),
        )
        if not offering_id:
            raise ValueError("Offering target is required for offering owner row.")
        vendor_id = _resolve_parent_id(
            cache=vendor_cache,
            source_row_index=source_row_index,
            source_group_key=source_group_key,
            explicit_value=str(
                payload.get("vendor_id")
                or default_vendor_id
                or _lookup_offering_vendor_id(repo, offering_id=offering_id)
            ),
        )
        owner_user_principal = str(payload.get("owner_user_principal") or "").strip()
        owner_role = str(payload.get("owner_role") or "business_owner").strip() or "business_owner"
        if not vendor_id:
            raise ValueError("Vendor target is required for offering owner row.")
        if not owner_user_principal:
            raise ValueError("owner_user_principal is required.")
        owner_id = repo.upsert_offering_owner(
            vendor_id=vendor_id,
            offering_id=offering_id,
            owner_user_principal=owner_user_principal,
            owner_role=owner_role,
            actor_user_principal=actor_user_principal,
        )
        return (
            "merged" if action == "merge" else "created",
            f"Offering owner upserted ({owner_id}).",
            {"vendor_id": vendor_id, "offering_id": offering_id},
        )

    if area_key == "offering_contact":
        offering_id = _resolve_parent_id(
            cache=offering_cache,
            source_row_index=source_row_index,
            source_group_key=source_group_key,
            explicit_value=str(payload.get("offering_id") or default_offering_id),
        )
        if not offering_id:
            raise ValueError("Offering target is required for offering contact row.")
        vendor_id = _resolve_parent_id(
            cache=vendor_cache,
            source_row_index=source_row_index,
            source_group_key=source_group_key,
            explicit_value=str(
                payload.get("vendor_id")
                or default_vendor_id
                or _lookup_offering_vendor_id(repo, offering_id=offering_id)
            ),
        )
        if not vendor_id:
            raise ValueError("Vendor target is required for offering contact row.")
        updates = {
            "contact_type": str(payload.get("contact_type") or "business").strip() or "business",
            "full_name": str(payload.get("full_name") or "").strip(),
            "email": str(payload.get("email") or "").strip(),
            "phone": str(payload.get("phone") or "").strip(),
        }
        if action == "merge" and target_id and hasattr(repo, "update_offering_contact"):
            repo.update_offering_contact(
                vendor_id=vendor_id,
                offering_id=offering_id,
                offering_contact_id=target_id,
                updates=updates,
                actor_user_principal=actor_user_principal,
                reason=reason,
            )
            return "merged", f"Offering contact merged ({target_id}).", {"vendor_id": vendor_id, "offering_id": offering_id}
        contact_id = repo.add_offering_contact(
            vendor_id=vendor_id,
            offering_id=offering_id,
            full_name=updates["full_name"] or updates["email"] or "Imported Contact",
            contact_type=updates["contact_type"],
            email=updates["email"] or None,
            phone=updates["phone"] or None,
            actor_user_principal=actor_user_principal,
        )
        return "created", f"Offering contact added ({contact_id}).", {"vendor_id": vendor_id, "offering_id": offering_id}

    if area_key == "contract":
        offering_id = _resolve_parent_id(
            cache=offering_cache,
            source_row_index=source_row_index,
            source_group_key=source_group_key,
            explicit_value=str(payload.get("offering_id") or default_offering_id),
        )
        vendor_id = _resolve_parent_id(
            cache=vendor_cache,
            source_row_index=source_row_index,
            source_group_key=source_group_key,
            explicit_value=str(
                payload.get("vendor_id")
                or default_vendor_id
                or _lookup_offering_vendor_id(repo, offering_id=offering_id)
            ),
        )
        if not vendor_id:
            raise ValueError("Vendor target is required for contract row.")
        contract_number = str(payload.get("contract_number") or "").strip()
        if action == "merge" and target_id and hasattr(repo, "update_contract"):
            updates: dict[str, Any] = {
                key: payload.get(key)
                for key in ("contract_number", "offering_id", "contract_status", "start_date", "end_date", "annual_value")
                if str(payload.get(key) or "").strip()
            }
            if not updates:
                updates = {"offering_id": offering_id}
            repo.update_contract(
                vendor_id=vendor_id,
                contract_id=target_id,
                actor_user_principal=actor_user_principal,
                updates=updates,
                reason=reason,
            )
            return "merged", f"Contract merged ({target_id}).", {"vendor_id": vendor_id, "offering_id": offering_id}
        if not contract_number:
            raise ValueError("contract_number is required for new contract rows.")
        contract_id = repo.create_contract(
            vendor_id=vendor_id,
            actor_user_principal=actor_user_principal,
            contract_number=contract_number,
            contract_status=str(payload.get("contract_status") or "active").strip() or "active",
            offering_id=offering_id or None,
            start_date=str(payload.get("start_date") or "").strip() or None,
            end_date=str(payload.get("end_date") or "").strip() or None,
            annual_value=str(payload.get("annual_value") or "").strip() or None,
        )
        return "created", f"Contract created ({contract_id}).", {"vendor_id": vendor_id, "offering_id": offering_id}

    if area_key in {"project", "invoice", "payment"}:
        layout_key = LAYOUT_BY_REVIEW_AREA.get(area_key, "projects")
        if area_key in {"invoice", "payment"} and default_offering_id and not str(payload.get("offering_id") or "").strip():
            payload["offering_id"] = default_offering_id
        fallback_vendor_id = _resolve_parent_id(
            cache=vendor_cache,
            source_row_index=source_row_index,
            source_group_key=source_group_key,
            explicit_value=str(payload.get("vendor_id") or default_vendor_id),
        )
        status, message, apply_result = apply_import_row(
            repo,
            layout_key=layout_key,
            row_data=payload,
            action=action,
            target_id=target_id,
            fallback_target_vendor_id=fallback_vendor_id,
            actor_user_principal=actor_user_principal,
            reason=reason,
            apply_context=None,
        )
        resolved: dict[str, str] = {}
        if isinstance(apply_result, dict):
            resolved = {
                "vendor_id": str(apply_result.get("vendor_id") or "").strip(),
                "offering_id": str(apply_result.get("offering_id") or "").strip(),
                "project_id": str(apply_result.get("project_id") or "").strip(),
                "invoice_id": str(apply_result.get("invoice_id") or "").strip(),
                "payment_id": str(apply_result.get("payment_id") or "").strip(),
            }
        return status, message, resolved

    raise ValueError(f"Unsupported review area '{area_key}'.")


@router.post("/imports/jobs/{job_id}/apply")
@require_permission("import_apply")
async def imports_job_apply(request: Request, job_id: str):
    imports_module = _imports_module()
    repo = imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    imports_module.log_page_view(request, user, "Imports")
    if write_blocked(user):
        add_flash(request, "Application is in locked mode. Import actions are disabled.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/final", status_code=303)
    job = repo.get_import_job(job_id)
    if job is None:
        add_flash(request, "Import job was not found.", "error")
        return RedirectResponse(url="/imports", status_code=303)
    workflow_state = str(job.get("status") or "").strip().lower()
    if workflow_state in {"applied", "applied_with_errors"}:
        add_flash(request, "This import job has already been applied.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/final", status_code=303)

    context_payload = dict(job.get("context") or {})
    approved, _mapping_status, _mapping_request_status, blocked_message = _resolve_stage_approval_or_message(
        repo,
        job=job,
        context=context_payload,
    )
    if not approved:
        add_flash(request, blocked_message, "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)
    if workflow_state != "ready_to_apply":
        add_flash(
            request,
            "Import job is not ready to apply. Complete staging and sequential review first.",
            "error",
        )
        return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)

    form = await request.form()
    if not _coerce_bool(form.get("final_confirm")):
        add_flash(request, "Final confirmation is required before apply.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/final", status_code=303)
    reason = str(form.get("reason") or "").strip()
    if _match_reason_required(repo, import_job_id=job_id) and not reason:
        add_flash(request, "Reason is required when merge decisions are present.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/final", status_code=303)

    area_states = _area_states(repo, import_job_id=job_id)
    if not area_states or any(str(row.get("status") or "").strip().lower() != "confirmed" for row in area_states):
        add_flash(request, "All review areas must be confirmed before apply.", "error")
        return RedirectResponse(url=f"/imports/jobs/{job_id}/final", status_code=303)

    actor = _resolve_user_principal(user)
    created_count = 0
    merged_count = 0
    skipped_count = 0
    failed_count = 0
    results: list[dict[str, Any]] = []
    vendor_cache: dict[tuple[int, str], str] = {}
    offering_cache: dict[tuple[int, str], str] = {}

    old_status = str(job.get("status") or "").strip().lower()
    for area_key in REVIEW_AREA_ORDER:
        rows = _serialize_review_rows(
            list(repo.list_import_review_rows(import_job_id=job_id, area_key=area_key) or [])
        )
        for row in rows:
            try:
                status, message, resolved = _apply_area_row(
                    repo,
                    area_key=area_key,
                    row=row,
                    actor_user_principal=actor,
                    reason=reason or "imports apply",
                    vendor_cache=vendor_cache,
                    offering_cache=offering_cache,
                )
                if status == "created":
                    created_count += 1
                elif status == "merged":
                    merged_count += 1
                elif status == "skipped":
                    skipped_count += 1
                else:
                    skipped_count += 1
                source_key = (
                    int(row.get("source_row_index") or 0),
                    str(row.get("source_group_key") or "__static__"),
                )
                vendor_id = str(resolved.get("vendor_id") or "").strip()
                offering_id = str(resolved.get("offering_id") or "").strip()
                if vendor_id:
                    vendor_cache[source_key] = vendor_id
                if offering_id:
                    offering_cache[source_key] = offering_id
                results.append(
                    {
                        "area_key": area_key,
                        "line_number": str(row.get("line_number") or "").strip(),
                        "status": status,
                        "message": message,
                    }
                )
            except Exception as exc:
                failed_count += 1
                results.append(
                    {
                        "area_key": area_key,
                        "line_number": str(row.get("line_number") or "").strip(),
                        "status": "failed",
                        "message": str(exc),
                    }
                )

    repo.finalize_import_stage_job(
        import_job_id=job_id,
        created_count=created_count,
        merged_count=merged_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        actor_user_principal=actor,
        error_message="" if failed_count == 0 else "One or more apply operations failed.",
    )

    refreshed_job = repo.get_import_job(job_id) or job
    context_payload = dict(refreshed_job.get("context") or {})
    context_payload["apply_results"] = results[:800]
    context_payload["apply_totals"] = {
        "created": created_count,
        "merged": merged_count,
        "skipped": skipped_count,
        "failed": failed_count,
    }
    repo.update_import_job_context(
        import_job_id=job_id,
        context=context_payload,
        actor_user_principal=actor,
    )
    _log_workflow_transition(
        repo,
        job=refreshed_job,
        old_status=old_status,
        new_status=str(refreshed_job.get("status") or "").strip().lower(),
        actor_user_principal=actor,
        message="apply completed",
    )

    if failed_count == 0:
        add_flash(
            request,
            f"Apply complete. created={created_count}, merged={merged_count}, skipped={skipped_count}, failed={failed_count}",
            "success",
        )
    else:
        add_flash(
            request,
            f"Apply completed with errors. created={created_count}, merged={merged_count}, skipped={skipped_count}, failed={failed_count}",
            "error",
        )
    return RedirectResponse(url=f"/imports/jobs/{job_id}/final", status_code=303)


@router.post("/imports/remap")
@require_permission("import_preview")
async def imports_legacy_remap_wrapper(request: Request):
    form = await request.form()
    job_id = str(form.get("import_job_id") or "").strip()
    if not job_id:
        token = str(form.get("preview_token") or "").strip()
        payload = load_preview_payload(token) if token else None
        job_id = str((payload or {}).get("import_job_id") or "").strip()
    if not job_id:
        add_flash(request, "Compatibility remap wrapper could not resolve import job.", "error")
        return RedirectResponse(url="/imports", status_code=303)
    return RedirectResponse(url=f"/imports/jobs/{job_id}/mapping", status_code=303)


@router.post("/imports/apply")
@require_permission("import_apply")
async def imports_legacy_apply_wrapper(request: Request):
    form = await request.form()
    job_id = str(form.get("import_job_id") or "").strip()
    if not job_id:
        token = str(form.get("preview_token") or "").strip()
        payload = load_preview_payload(token) if token else None
        job_id = str((payload or {}).get("import_job_id") or "").strip()
    if not job_id:
        add_flash(request, "Compatibility apply wrapper could not resolve import job.", "error")
        return RedirectResponse(url="/imports", status_code=303)
    return RedirectResponse(url=f"/imports/jobs/{job_id}/final", status_code=303)

