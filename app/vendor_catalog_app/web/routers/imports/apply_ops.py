from __future__ import annotations

import re
from typing import Any


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _normalize_phone(value: str) -> str:
    return re.sub(r"[^0-9]", "", str(value or ""))


def _safe_float(value: Any) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9.\\-]", "", raw)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except Exception:
        return None


def _payload_value(payload: dict[str, Any], key: str) -> str:
    return str(payload.get(key) or "").strip()


class ImportApplyContext:
    def __init__(self, repo) -> None:
        self.repo = repo
        self._vendor_contact_keys: dict[str, set[str]] = {}
        self._vendor_owner_keys: dict[str, set[str]] = {}
        self._offering_owner_keys: dict[tuple[str, str], set[str]] = {}
        self._offering_contact_keys: dict[tuple[str, str], set[str]] = {}
        self._vendor_contract_number_keys: dict[str, set[str]] = {}
        self._offering_vendor_id_cache: dict[str, str] = {}

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

    def _load_vendor_owner_keys(self, vendor_id: str) -> set[str]:
        key = str(vendor_id or "").strip()
        if not key:
            return set()
        if key in self._vendor_owner_keys:
            return self._vendor_owner_keys[key]
        owner_keys: set[str] = set()
        try:
            rows = self.repo.get_vendor_business_owners(key).to_dict("records")
        except Exception:
            rows = []
        for row in rows:
            owner = str(row.get("owner_user_principal") or "").strip().lower()
            role = str(row.get("owner_role") or "business_owner").strip().lower() or "business_owner"
            if owner:
                owner_keys.add(f"{owner}|{role}")
        self._vendor_owner_keys[key] = owner_keys
        return owner_keys

    def _load_offering_owner_keys(self, *, vendor_id: str, offering_id: str) -> set[str]:
        vendor_key = str(vendor_id or "").strip()
        offering_key = str(offering_id or "").strip()
        cache_key = (vendor_key, offering_key)
        if not vendor_key or not offering_key:
            return set()
        if cache_key in self._offering_owner_keys:
            return self._offering_owner_keys[cache_key]
        owner_keys: set[str] = set()
        try:
            rows = self.repo.get_vendor_offering_business_owners(vendor_key).to_dict("records")
        except Exception:
            rows = []
        for row in rows:
            if str(row.get("offering_id") or "").strip() != offering_key:
                continue
            owner = str(row.get("owner_user_principal") or "").strip().lower()
            role = str(row.get("owner_role") or "business_owner").strip().lower() or "business_owner"
            if owner:
                owner_keys.add(f"{owner}|{role}")
        self._offering_owner_keys[cache_key] = owner_keys
        return owner_keys

    def _load_offering_contact_keys(self, *, vendor_id: str, offering_id: str) -> set[str]:
        vendor_key = str(vendor_id or "").strip()
        offering_key = str(offering_id or "").strip()
        cache_key = (vendor_key, offering_key)
        if not vendor_key or not offering_key:
            return set()
        if cache_key in self._offering_contact_keys:
            return self._offering_contact_keys[cache_key]
        contact_keys: set[str] = set()
        try:
            rows = self.repo.get_vendor_offering_contacts(vendor_key).to_dict("records")
        except Exception:
            rows = []
        for row in rows:
            if str(row.get("offering_id") or "").strip() != offering_key:
                continue
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
        self._offering_contact_keys[cache_key] = contact_keys
        return contact_keys

    def _load_vendor_contract_keys(self, vendor_id: str) -> set[str]:
        key = str(vendor_id or "").strip()
        if not key:
            return set()
        if key in self._vendor_contract_number_keys:
            return self._vendor_contract_number_keys[key]
        contract_keys: set[str] = set()
        try:
            rows = self.repo.get_vendor_contracts(key).to_dict("records")
        except Exception:
            rows = []
        for row in rows:
            contract_number = str(row.get("contract_number") or "").strip().lower()
            if contract_number:
                contract_keys.add(contract_number)
        self._vendor_contract_number_keys[key] = contract_keys
        return contract_keys

    def resolve_offering_vendor_id(self, offering_id: str) -> str:
        key = str(offering_id or "").strip()
        if not key:
            return ""
        if key in self._offering_vendor_id_cache:
            return self._offering_vendor_id_cache[key]
        vendor_id = ""
        try:
            rows = self.repo.get_offerings_by_ids([key])
            if not rows.empty:
                vendor_id = str(rows.iloc[0].to_dict().get("vendor_id") or "").strip()
        except Exception:
            vendor_id = ""
        self._offering_vendor_id_cache[key] = vendor_id
        return vendor_id

    def maybe_add_vendor_contact(
        self,
        *,
        vendor_id: str,
        full_name: str,
        contact_type: str,
        email: str,
        phone: str,
        actor_user_principal: str,
    ) -> str:
        key = str(vendor_id or "").strip()
        if not key or not hasattr(self.repo, "add_vendor_contact"):
            return ""
        resolved_name = str(full_name or "").strip()
        resolved_email = str(email or "").strip()
        resolved_phone = str(phone or "").strip()
        resolved_type = str(contact_type or "business").strip() or "business"
        if not any([resolved_name, resolved_email, resolved_phone]):
            return ""
        if not resolved_name:
            resolved_name = resolved_email or "Support Contact"

        normalized_email = _normalize_email(resolved_email)
        normalized_phone = _normalize_phone(resolved_phone)
        normalized_name = resolved_name.lower()
        contact_keys = self._load_vendor_contact_keys(key)
        if normalized_email and f"email:{normalized_email}" in contact_keys:
            return ""
        if normalized_phone and len(normalized_phone) >= 7 and f"phone:{normalized_phone}" in contact_keys:
            return ""
        if normalized_name and f"name_type:{normalized_name}|{resolved_type.lower()}" in contact_keys:
            return ""

        contact_id = self.repo.add_vendor_contact(
            vendor_id=key,
            full_name=resolved_name,
            contact_type=resolved_type,
            email=resolved_email or None,
            phone=resolved_phone or None,
            actor_user_principal=actor_user_principal,
        )
        if normalized_email:
            contact_keys.add(f"email:{normalized_email}")
        if normalized_phone and len(normalized_phone) >= 7:
            contact_keys.add(f"phone:{normalized_phone}")
        if normalized_name:
            contact_keys.add(f"name_type:{normalized_name}|{resolved_type.lower()}")
        return str(contact_id or "").strip()

    def maybe_add_vendor_support_contact(self, *, vendor_id: str, row_data: dict[str, str], actor_user_principal: str) -> str:
        return self.maybe_add_vendor_contact(
            vendor_id=vendor_id,
            full_name=str(row_data.get("support_contact_name") or "").strip(),
            contact_type=str(row_data.get("support_contact_type") or "business").strip() or "business",
            email=str(row_data.get("support_email") or "").strip(),
            phone=str(row_data.get("support_phone") or "").strip(),
            actor_user_principal=actor_user_principal,
        )

    def maybe_add_vendor_owner(
        self,
        *,
        vendor_id: str,
        owner_user_principal: str,
        owner_role: str,
        actor_user_principal: str,
    ) -> str:
        key = str(vendor_id or "").strip()
        owner = str(owner_user_principal or "").strip()
        role = str(owner_role or "business_owner").strip() or "business_owner"
        if not key or not owner or not hasattr(self.repo, "add_vendor_owner"):
            return ""
        owner_keys = self._load_vendor_owner_keys(key)
        dedupe_key = f"{owner.lower()}|{role.lower()}"
        if dedupe_key in owner_keys:
            return ""
        owner_id = self.repo.add_vendor_owner(
            vendor_id=key,
            owner_user_principal=owner,
            owner_role=role,
            actor_user_principal=actor_user_principal,
        )
        owner_keys.add(dedupe_key)
        return str(owner_id or "").strip()

    def maybe_add_offering_owner(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        owner_user_principal: str,
        owner_role: str,
        actor_user_principal: str,
    ) -> str:
        vendor_key = str(vendor_id or "").strip()
        offering_key = str(offering_id or "").strip()
        owner = str(owner_user_principal or "").strip()
        role = str(owner_role or "business_owner").strip() or "business_owner"
        if not vendor_key or not offering_key or not owner or not hasattr(self.repo, "add_offering_owner"):
            return ""
        owner_keys = self._load_offering_owner_keys(vendor_id=vendor_key, offering_id=offering_key)
        dedupe_key = f"{owner.lower()}|{role.lower()}"
        if dedupe_key in owner_keys:
            return ""
        owner_id = self.repo.add_offering_owner(
            vendor_id=vendor_key,
            offering_id=offering_key,
            owner_user_principal=owner,
            owner_role=role,
            actor_user_principal=actor_user_principal,
        )
        owner_keys.add(dedupe_key)
        return str(owner_id or "").strip()

    def maybe_add_offering_contact(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        full_name: str,
        contact_type: str,
        email: str,
        phone: str,
        actor_user_principal: str,
    ) -> str:
        vendor_key = str(vendor_id or "").strip()
        offering_key = str(offering_id or "").strip()
        if not vendor_key or not offering_key or not hasattr(self.repo, "add_offering_contact"):
            return ""
        resolved_name = str(full_name or "").strip()
        resolved_email = str(email or "").strip()
        resolved_phone = str(phone or "").strip()
        resolved_type = str(contact_type or "business").strip() or "business"
        if not any([resolved_name, resolved_email, resolved_phone]):
            return ""
        if not resolved_name:
            resolved_name = resolved_email or "Offering Contact"
        contact_keys = self._load_offering_contact_keys(vendor_id=vendor_key, offering_id=offering_key)
        normalized_email = _normalize_email(resolved_email)
        normalized_phone = _normalize_phone(resolved_phone)
        normalized_name = resolved_name.lower()
        if normalized_email and f"email:{normalized_email}" in contact_keys:
            return ""
        if normalized_phone and len(normalized_phone) >= 7 and f"phone:{normalized_phone}" in contact_keys:
            return ""
        if normalized_name and f"name_type:{normalized_name}|{resolved_type.lower()}" in contact_keys:
            return ""
        contact_id = self.repo.add_offering_contact(
            vendor_id=vendor_key,
            offering_id=offering_key,
            full_name=resolved_name,
            contact_type=resolved_type,
            email=resolved_email or None,
            phone=resolved_phone or None,
            actor_user_principal=actor_user_principal,
        )
        if normalized_email:
            contact_keys.add(f"email:{normalized_email}")
        if normalized_phone and len(normalized_phone) >= 7:
            contact_keys.add(f"phone:{normalized_phone}")
        if normalized_name:
            contact_keys.add(f"name_type:{normalized_name}|{resolved_type.lower()}")
        return str(contact_id or "").strip()

    def maybe_create_contract(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        contract_number: str,
        contract_status: str,
        start_date: str,
        end_date: str,
        annual_value: Any,
        actor_user_principal: str,
    ) -> str:
        vendor_key = str(vendor_id or "").strip()
        number = str(contract_number or "").strip()
        if not vendor_key or not number or not hasattr(self.repo, "create_contract"):
            return ""
        contract_keys = self._load_vendor_contract_keys(vendor_key)
        normalized_number = number.lower()
        if normalized_number in contract_keys:
            return ""
        contract_id = self.repo.create_contract(
            vendor_id=vendor_key,
            offering_id=str(offering_id or "").strip() or None,
            contract_number=number,
            contract_status=str(contract_status or "").strip() or "active",
            start_date=str(start_date or "").strip() or None,
            end_date=str(end_date or "").strip() or None,
            annual_value=_safe_float(annual_value),
            actor_user_principal=actor_user_principal,
        )
        contract_keys.add(normalized_number)
        return str(contract_id or "").strip()


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


