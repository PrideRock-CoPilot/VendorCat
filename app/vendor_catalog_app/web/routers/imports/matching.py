from __future__ import annotations

import re
from typing import Any


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    return digits


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


class ImportMatchContext:
    def __init__(self, repo) -> None:
        self.repo = repo
        self._vendor_profile_cache: dict[str, dict[str, Any] | None] = {}
        self._offering_cache: dict[str, dict[str, Any] | None] = {}
        self._project_cache: dict[str, dict[str, Any] | None] = {}
        self._vendor_search_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
        self._offering_search_cache: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
        self._project_search_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
        self._contact_maps_loaded = False
        self._vendor_ids_by_email: dict[str, set[str]] = {}
        self._vendor_ids_by_phone: dict[str, set[str]] = {}

    def vendor_profile(self, vendor_id: str) -> dict[str, Any] | None:
        key = str(vendor_id or "").strip()
        if not key:
            return None
        if key in self._vendor_profile_cache:
            return self._vendor_profile_cache[key]
        profile_df = self.repo.get_vendor_profile(key)
        profile = profile_df.iloc[0].to_dict() if not profile_df.empty else None
        self._vendor_profile_cache[key] = profile
        return profile

    def offering_by_id(self, offering_id: str) -> dict[str, Any] | None:
        key = str(offering_id or "").strip()
        if not key:
            return None
        if key in self._offering_cache:
            return self._offering_cache[key]
        rows = self.repo.get_offerings_by_ids([key])
        item = rows.iloc[0].to_dict() if not rows.empty else None
        self._offering_cache[key] = item
        return item

    def project_by_id(self, project_id: str) -> dict[str, Any] | None:
        key = str(project_id or "").strip()
        if not key:
            return None
        if key in self._project_cache:
            return self._project_cache[key]
        project = self.repo.get_project_by_id(key)
        self._project_cache[key] = project
        return project

    def search_vendors(self, *, q: str, limit: int = 10) -> list[dict[str, Any]]:
        query = str(q or "").strip()
        if not query:
            return []
        key = (query.lower(), int(limit))
        if key in self._vendor_search_cache:
            return self._vendor_search_cache[key]
        rows = self.repo.search_vendors_typeahead(q=query, limit=limit).to_dict("records")
        self._vendor_search_cache[key] = rows
        return rows

    def search_offerings(self, *, vendor_id: str | None, q: str, limit: int = 10) -> list[dict[str, Any]]:
        query = str(q or "").strip()
        vendor_filter = str(vendor_id or "").strip()
        if not query:
            return []
        key = (vendor_filter.lower(), query.lower(), int(limit))
        if key in self._offering_search_cache:
            return self._offering_search_cache[key]
        rows = self.repo.search_offerings_typeahead(vendor_id=vendor_filter or None, q=query, limit=limit).to_dict("records")
        self._offering_search_cache[key] = rows
        return rows

    def search_projects(self, *, q: str, limit: int = 10) -> list[dict[str, Any]]:
        query = str(q or "").strip()
        if not query:
            return []
        key = (query.lower(), int(limit))
        if key in self._project_search_cache:
            return self._project_search_cache[key]
        rows = self.repo.search_projects_typeahead(q=query, limit=limit).to_dict("records")
        self._project_search_cache[key] = rows
        return rows

    def _load_contact_maps(self) -> None:
        if self._contact_maps_loaded:
            return
        self._contact_maps_loaded = True
        try:
            rows = self.repo.list_vendor_contacts_index(limit=250000).to_dict("records")
        except Exception:
            return
        for row in rows:
            vendor_id = str(row.get("vendor_id") or "").strip()
            if not vendor_id:
                continue
            email = _normalize_email(str(row.get("email") or ""))
            phone = _normalize_phone(str(row.get("phone") or ""))
            if email:
                self._vendor_ids_by_email.setdefault(email, set()).add(vendor_id)
            if len(phone) >= 7:
                self._vendor_ids_by_phone.setdefault(phone, set()).add(vendor_id)

    def match_vendor_by_contact(self, *, email: str, phone: str) -> tuple[str, str]:
        self._load_contact_maps()
        normalized_email = _normalize_email(email)
        normalized_phone = _normalize_phone(phone)
        email_matches = self._vendor_ids_by_email.get(normalized_email, set()) if normalized_email else set()
        phone_matches = self._vendor_ids_by_phone.get(normalized_phone, set()) if len(normalized_phone) >= 7 else set()

        if normalized_email and len(email_matches) == 1:
            return next(iter(email_matches)), "Matched vendor via support/contact email."
        if normalized_phone and len(phone_matches) == 1:
            return next(iter(phone_matches)), "Matched vendor via support/contact phone."
        if normalized_email and len(email_matches) > 1:
            return "", "Support/contact email matched multiple vendors."
        if normalized_phone and len(phone_matches) > 1:
            return "", "Support/contact phone matched multiple vendors."
        return "", ""


def _suggest_vendor_match(repo, row_data: dict[str, str], ctx: ImportMatchContext) -> tuple[str, str, list[str]]:
    notes: list[str] = []
    explicit_vendor_id = str(row_data.get("vendor_id") or "").strip()
    if explicit_vendor_id:
        existing = ctx.vendor_profile(explicit_vendor_id)
        if existing is not None:
            return explicit_vendor_id, _label_for_vendor_row(existing), notes
        notes.append(f"vendor_id '{explicit_vendor_id}' was not found.")
        return "", "", notes

    query = str(row_data.get("legal_name") or row_data.get("display_name") or row_data.get("vendor_name") or "").strip()
    if query:
        candidates = ctx.search_vendors(q=query, limit=10)
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

    vendor_id_by_contact, contact_note = ctx.match_vendor_by_contact(
        email=str(row_data.get("support_email") or row_data.get("vendor_contact_email") or "").strip(),
        phone=str(row_data.get("support_phone") or row_data.get("vendor_support_phone") or "").strip(),
    )
    if contact_note:
        notes.append(contact_note)
    if vendor_id_by_contact:
        existing = ctx.vendor_profile(vendor_id_by_contact) or {"vendor_id": vendor_id_by_contact}
        return vendor_id_by_contact, _label_for_vendor_row(existing), notes
    return "", "", notes


