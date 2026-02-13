from __future__ import annotations

import re
from typing import Any


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _normalize_phone(value: str) -> str:
    return re.sub(r"[^0-9]", "", str(value or ""))


class ImportApplyContext:
    def __init__(self, repo) -> None:
        self.repo = repo
        self._vendor_contact_keys: dict[str, set[str]] = {}

    def _load_vendor_contact_keys(self, vendor_id: str) -> set[str]:
        key = str(vendor_id or "").strip()
        if not key:
            return set()
        if key in self._vendor_contact_keys:
            return self._vendor_contact_keys[key]
        contact_keys: set[str] = set()
        try:
            rows = self.repo.get_vendor_contacts(key).to_dict("records")
        except Exception:
            rows = []
        for row in rows:
            email = _normalize_email(str(row.get("email") or ""))
            phone = _normalize_phone(str(row.get("phone") or ""))
            full_name = str(row.get("full_name") or "").strip().lower()
            contact_type = str(row.get("contact_type") or "business").strip().lower() or "business"
            if email:
                contact_keys.add(f"email:{email}")
            if len(phone) >= 7:
                contact_keys.add(f"phone:{phone}")
            if full_name:
                contact_keys.add(f"name_type:{full_name}|{contact_type}")
        self._vendor_contact_keys[key] = contact_keys
        return contact_keys

    def maybe_add_vendor_support_contact(self, *, vendor_id: str, row_data: dict[str, str], actor_user_principal: str) -> str:
        key = str(vendor_id or "").strip()
        if not key:
            return ""
        full_name = str(row_data.get("support_contact_name") or "").strip()
        contact_type = str(row_data.get("support_contact_type") or "business").strip() or "business"
        email = str(row_data.get("support_email") or "").strip()
        phone = str(row_data.get("support_phone") or "").strip()
        if not any([full_name, email, phone]):
            return ""
        if not full_name:
            full_name = "Support Contact"

        normalized_email = _normalize_email(email)
        normalized_phone = _normalize_phone(phone)
        normalized_name = full_name.lower()
        contact_keys = self._load_vendor_contact_keys(key)
        duplicate = False
        if normalized_email and f"email:{normalized_email}" in contact_keys:
            duplicate = True
        if normalized_phone and len(normalized_phone) >= 7 and f"phone:{normalized_phone}" in contact_keys:
            duplicate = True
        if normalized_name and f"name_type:{normalized_name}|{contact_type.lower()}" in contact_keys:
            duplicate = True
        if duplicate:
            return ""

        contact_id = self.repo.add_vendor_contact(
            vendor_id=key,
            full_name=full_name,
            contact_type=contact_type,
            email=email or None,
            phone=phone or None,
            actor_user_principal=actor_user_principal,
        )
        if normalized_email:
            contact_keys.add(f"email:{normalized_email}")
        if normalized_phone and len(normalized_phone) >= 7:
            contact_keys.add(f"phone:{normalized_phone}")
        if normalized_name:
            contact_keys.add(f"name_type:{normalized_name}|{contact_type.lower()}")
        return str(contact_id or "").strip()


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


def apply_import_row(
    repo,
    *,
    layout_key: str,
    row_data: dict[str, str],
    action: str,
    target_id: str,
    fallback_target_vendor_id: str,
    actor_user_principal: str,
    reason: str,
    apply_context: ImportApplyContext,
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
            contact_id = apply_context.maybe_add_vendor_support_contact(
                vendor_id=created_vendor_id,
                row_data=row_data,
                actor_user_principal=actor_user_principal,
            )
            if contact_id:
                return "created", f"Vendor created: {created_vendor_id} (support contact: {contact_id})"
            return "created", f"Vendor created: {created_vendor_id}"

        if not target_id:
            raise ValueError("Target vendor_id is required for merge.")
        updates = _vendor_updates_from_row(row_data)
        contact_id = ""
        if updates:
            repo.apply_vendor_profile_update(
                vendor_id=target_id,
                actor_user_principal=actor_user_principal,
                updates=updates,
                reason=reason,
            )
        contact_id = apply_context.maybe_add_vendor_support_contact(
            vendor_id=target_id,
            row_data=row_data,
            actor_user_principal=actor_user_principal,
        )
        if not updates and not contact_id:
            raise ValueError("No merge updates were provided for vendor row.")
        if contact_id:
            return "merged", f"Vendor merged: {target_id} (support contact: {contact_id})"
        return "merged", f"Vendor merged: {target_id}"

    if layout_key == "offerings":
        if selected_action == "new":
            vendor_id = str(row_data.get("vendor_id") or "").strip() or str(fallback_target_vendor_id or "").strip()
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