def _search_vendor_id_by_name(repo, vendor_name: str) -> str:
    query = str(vendor_name or "").strip()
    if not query or not hasattr(repo, "search_vendors_typeahead"):
        return ""
    try:
        rows = repo.search_vendors_typeahead(q=query, limit=10).to_dict("records")
    except Exception:
        return ""
    lowered = query.lower()
    exact = [
        row
        for row in rows
        if str(row.get("vendor_id") or "").strip().lower() == lowered
        or str(row.get("display_name") or "").strip().lower() == lowered
        or str(row.get("legal_name") or "").strip().lower() == lowered
    ]
    if len(exact) == 1:
        return str(exact[0].get("vendor_id") or "").strip()
    if len(rows) == 1:
        return str(rows[0].get("vendor_id") or "").strip()
    return ""


def _resolve_vendor_id_for_financial_row(repo, *, row_data: dict[str, str], fallback_vendor_id: str = "") -> str:
    explicit_vendor_id = str(row_data.get("vendor_id") or "").strip() or str(fallback_vendor_id or "").strip()
    if explicit_vendor_id:
        return explicit_vendor_id
    vendor_name = str(row_data.get("vendor_name") or row_data.get("legal_name") or row_data.get("display_name") or "").strip()
    return _search_vendor_id_by_name(repo, vendor_name)


