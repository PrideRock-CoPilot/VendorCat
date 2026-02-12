from __future__ import annotations

from copy import deepcopy
import csv
import io
import threading
import time
import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from vendor_catalog_app.web.flash import add_flash
from vendor_catalog_app.web.services import (
    base_template_context,
    ensure_session_started,
    get_repo,
    get_user_context,
    log_page_view,
)


router = APIRouter()

IMPORT_LAYOUTS: dict[str, dict[str, Any]] = {
    "vendors": {
        "label": "Vendors",
        "description": "Create new vendor profiles or merge updates into existing vendor records.",
        "fields": ["vendor_id", "legal_name", "display_name", "owner_org_id", "lifecycle_state", "risk_tier"],
        "sample_rows": [
            {
                "vendor_id": "",
                "legal_name": "Acme Cloud LLC",
                "display_name": "Acme Cloud",
                "owner_org_id": "IT",
                "lifecycle_state": "draft",
                "risk_tier": "medium",
            }
        ],
    },
    "offerings": {
        "label": "Offerings",
        "description": "Create new offerings or merge updates into existing offerings.",
        "fields": [
            "offering_id",
            "vendor_id",
            "offering_name",
            "offering_type",
            "lob",
            "service_type",
            "lifecycle_state",
            "criticality_tier",
        ],
        "sample_rows": [
            {
                "offering_id": "",
                "vendor_id": "vnd-123456",
                "offering_name": "Enterprise Search",
                "offering_type": "software",
                "lob": "internal_platform",
                "service_type": "saas",
                "lifecycle_state": "draft",
                "criticality_tier": "tier2",
            }
        ],
    },
    "projects": {
        "label": "Projects",
        "description": "Create new projects or merge updates into existing projects.",
        "fields": [
            "project_id",
            "vendor_id",
            "project_name",
            "project_type",
            "status",
            "start_date",
            "target_date",
            "owner_principal",
            "description",
        ],
        "sample_rows": [
            {
                "project_id": "",
                "vendor_id": "vnd-123456",
                "project_name": "Q2 Renewal Program",
                "project_type": "renewal",
                "status": "draft",
                "start_date": "2026-03-01",
                "target_date": "2026-06-30",
                "owner_principal": "jane.doe@example.com",
                "description": "Renewal and right-sizing workstream.",
            }
        ],
    },
}

ALLOWED_IMPORT_ACTIONS = {"new", "merge", "skip"}
_IMPORT_PREVIEW_TTL_SEC = 1800.0
_IMPORT_PREVIEW_MAX_ITEMS = 64
_IMPORT_PREVIEW_LOCK = threading.Lock()
_IMPORT_PREVIEW_STORE: dict[str, tuple[float, dict[str, Any]]] = {}


def _can_manage_imports(user) -> bool:
    return bool(getattr(user, "can_edit", False))


def _write_blocked(user) -> bool:
    return bool(getattr(getattr(user, "config", None), "locked_mode", False))