def _infer_vendor_for_offering(row_data: dict[str, str], ctx: ImportMatchContext) -> tuple[str, list[str]]:
    notes: list[str] = []
    explicit_vendor_id = str(row_data.get("vendor_id") or "").strip()
    if explicit_vendor_id:
        return explicit_vendor_id, notes

    vendor_name = str(row_data.get("vendor_name") or "").strip()
    if vendor_name:
        candidates = ctx.search_vendors(q=vendor_name, limit=10)
        lowered = vendor_name.lower()
        exact = [
            row
            for row in candidates
            if str(row.get("display_name") or "").strip().lower() == lowered
            or str(row.get("legal_name") or "").strip().lower() == lowered
            or str(row.get("vendor_id") or "").strip().lower() == lowered
        ]
        if len(exact) == 1:
            row = exact[0]
            notes.append("Inferred vendor from vendor_name.")
            return str(row.get("vendor_id") or "").strip(), notes
        if len(candidates) == 1:
            row = candidates[0]
            notes.append("Single near-match found for vendor_name.")
            return str(row.get("vendor_id") or "").strip(), notes
        if len(candidates) > 1:
            notes.append("vendor_name matched multiple vendors.")

    vendor_id_by_contact, contact_note = ctx.match_vendor_by_contact(
        email=str(row_data.get("vendor_contact_email") or "").strip(),
        phone=str(row_data.get("vendor_support_phone") or "").strip(),
    )
    if contact_note:
        notes.append(contact_note)
    if vendor_id_by_contact:
        return vendor_id_by_contact, notes
    return "", notes


def _suggest_offering_match(repo, row_data: dict[str, str], ctx: ImportMatchContext) -> tuple[str, str, str, list[str]]:
    notes: list[str] = []
    explicit_offering_id = str(row_data.get("offering_id") or "").strip()
    if explicit_offering_id:
        existing = ctx.offering_by_id(explicit_offering_id)
        if existing is not None:
            return (
                explicit_offering_id,
                str(existing.get("vendor_id") or "").strip(),
                _label_for_offering_row(existing),
                notes,
            )
        notes.append(f"offering_id '{explicit_offering_id}' was not found.")
        return "", "", "", notes

    inferred_vendor_id, infer_notes = _infer_vendor_for_offering(row_data, ctx)
    notes.extend(infer_notes)

    query = str(row_data.get("offering_name") or "").strip()
    if not query:
        return "", inferred_vendor_id, "", notes
    candidates = ctx.search_offerings(vendor_id=inferred_vendor_id or None, q=query, limit=10)
    if not candidates and inferred_vendor_id:
        notes.append("No offering matched by name for inferred vendor.")
        return "", inferred_vendor_id, "", notes
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
        notes.append("Single near-match found by offering name.")
        return (
            str(row.get("offering_id") or "").strip(),
            str(row.get("vendor_id") or "").strip(),
            _label_for_offering_row(row),
            notes,
        )
    return "", inferred_vendor_id, "", notes


def _suggest_project_match(repo, row_data: dict[str, str], ctx: ImportMatchContext) -> tuple[str, str, str, list[str]]:
    notes: list[str] = []
    explicit_project_id = str(row_data.get("project_id") or "").strip()
    if explicit_project_id:
        project = ctx.project_by_id(explicit_project_id)
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
    candidates = ctx.search_projects(q=query, limit=10)
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


def build_preview_rows(repo, layout_key: str, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    preview_rows: list[dict[str, Any]] = []
    ctx = ImportMatchContext(repo)
    for idx, row_data in enumerate(rows, start=1):
        errors: list[str] = []
        notes: list[str] = []
        suggested_target_id = ""
        suggested_target_vendor_id = ""
        suggested_target_label = ""
        if layout_key == "vendors":
            suggested_target_id, suggested_target_label, notes = _suggest_vendor_match(repo, row_data, ctx)
        elif layout_key == "offerings":
            suggested_target_id, suggested_target_vendor_id, suggested_target_label, notes = _suggest_offering_match(
                repo,
                row_data,
                ctx,
            )
        else:
            suggested_target_id, suggested_target_vendor_id, suggested_target_label, notes = _suggest_project_match(
                repo,
                row_data,
                ctx,
            )

        if layout_key == "vendors" and not str(row_data.get("legal_name") or "").strip():
            errors.append("legal_name is required for new records.")
        if layout_key == "offerings":
            if not str(row_data.get("offering_name") or "").strip():
                errors.append("offering_name is required for new records.")
            if not str(row_data.get("vendor_id") or "").strip() and not suggested_target_vendor_id:
                errors.append("vendor_id is required, or provide vendor_name/contact fields for auto-match.")
        if layout_key == "projects" and not str(row_data.get("project_name") or "").strip():
            errors.append("project_name is required for new records.")

        row_status = "ready"
        if errors:
            row_status = "error"
        elif notes:
            row_status = "review"

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
                "row_status": row_status,
            }
        )
    return preview_rows