def _resolve_offering_id_for_financial_row(
    repo,
    *,
    row_data: dict[str, str],
    vendor_id: str,
    actor_user_principal: str,
    allow_create: bool,
) -> str:
    explicit_offering_id = str(row_data.get("offering_id") or "").strip()
    if explicit_offering_id and hasattr(repo, "get_offerings_by_ids"):
        try:
            existing = repo.get_offerings_by_ids([explicit_offering_id])
            if not existing.empty:
                return explicit_offering_id
        except Exception:
            pass

    offering_name = str(row_data.get("offering_name") or "").strip()
    if offering_name and hasattr(repo, "search_offerings_typeahead"):
        try:
            rows = repo.search_offerings_typeahead(vendor_id=vendor_id or None, q=offering_name, limit=10).to_dict("records")
        except Exception:
            rows = []
        lowered = offering_name.lower()
        exact = [
            row
            for row in rows
            if str(row.get("offering_id") or "").strip().lower() == lowered
            or str(row.get("offering_name") or "").strip().lower() == lowered
        ]
        if len(exact) == 1:
            return str(exact[0].get("offering_id") or "").strip()
        if len(rows) == 1:
            return str(rows[0].get("offering_id") or "").strip()

    if not allow_create or not vendor_id or not hasattr(repo, "create_offering"):
        return ""
    resolved_name = offering_name or "Imported Financial Feed"
    try:
        created_id = repo.create_offering(
            vendor_id=vendor_id,
            actor_user_principal=actor_user_principal,
            offering_name=resolved_name,
            offering_type="service",
            lob=None,
            service_type=None,
            lifecycle_state="draft",
            criticality_tier=None,
        )
    except Exception:
        return ""
    return str(created_id or "").strip()