def _safe_layout(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned in IMPORT_LAYOUTS:
        return cleaned
    return "vendors"


def _layout_options() -> list[dict[str, str]]:
    return [
        {"key": key, "label": str(spec.get("label") or key.title()), "description": str(spec.get("description") or "")}
        for key, spec in IMPORT_LAYOUTS.items()
    ]


def _normalize_column_name(raw_name: str) -> str:
    cleaned = str(raw_name or "").strip().lower()
    cleaned = cleaned.replace(" ", "_").replace("-", "_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned


def _decode_upload_bytes(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except Exception:
            continue
    raise ValueError("Could not decode upload. Use UTF-8 CSV.")


def _parse_layout_rows(layout_key: str, raw_bytes: bytes) -> list[dict[str, str]]:
    spec = IMPORT_LAYOUTS[layout_key]
    text = _decode_upload_bytes(raw_bytes)
    stream = io.StringIO(text)
    reader = csv.DictReader(stream)
    if not reader.fieldnames:
        raise ValueError("CSV must include a header row.")

    normalized_fields = [_normalize_column_name(name) for name in reader.fieldnames]
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
    if len(rows) > 1000:
        raise ValueError("Upload is too large. Maximum 1000 rows per import.")
    return rows


def _label_for_vendor_row(row: dict[str, Any]) -> str:
    vendor_id = str(row.get("vendor_id") or "").strip()
    display_name = str(row.get("display_name") or row.get("legal_name") or vendor_id).strip()
    return f"{display_name} ({vendor_id})" if vendor_id else display_name


def _label_for_offering_row(row: dict[str, Any]) -> str:
    offering_id = str(row.get("offering_id") or "").strip()
    offering_name = str(row.get("offering_name") or offering_id).strip()
    vendor_id = str(row.get("vendor_id") or "").strip()
    if vendor_id and offering_id:
        return f"{offering_name} ({offering_id}) / {vendor_id}"
    if offering_id:
        return f"{offering_name} ({offering_id})"
    return offering_name


def _label_for_project_row(row: dict[str, Any]) -> str:
    project_id = str(row.get("project_id") or "").strip()
    project_name = str(row.get("project_name") or project_id).strip()
    vendor_id = str(row.get("vendor_id") or "").strip()
    if vendor_id and project_id:
        return f"{project_name} ({project_id}) / {vendor_id}"
    if project_id:
        return f"{project_name} ({project_id})"
    return project_name


def _suggest_vendor_match(repo, row_data: dict[str, str]) -> tuple[str, str, list[str]]:
    notes: list[str] = []
    explicit_vendor_id = str(row_data.get("vendor_id") or "").strip()
    if explicit_vendor_id:
        existing = repo.get_vendor_profile(explicit_vendor_id)
        if not existing.empty:
            row = existing.iloc[0].to_dict()
            return explicit_vendor_id, _label_for_vendor_row(row), notes
        notes.append(f"vendor_id '{explicit_vendor_id}' was not found.")
        return "", "", notes

    query = str(row_data.get("legal_name") or row_data.get("display_name") or "").strip()
    if not query:
        return "", "", notes
    candidates = repo.search_vendors_typeahead(q=query, limit=10).to_dict("records")
    if not candidates:
        return "", "", notes
    lowered = query.lower()
    exact = [
        row
        for row in candidates
        if str(row.get("vendor_id") or "").strip().lower() == lowered
        or str(row.get("display_name") or "").strip().lower() == lowered
        or str(row.get("legal_name") or "").strip().lower() == lowered
    ]
    if len(exact) == 1:
        row = exact[0]
        return str(row.get("vendor_id") or "").strip(), _label_for_vendor_row(row), notes
    if len(candidates) == 1:
        row = candidates[0]
        notes.append("Single near-match found by name.")
        return str(row.get("vendor_id") or "").strip(), _label_for_vendor_row(row), notes
    return "", "", notes


def _suggest_offering_match(repo, row_data: dict[str, str]) -> tuple[str, str, str, list[str]]:
    notes: list[str] = []
    explicit_offering_id = str(row_data.get("offering_id") or "").strip()
    if explicit_offering_id:
        existing = repo.get_offerings_by_ids([explicit_offering_id])
        if not existing.empty:
            row = existing.iloc[0].to_dict()
            return (
                explicit_offering_id,
                str(row.get("vendor_id") or "").strip(),
                _label_for_offering_row(row),
                notes,
            )
        notes.append(f"offering_id '{explicit_offering_id}' was not found.")
        return "", "", "", notes

    query = str(row_data.get("offering_name") or "").strip()
    if not query:
        return "", "", "", notes
    vendor_filter = str(row_data.get("vendor_id") or "").strip() or None
    candidates = repo.search_offerings_typeahead(vendor_id=vendor_filter, q=query, limit=10).to_dict("records")
    if not candidates:
        return "", "", "", notes
    lowered = query.lower()
    exact = [
        row
        for row in candidates
        if str(row.get("offering_id") or "").strip().lower() == lowered
        or str(row.get("offering_name") or "").strip().lower() == lowered
    ]
    if len(exact) == 1:
        row = exact[0]
        return (
            str(row.get("offering_id") or "").strip(),
            str(row.get("vendor_id") or "").strip(),
            _label_for_offering_row(row),
            notes,
        )
    if len(candidates) == 1:
        row = candidates[0]
        notes.append("Single near-match found by name.")
        return (
            str(row.get("offering_id") or "").strip(),
            str(row.get("vendor_id") or "").strip(),
            _label_for_offering_row(row),
            notes,
        )
    return "", "", "", notes


def _suggest_project_match(repo, row_data: dict[str, str]) -> tuple[str, str, str, list[str]]:
    notes: list[str] = []
    explicit_project_id = str(row_data.get("project_id") or "").strip()
    if explicit_project_id:
        project = repo.get_project_by_id(explicit_project_id)
        if project:
            return (
                explicit_project_id,
                str(project.get("vendor_id") or "").strip(),
                _label_for_project_row(project),
                notes,
            )
        notes.append(f"project_id '{explicit_project_id}' was not found.")
        return "", "", "", notes

    query = str(row_data.get("project_name") or "").strip()
    if not query:
        return "", "", "", notes
    vendor_filter = str(row_data.get("vendor_id") or "").strip()
    candidates = repo.search_projects_typeahead(q=query, limit=10).to_dict("records")
    if vendor_filter:
        candidates = [row for row in candidates if str(row.get("vendor_id") or "").strip() == vendor_filter]
    if not candidates:
        return "", "", "", notes
    lowered = query.lower()
    exact = [
        row
        for row in candidates
        if str(row.get("project_id") or "").strip().lower() == lowered
        or str(row.get("project_name") or "").strip().lower() == lowered
    ]
    if len(exact) == 1:
        row = exact[0]
        return (
            str(row.get("project_id") or "").strip(),
            str(row.get("vendor_id") or "").strip(),
            _label_for_project_row(row),
            notes,
        )
    if len(candidates) == 1:
        row = candidates[0]
        notes.append("Single near-match found by name.")
        return (
            str(row.get("project_id") or "").strip(),
            str(row.get("vendor_id") or "").strip(),
            _label_for_project_row(row),
            notes,
        )
    return "", "", "", notes


def _build_preview_rows(repo, layout_key: str, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    preview_rows: list[dict[str, Any]] = []
    for idx, row_data in enumerate(rows, start=1):
        errors: list[str] = []
        notes: list[str] = []
        suggested_target_id = ""
        suggested_target_vendor_id = ""
        suggested_target_label = ""
        if layout_key == "vendors":
            suggested_target_id, suggested_target_label, notes = _suggest_vendor_match(repo, row_data)
        elif layout_key == "offerings":
            suggested_target_id, suggested_target_vendor_id, suggested_target_label, notes = _suggest_offering_match(
                repo,
                row_data,
            )
        else:
            suggested_target_id, suggested_target_vendor_id, suggested_target_label, notes = _suggest_project_match(
                repo,
                row_data,
            )

        if layout_key == "vendors" and not str(row_data.get("legal_name") or "").strip():
            errors.append("legal_name is required for new records.")
        if layout_key == "offerings":
            if not str(row_data.get("offering_name") or "").strip():
                errors.append("offering_name is required for new records.")
            if not str(row_data.get("vendor_id") or "").strip() and not suggested_target_vendor_id:
                errors.append("vendor_id is required for new records.")
        if layout_key == "projects" and not str(row_data.get("project_name") or "").strip():
            errors.append("project_name is required for new records.")

        preview_rows.append(
            {
                "row_index": idx,
                "line_number": str(row_data.get("_line") or ""),
                "row_data": {k: v for k, v in row_data.items() if k != "_line"},
                "suggested_action": "merge" if suggested_target_id else "new",
                "suggested_target_id": suggested_target_id,
                "suggested_target_vendor_id": suggested_target_vendor_id,
                "suggested_target_label": suggested_target_label,
                "notes": notes,
                "errors": errors,
            }
        )
    return preview_rows


def _prune_preview_store(now: float) -> None:
    expired = [token for token, (created, _) in _IMPORT_PREVIEW_STORE.items() if (now - created) >= _IMPORT_PREVIEW_TTL_SEC]
    for token in expired:
        _IMPORT_PREVIEW_STORE.pop(token, None)
    while len(_IMPORT_PREVIEW_STORE) > _IMPORT_PREVIEW_MAX_ITEMS:
        oldest_token = min(_IMPORT_PREVIEW_STORE, key=lambda key: _IMPORT_PREVIEW_STORE[key][0], default=None)
        if oldest_token is None:
            break
        _IMPORT_PREVIEW_STORE.pop(oldest_token, None)


def _save_preview_payload(payload: dict[str, Any]) -> str:
    token = uuid.uuid4().hex
    now = time.monotonic()
    with _IMPORT_PREVIEW_LOCK:
        _prune_preview_store(now)
        _IMPORT_PREVIEW_STORE[token] = (now, deepcopy(payload))
    return token


def _load_preview_payload(token: str) -> dict[str, Any] | None:
    key = str(token or "").strip()
    if not key:
        return None
    now = time.monotonic()
    with _IMPORT_PREVIEW_LOCK:
        _prune_preview_store(now)
        entry = _IMPORT_PREVIEW_STORE.get(key)
        if entry is None:
            return None
        _, payload = entry
        return deepcopy(payload)


def _discard_preview_payload(token: str) -> None:
    key = str(token or "").strip()
    if not key:
        return
    with _IMPORT_PREVIEW_LOCK:
        _IMPORT_PREVIEW_STORE.pop(key, None)


def _vendor_updates_from_row(row_data: dict[str, str]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for field in ("legal_name", "display_name", "lifecycle_state", "owner_org_id", "risk_tier"):
        value = str(row_data.get(field) or "").strip()
        if value:
            updates[field] = value
    return updates


def _offering_updates_from_row(row_data: dict[str, str]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for field in ("offering_name", "offering_type", "lob", "service_type", "lifecycle_state", "criticality_tier"):
        value = str(row_data.get(field) or "").strip()
        if value:
            updates[field] = value
    return updates


def _project_updates_from_row(row_data: dict[str, str]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for field in ("project_name", "project_type", "status", "start_date", "target_date", "owner_principal", "description"):
        value = str(row_data.get(field) or "").strip()
        if value:
            updates[field] = value
    return updates


def _apply_import_row(
    repo,
    *,
    layout_key: str,
    row_data: dict[str, str],
    action: str,
    target_id: str,
    fallback_target_vendor_id: str,
    actor_user_principal: str,
    reason: str,
) -> tuple[str, str]:
    selected_action = str(action or "").strip().lower()
    if selected_action == "skip":
        return "skipped", "Skipped by user."

    if layout_key == "vendors":
        if selected_action == "new":
            legal_name = str(row_data.get("legal_name") or "").strip()
            owner_org_id = str(row_data.get("owner_org_id") or "").strip()
            if not legal_name:
                raise ValueError("legal_name is required for new vendor records.")
            if not owner_org_id:
                raise ValueError("owner_org_id is required for new vendor records.")
            created_vendor_id = repo.create_vendor_profile(
                actor_user_principal=actor_user_principal,
                legal_name=legal_name,
                display_name=str(row_data.get("display_name") or "").strip() or None,
                lifecycle_state=str(row_data.get("lifecycle_state") or "").strip() or "draft",
                owner_org_id=owner_org_id,
                risk_tier=str(row_data.get("risk_tier") or "").strip() or None,
                source_system="bulk_import",
            )
            return "created", f"Vendor created: {created_vendor_id}"
        if not target_id:
            raise ValueError("Target vendor_id is required for merge.")
        updates = _vendor_updates_from_row(row_data)
        if not updates:
            raise ValueError("No merge updates were provided for vendor row.")
        repo.apply_vendor_profile_update(
            vendor_id=target_id,
            actor_user_principal=actor_user_principal,
            updates=updates,
            reason=reason,
        )
        return "merged", f"Vendor merged: {target_id}"

    if layout_key == "offerings":
        if selected_action == "new":
            vendor_id = str(row_data.get("vendor_id") or "").strip()
            offering_name = str(row_data.get("offering_name") or "").strip()
            if not vendor_id:
                raise ValueError("vendor_id is required for new offering records.")
            if not offering_name:
                raise ValueError("offering_name is required for new offering records.")
            created_offering_id = repo.create_offering(
                vendor_id=vendor_id,
                actor_user_principal=actor_user_principal,
                offering_name=offering_name,
                offering_type=str(row_data.get("offering_type") or "").strip() or None,
                lob=str(row_data.get("lob") or "").strip() or None,
                service_type=str(row_data.get("service_type") or "").strip() or None,
                lifecycle_state=str(row_data.get("lifecycle_state") or "").strip() or "draft",
                criticality_tier=str(row_data.get("criticality_tier") or "").strip() or None,
            )
            return "created", f"Offering created: {created_offering_id}"
        if not target_id:
            raise ValueError("Target offering_id is required for merge.")
        target_vendor_id = str(row_data.get("vendor_id") or "").strip() or str(fallback_target_vendor_id or "").strip()
        if not target_vendor_id:
            existing = repo.get_offerings_by_ids([target_id])
            if existing.empty:
                raise ValueError("Target offering was not found.")
            target_vendor_id = str(existing.iloc[0].to_dict().get("vendor_id") or "").strip()
        updates = _offering_updates_from_row(row_data)
        if not updates:
            raise ValueError("No merge updates were provided for offering row.")
        repo.update_offering_fields(
            vendor_id=target_vendor_id,
            offering_id=target_id,
            actor_user_principal=actor_user_principal,
            updates=updates,
            reason=reason,
        )
        return "merged", f"Offering merged: {target_id}"

    if selected_action == "new":
        project_name = str(row_data.get("project_name") or "").strip()
        if not project_name:
            raise ValueError("project_name is required for new project records.")
        created_project_id = repo.create_project(
            vendor_id=str(row_data.get("vendor_id") or "").strip() or None,
            actor_user_principal=actor_user_principal,
            project_name=project_name,
            project_type=str(row_data.get("project_type") or "").strip() or None,
            status=str(row_data.get("status") or "").strip() or "draft",
            start_date=str(row_data.get("start_date") or "").strip() or None,
            target_date=str(row_data.get("target_date") or "").strip() or None,
            owner_principal=str(row_data.get("owner_principal") or "").strip() or None,
            description=str(row_data.get("description") or "").strip() or None,
            linked_offering_ids=[],
        )
        return "created", f"Project created: {created_project_id}"
    if not target_id:
        raise ValueError("Target project_id is required for merge.")
    existing_project = repo.get_project_by_id(target_id)
    if existing_project is None:
        raise ValueError("Target project was not found.")
    target_vendor_id = str(row_data.get("vendor_id") or "").strip() or str(existing_project.get("vendor_id") or "").strip()
    updates = _project_updates_from_row(row_data)
    if not updates and not target_vendor_id:
        raise ValueError("No merge updates were provided for project row.")
    target_vendor_ids = [target_vendor_id] if target_vendor_id else None
    repo.update_project(
        vendor_id=target_vendor_id or None,
        project_id=target_id,
        actor_user_principal=actor_user_principal,
        updates=updates,
        vendor_ids=target_vendor_ids,
        linked_offering_ids=None,
        reason=reason,
    )
    return "merged", f"Project merged: {target_id}"


@router.get("/imports")
def imports_home(request: Request):
    get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Imports")

    if not _can_manage_imports(user):
        add_flash(request, "You do not have permission to access Imports.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    context = base_template_context(
        request,
        user,
        title="Data Imports",
        active_nav="imports",
        extra={
            "layout_options": _layout_options(),
            "selected_layout": "vendors",
            "selected_layout_spec": IMPORT_LAYOUTS["vendors"],
            "preview_token": "",
            "preview_rows": [],
            "import_results": [],
            "import_reason": "",
        },
    )
    return request.app.state.templates.TemplateResponse(request, "imports.html", context)


@router.get("/imports/templates/{layout_key}.csv")
def import_template_download(layout_key: str):
    selected_layout = _safe_layout(layout_key)
    spec = IMPORT_LAYOUTS[selected_layout]
    fields = [str(field) for field in spec.get("fields", [])]
    sample_rows = list(spec.get("sample_rows") or [])
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for sample in sample_rows:
        writer.writerow({field: str(sample.get(field, "") or "") for field in fields})
    filename = f"vendorcat_{selected_layout}_template.csv"
    return Response(
        content=stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename=\"{filename}\"'},
    )


@router.post("/imports/preview")
async def imports_preview(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Imports")

    if not _can_manage_imports(user):
        add_flash(request, "You do not have permission to run imports.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)
    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Import actions are disabled.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    form = await request.form()
    selected_layout = _safe_layout(str(form.get("layout", "vendors")))
    upload = form.get("file")
    if upload is None or not hasattr(upload, "filename"):
        add_flash(request, "Select a CSV file to upload.", "error")
        return RedirectResponse(url="/imports", status_code=303)
    raw_bytes = await upload.read()
    if not raw_bytes:
        add_flash(request, "Uploaded file is empty.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    try:
        parsed_rows = _parse_layout_rows(selected_layout, raw_bytes)
        preview_rows = _build_preview_rows(repo, selected_layout, parsed_rows)
    except Exception as exc:
        add_flash(request, f"Failed to parse import file: {exc}", "error")
        return RedirectResponse(url="/imports", status_code=303)

    preview_payload = {
        "layout_key": selected_layout,
        "rows": preview_rows,
    }
    preview_token = _save_preview_payload(preview_payload)
    context = base_template_context(
        request,
        user,
        title="Data Imports",
        active_nav="imports",
        extra={
            "layout_options": _layout_options(),
            "selected_layout": selected_layout,
            "selected_layout_spec": IMPORT_LAYOUTS[selected_layout],
            "preview_token": preview_token,
            "preview_rows": preview_rows,
            "import_results": [],
            "import_reason": "",
        },
    )
    return request.app.state.templates.TemplateResponse(request, "imports.html", context)


@router.post("/imports/apply")
async def imports_apply(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Imports")

    if not _can_manage_imports(user):
        add_flash(request, "You do not have permission to run imports.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)
    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Import actions are disabled.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    form = await request.form()
    preview_token = str(form.get("preview_token", "")).strip()
    reason = str(form.get("reason", "")).strip()
    payload = _load_preview_payload(preview_token)
    if payload is None:
        add_flash(request, "Import preview expired. Upload the file again.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    layout_key = _safe_layout(str(payload.get("layout_key") or "vendors"))
    preview_rows = list(payload.get("rows") or [])
    results: list[dict[str, Any]] = []
    created_count = 0
    merged_count = 0
    skipped_count = 0
    failed_count = 0
    for preview_row in preview_rows:
        row_index = int(preview_row.get("row_index") or 0)
        row_data = dict(preview_row.get("row_data") or {})
        default_action = str(preview_row.get("suggested_action") or "new").strip().lower()
        selected_action = str(form.get(f"action_{row_index}", default_action)).strip().lower()
        if selected_action not in ALLOWED_IMPORT_ACTIONS:
            selected_action = "skip"
        target_id = str(
            form.get(
                f"target_{row_index}",
                str(preview_row.get("suggested_target_id") or ""),
            )
            or ""
        ).strip()
        fallback_target_vendor_id = str(preview_row.get("suggested_target_vendor_id") or "").strip()

        try:
            if selected_action == "merge" and not reason:
                raise ValueError("Reason is required for merge actions.")
            status, message = _apply_import_row(
                repo,
                layout_key=layout_key,
                row_data=row_data,
                action=selected_action,
                target_id=target_id,
                fallback_target_vendor_id=fallback_target_vendor_id,
                actor_user_principal=user.user_principal,
                reason=reason or "bulk import",
            )
            if status == "created":
                created_count += 1
            elif status == "merged":
                merged_count += 1
            elif status == "skipped":
                skipped_count += 1
            results.append(
                {
                    "row_index": row_index,
                    "status": status,
                    "message": message,
                }
            )
        except Exception as exc:
            failed_count += 1
            results.append(
                {
                    "row_index": row_index,
                    "status": "failed",
                    "message": str(exc),
                }
            )

    _discard_preview_payload(preview_token)
    if failed_count == 0:
        add_flash(
            request,
            (
                "Import complete. "
                f"created={created_count}, merged={merged_count}, skipped={skipped_count}, failed={failed_count}"
            ),
            "success",
        )
    else:
        add_flash(
            request,
            (
                "Import completed with errors. "
                f"created={created_count}, merged={merged_count}, skipped={skipped_count}, failed={failed_count}"
            ),
            "error",
        )

    context = base_template_context(
        request,
        user,
        title="Data Imports",
        active_nav="imports",
        extra={
            "layout_options": _layout_options(),
            "selected_layout": layout_key,
            "selected_layout_spec": IMPORT_LAYOUTS[layout_key],
            "preview_token": "",
            "preview_rows": [],
            "import_results": results,
            "import_reason": reason,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "imports.html", context)