def _find_invoice_candidate(
    repo,
    *,
    invoice_id: str,
    invoice_number: str,
    vendor_id: str,
    offering_id: str,
) -> dict[str, Any] | None:
    if hasattr(repo, "find_offering_invoice_candidates"):
        try:
            frame = repo.find_offering_invoice_candidates(
                invoice_id=invoice_id or None,
                invoice_number=invoice_number or None,
                vendor_id=vendor_id or None,
                offering_id=offering_id or None,
                limit=5,
            )
            if not frame.empty:
                return frame.iloc[0].to_dict()
        except Exception:
            return None
    if hasattr(repo, "list_offering_invoices") and vendor_id and offering_id and invoice_number:
        try:
            rows = repo.list_offering_invoices(vendor_id=vendor_id, offering_id=offering_id).to_dict("records")
        except Exception:
            rows = []
        invoice_lower = invoice_number.lower()
        for row in rows:
            if str(row.get("invoice_number") or "").strip().lower() == invoice_lower:
                return row
    return None


def _find_payment_candidate(
    repo,
    *,
    payment_reference: str,
    invoice_id: str,
    vendor_id: str,
    offering_id: str,
) -> dict[str, Any] | None:
    if not hasattr(repo, "find_offering_payment_candidates"):
        return None
    try:
        frame = repo.find_offering_payment_candidates(
            payment_reference=payment_reference or None,
            invoice_id=invoice_id or None,
            vendor_id=vendor_id or None,
            offering_id=offering_id or None,
            limit=5,
        )
        if frame.empty:
            return None
        return frame.iloc[0].to_dict()
    except Exception:
        return None


def _apply_invoice_payload(
    repo,
    *,
    row_data: dict[str, str],
    fallback_vendor_id: str,
    actor_user_principal: str,
) -> tuple[str, str, dict[str, str]]:
    invoice_id = str(row_data.get("invoice_id") or "").strip()
    invoice_number = str(row_data.get("invoice_number") or "").strip()
    invoice_date = str(row_data.get("invoice_date") or "").strip()
    amount = _safe_float(row_data.get("amount"))
    if not invoice_date:
        raise ValueError("invoice_date is required for invoice records.")
    if amount is None or amount <= 0:
        raise ValueError("amount must be greater than zero for invoice records.")
    vendor_id = _resolve_vendor_id_for_financial_row(repo, row_data=row_data, fallback_vendor_id=fallback_vendor_id)
    if not vendor_id:
        raise ValueError("Missing vendor dependency for invoice row.")
    offering_id = _resolve_offering_id_for_financial_row(
        repo,
        row_data=row_data,
        vendor_id=vendor_id,
        actor_user_principal=actor_user_principal,
        allow_create=True,
    )
    if not offering_id:
        raise ValueError("Missing offering dependency for invoice row.")

    existing = _find_invoice_candidate(
        repo,
        invoice_id=invoice_id,
        invoice_number=invoice_number,
        vendor_id=vendor_id,
        offering_id=offering_id,
    )
    if existing is not None:
        existing_id = str(existing.get("invoice_id") or "").strip()
        return (
            "merged",
            f"Invoice already exists: {existing_id}",
            {
                "entity_type": "invoice",
                "invoice_id": existing_id,
                "vendor_id": vendor_id,
                "offering_id": offering_id,
            },
        )

    if not hasattr(repo, "add_offering_invoice"):
        raise ValueError("Invoice writes are not supported in this runtime.")
    created_invoice_id = repo.add_offering_invoice(
        vendor_id=vendor_id,
        offering_id=offering_id,
        invoice_number=invoice_number or None,
        invoice_date=invoice_date,
        amount=float(amount),
        currency_code=str(row_data.get("currency_code") or "").strip() or "USD",
        invoice_status=str(row_data.get("invoice_status") or "").strip() or "received",
        notes=str(row_data.get("notes") or "").strip() or None,
        actor_user_principal=actor_user_principal,
    )
    return (
        "created",
        f"Invoice created: {created_invoice_id}",
        {
            "entity_type": "invoice",
            "invoice_id": str(created_invoice_id or "").strip(),
            "vendor_id": vendor_id,
            "offering_id": offering_id,
        },
    )


def _apply_payment_payload(
    repo,
    *,
    row_data: dict[str, str],
    fallback_vendor_id: str,
    actor_user_principal: str,
) -> tuple[str, str, dict[str, str]]:
    payment_date = str(row_data.get("payment_date") or "").strip()
    amount = _safe_float(row_data.get("amount"))
    if not payment_date:
        raise ValueError("payment_date is required for payment records.")
    if amount is None or amount <= 0:
        raise ValueError("amount must be greater than zero for payment records.")
    vendor_id = _resolve_vendor_id_for_financial_row(repo, row_data=row_data, fallback_vendor_id=fallback_vendor_id)
    offering_id = _resolve_offering_id_for_financial_row(
        repo,
        row_data=row_data,
        vendor_id=vendor_id,
        actor_user_principal=actor_user_principal,
        allow_create=False,
    )
    invoice_id = str(row_data.get("invoice_id") or "").strip()
    invoice_number = str(row_data.get("invoice_number") or "").strip()
    invoice_candidate = _find_invoice_candidate(
        repo,
        invoice_id=invoice_id,
        invoice_number=invoice_number,
        vendor_id=vendor_id,
        offering_id=offering_id,
    )
    if invoice_candidate is None:
        raise ValueError("Missing invoice dependency for payment row.")
    resolved_invoice_id = str(invoice_candidate.get("invoice_id") or "").strip()
    resolved_vendor_id = str(invoice_candidate.get("vendor_id") or "").strip() or vendor_id
    resolved_offering_id = str(invoice_candidate.get("offering_id") or "").strip() or offering_id

    payment_reference = str(row_data.get("payment_reference") or row_data.get("payment_id") or "").strip()
    existing = _find_payment_candidate(
        repo,
        payment_reference=payment_reference,
        invoice_id=resolved_invoice_id,
        vendor_id=resolved_vendor_id,
        offering_id=resolved_offering_id,
    )
    if existing is not None:
        existing_id = str(existing.get("payment_id") or "").strip()
        return (
            "merged",
            f"Payment already exists: {existing_id}",
            {
                "entity_type": "payment",
                "payment_id": existing_id,
                "invoice_id": resolved_invoice_id,
                "vendor_id": resolved_vendor_id,
                "offering_id": resolved_offering_id,
            },
        )

    if not hasattr(repo, "add_offering_payment"):
        raise ValueError("Payment writes are not supported in this runtime.")
    created_payment_id = repo.add_offering_payment(
        vendor_id=resolved_vendor_id,
        offering_id=resolved_offering_id,
        invoice_id=resolved_invoice_id,
        payment_reference=payment_reference or None,
        payment_date=payment_date,
        amount=float(amount),
        currency_code=str(row_data.get("currency_code") or "").strip() or "USD",
        payment_status=str(row_data.get("payment_status") or "").strip() or "settled",
        notes=str(row_data.get("notes") or "").strip() or None,
        actor_user_principal=actor_user_principal,
    )
    return (
        "created",
        f"Payment created: {created_payment_id}",
        {
            "entity_type": "payment",
            "payment_id": str(created_payment_id or "").strip(),
            "invoice_id": resolved_invoice_id,
            "vendor_id": resolved_vendor_id,
            "offering_id": resolved_offering_id,
        },
    )


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
) -> tuple[str, str, dict[str, str]]:
    selected_action = str(action or "").strip().lower()
    if selected_action == "skip":
        return "skipped", "Skipped by user.", {}

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
                return (
                    "created",
                    f"Vendor created: {created_vendor_id} (support contact: {contact_id})",
                    {"entity_type": "vendor", "vendor_id": str(created_vendor_id or "").strip()},
                )
            return (
                "created",
                f"Vendor created: {created_vendor_id}",
                {"entity_type": "vendor", "vendor_id": str(created_vendor_id or "").strip()},
            )

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
            return (
                "merged",
                f"Vendor merged: {target_id} (support contact: {contact_id})",
                {"entity_type": "vendor", "vendor_id": str(target_id or "").strip()},
            )
        return (
            "merged",
            f"Vendor merged: {target_id}",
            {"entity_type": "vendor", "vendor_id": str(target_id or "").strip()},
        )

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
            return (
                "created",
                f"Offering created: {created_offering_id}",
                {
                    "entity_type": "offering",
                    "vendor_id": vendor_id,
                    "offering_id": str(created_offering_id or "").strip(),
                },
            )

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
        return (
            "merged",
            f"Offering merged: {target_id}",
            {
                "entity_type": "offering",
                "vendor_id": str(target_vendor_id or "").strip(),
                "offering_id": str(target_id or "").strip(),
            },
        )

    if layout_key == "invoices":
        if selected_action == "merge" and target_id:
            return (
                "merged",
                f"Invoice retained: {target_id}",
                {"entity_type": "invoice", "invoice_id": str(target_id or "").strip()},
            )
        return _apply_invoice_payload(
            repo,
            row_data=row_data,
            fallback_vendor_id=fallback_target_vendor_id,
            actor_user_principal=actor_user_principal,
        )

    if layout_key == "payments":
        if selected_action == "merge" and target_id:
            return (
                "merged",
                f"Payment retained: {target_id}",
                {"entity_type": "payment", "payment_id": str(target_id or "").strip()},
            )
        return _apply_payment_payload(
            repo,
            row_data=row_data,
            fallback_vendor_id=fallback_target_vendor_id,
            actor_user_principal=actor_user_principal,
        )

    if selected_action == "new":
        project_name = str(row_data.get("project_name") or "").strip()
        if not project_name:
            raise ValueError("project_name is required for new project records.")
        resolved_vendor_id = str(row_data.get("vendor_id") or "").strip() or None
        created_project_id = repo.create_project(
            vendor_id=resolved_vendor_id,
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
        return (
            "created",
            f"Project created: {created_project_id}",
            {
                "entity_type": "project",
                "vendor_id": str(resolved_vendor_id or "").strip(),
                "project_id": str(created_project_id or "").strip(),
            },
        )

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
    return (
        "merged",
        f"Project merged: {target_id}",
        {
            "entity_type": "project",
            "vendor_id": str(target_vendor_id or "").strip(),
            "project_id": str(target_id or "").strip(),
        },
    )


def apply_stage_area_rows_for_row(
    repo,
    *,
    stage_area_rows: dict[str, list[dict[str, Any]]],
    row_index: int,
    selected_action: str,
    row_data: dict[str, str],
    fallback_target_vendor_id: str,
    primary_result: dict[str, str],
    actor_user_principal: str,
    reason: str,
    apply_context: ImportApplyContext,
) -> dict[str, int]:
    action = str(selected_action or "").strip().lower()
    if action == "skip":
        return {}

    row_line = int(row_index or 0)
    area_rows_by_area: dict[str, list[dict[str, Any]]] = {}
    for area, rows in dict(stage_area_rows or {}).items():
        selected_rows = [dict(item) for item in list(rows or []) if int(item.get("row_index") or 0) == row_line]
        if selected_rows:
            area_rows_by_area[str(area)] = selected_rows
    if not area_rows_by_area:
        return {}

    resolved_vendor_id = (
        str(primary_result.get("vendor_id") or "").strip()
        or str(row_data.get("vendor_id") or "").strip()
        or str(fallback_target_vendor_id or "").strip()
    )
    primary_offering_id = str(primary_result.get("offering_id") or "").strip()
    child_counts: dict[str, int] = {}
    created_offering_ids: list[str] = []
    created_offering_id_by_group: dict[str, str] = {}

    for area_row in area_rows_by_area.get("offering", []):
        payload = dict(area_row.get("payload") or {})
        group_key = str(area_row.get("source_group_key") or "__static__")
        explicit_offering_id = _payload_value(payload, "offering_id")
        offering_vendor_id = _payload_value(payload, "vendor_id") or resolved_vendor_id
        if explicit_offering_id:
            if not hasattr(repo, "get_offerings_by_ids"):
                continue
            existing = repo.get_offerings_by_ids([explicit_offering_id])
            if existing.empty:
                continue
            existing_vendor_id = str(existing.iloc[0].to_dict().get("vendor_id") or "").strip()
            if not offering_vendor_id:
                offering_vendor_id = existing_vendor_id
            updates = _offering_updates_from_row(payload)
            if updates and hasattr(repo, "update_offering_fields") and offering_vendor_id:
                repo.update_offering_fields(
                    vendor_id=offering_vendor_id,
                    offering_id=explicit_offering_id,
                    actor_user_principal=actor_user_principal,
                    updates=updates,
                    reason=reason or "bulk import",
                )
                child_counts["offering"] = child_counts.get("offering", 0) + 1
            created_offering_id_by_group[group_key] = explicit_offering_id
            continue
        offering_name = _payload_value(payload, "offering_name")
        if not offering_name:
            continue
        if not offering_vendor_id:
            raise ValueError("Could not resolve vendor_id for mapped offering row.")
        if not hasattr(repo, "create_offering"):
            continue
        created_offering_id = repo.create_offering(
            vendor_id=offering_vendor_id,
            actor_user_principal=actor_user_principal,
            offering_name=offering_name,
            offering_type=_payload_value(payload, "offering_type") or None,
            lob=_payload_value(payload, "lob") or None,
            service_type=_payload_value(payload, "service_type") or None,
            lifecycle_state=_payload_value(payload, "lifecycle_state") or "draft",
            criticality_tier=_payload_value(payload, "criticality_tier") or None,
        )
        created_key = str(created_offering_id or "").strip()
        if created_key:
            created_offering_ids.append(created_key)
            created_offering_id_by_group[group_key] = created_key
            child_counts["offering"] = child_counts.get("offering", 0) + 1

    def resolve_offering_id(payload: dict[str, Any], group_key: str) -> str:
        explicit = _payload_value(payload, "offering_id")
        if explicit:
            return explicit
        mapped = str(created_offering_id_by_group.get(group_key) or "").strip()
        if mapped:
            return mapped
        if primary_offering_id:
            return primary_offering_id
        if len(created_offering_ids) == 1:
            return created_offering_ids[0]
        return ""

    def resolve_vendor_id(*, payload: dict[str, Any], offering_id: str) -> str:
        explicit_vendor_id = _payload_value(payload, "vendor_id")
        if explicit_vendor_id:
            return explicit_vendor_id
        if resolved_vendor_id:
            return resolved_vendor_id
        if offering_id:
            return apply_context.resolve_offering_vendor_id(offering_id)
        return ""

    for area_row in area_rows_by_area.get("vendor_owner", []):
        payload = dict(area_row.get("payload") or {})
        vendor_id = resolve_vendor_id(payload=payload, offering_id="")
        owner_user_principal = _payload_value(payload, "owner_user_principal")
        owner_role = _payload_value(payload, "owner_role") or "business_owner"
        owner_id = apply_context.maybe_add_vendor_owner(
            vendor_id=vendor_id,
            owner_user_principal=owner_user_principal,
            owner_role=owner_role,
            actor_user_principal=actor_user_principal,
        )
        if owner_id:
            child_counts["vendor_owner"] = child_counts.get("vendor_owner", 0) + 1

    for area_row in area_rows_by_area.get("vendor_contact", []):
        payload = dict(area_row.get("payload") or {})
        vendor_id = resolve_vendor_id(payload=payload, offering_id="")
        contact_id = apply_context.maybe_add_vendor_contact(
            vendor_id=vendor_id,
            full_name=_payload_value(payload, "full_name"),
            contact_type=_payload_value(payload, "contact_type") or "business",
            email=_payload_value(payload, "email"),
            phone=_payload_value(payload, "phone"),
            actor_user_principal=actor_user_principal,
        )
        if contact_id:
            child_counts["vendor_contact"] = child_counts.get("vendor_contact", 0) + 1

    for area_row in area_rows_by_area.get("offering_owner", []):
        payload = dict(area_row.get("payload") or {})
        group_key = str(area_row.get("source_group_key") or "__static__")
        offering_id = resolve_offering_id(payload, group_key)
        vendor_id = resolve_vendor_id(payload=payload, offering_id=offering_id)
        owner_user_principal = _payload_value(payload, "owner_user_principal")
        owner_role = _payload_value(payload, "owner_role") or "business_owner"
        owner_id = apply_context.maybe_add_offering_owner(
            vendor_id=vendor_id,
            offering_id=offering_id,
            owner_user_principal=owner_user_principal,
            owner_role=owner_role,
            actor_user_principal=actor_user_principal,
        )
        if owner_id:
            child_counts["offering_owner"] = child_counts.get("offering_owner", 0) + 1

    for area_row in area_rows_by_area.get("offering_contact", []):
        payload = dict(area_row.get("payload") or {})
        group_key = str(area_row.get("source_group_key") or "__static__")
        offering_id = resolve_offering_id(payload, group_key)
        vendor_id = resolve_vendor_id(payload=payload, offering_id=offering_id)
        contact_id = apply_context.maybe_add_offering_contact(
            vendor_id=vendor_id,
            offering_id=offering_id,
            full_name=_payload_value(payload, "full_name"),
            contact_type=_payload_value(payload, "contact_type") or "business",
            email=_payload_value(payload, "email"),
            phone=_payload_value(payload, "phone"),
            actor_user_principal=actor_user_principal,
        )
        if contact_id:
            child_counts["offering_contact"] = child_counts.get("offering_contact", 0) + 1

    for area_row in area_rows_by_area.get("contract", []):
        payload = dict(area_row.get("payload") or {})
        group_key = str(area_row.get("source_group_key") or "__static__")
        offering_id = resolve_offering_id(payload, group_key)
        vendor_id = resolve_vendor_id(payload=payload, offering_id=offering_id)
        contract_number = _payload_value(payload, "contract_number")
        if not contract_number:
            continue
        contract_status = _payload_value(payload, "contract_status") or "active"
        contract_id = apply_context.maybe_create_contract(
            vendor_id=vendor_id,
            offering_id=offering_id,
            contract_number=contract_number,
            contract_status=contract_status,
            start_date=_payload_value(payload, "start_date"),
            end_date=_payload_value(payload, "end_date"),
            annual_value=_payload_value(payload, "annual_value"),
            actor_user_principal=actor_user_principal,
        )
        if contract_id:
            child_counts["contract"] = child_counts.get("contract", 0) + 1

    for area_row in area_rows_by_area.get("project", []):
        payload = dict(area_row.get("payload") or {})
        project_id = _payload_value(payload, "project_id")
        project_vendor_id = resolve_vendor_id(payload=payload, offering_id="")
        if project_id and hasattr(repo, "get_project_by_id") and hasattr(repo, "update_project"):
            existing = repo.get_project_by_id(project_id)
            if existing is not None:
                updates = _project_updates_from_row(payload)
                if updates or project_vendor_id:
                    repo.update_project(
                        vendor_id=project_vendor_id or None,
                        project_id=project_id,
                        actor_user_principal=actor_user_principal,
                        updates=updates,
                        vendor_ids=([project_vendor_id] if project_vendor_id else None),
                        linked_offering_ids=None,
                        reason=reason or "bulk import",
                    )
                    child_counts["project"] = child_counts.get("project", 0) + 1
                continue
        project_name = _payload_value(payload, "project_name")
        if not project_name or not hasattr(repo, "create_project"):
            continue
        created_project_id = repo.create_project(
            vendor_id=project_vendor_id or None,
            actor_user_principal=actor_user_principal,
            project_name=project_name,
            project_type=_payload_value(payload, "project_type") or None,
            status=_payload_value(payload, "status") or "draft",
            start_date=_payload_value(payload, "start_date") or None,
            target_date=_payload_value(payload, "target_date") or None,
            owner_principal=_payload_value(payload, "owner_principal") or None,
            description=_payload_value(payload, "description") or None,
            linked_offering_ids=[],
        )
        if str(created_project_id or "").strip():
            child_counts["project"] = child_counts.get("project", 0) + 1

    for area_row in area_rows_by_area.get("invoice", []):
        payload = dict(area_row.get("payload") or {})
        payload_vendor_id = _payload_value(payload, "vendor_id") or resolved_vendor_id
        try:
            status, _message, _result = _apply_invoice_payload(
                repo,
                row_data={str(k): str(v or "") for k, v in payload.items()},
                fallback_vendor_id=payload_vendor_id,
                actor_user_principal=actor_user_principal,
            )
        except Exception:
            continue
        if status in {"created", "merged"}:
            child_counts["invoice"] = child_counts.get("invoice", 0) + 1

    for area_row in area_rows_by_area.get("payment", []):
        payload = dict(area_row.get("payload") or {})
        payload_vendor_id = _payload_value(payload, "vendor_id") or resolved_vendor_id
        try:
            status, _message, _result = _apply_payment_payload(
                repo,
                row_data={str(k): str(v or "") for k, v in payload.items()},
                fallback_vendor_id=payload_vendor_id,
                actor_user_principal=actor_user_principal,
            )
        except Exception:
            continue
        if status in {"created", "merged"}:
            child_counts["payment"] = child_counts.get("payment", 0) + 1

    return {k: int(v) for k, v in child_counts.items() if int(v or 0) > 0}
