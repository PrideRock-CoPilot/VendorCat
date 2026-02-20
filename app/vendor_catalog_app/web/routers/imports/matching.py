from __future__ import annotations

import re
from typing import Any


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _email_domain(value: str) -> str:
    normalized = _normalize_email(value)
    if "@" not in normalized:
        return ""
    return normalized.split("@", 1)[1].strip()


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    return digits


def _phone_suffix(value: str, size: int = 7) -> str:
    digits = _normalize_phone(value)
    if len(digits) < size:
        return ""
    return digits[-size:]


def _label_for_vendor_row(row: dict[str, Any]) -> str:
    vendor_id = str(row.get("vendor_id") or "").strip()
    display_name = str(row.get("display_name") or row.get("legal_name") or vendor_id).strip()
    return display_name or vendor_id


def _label_for_offering_row(row: dict[str, Any]) -> str:
    offering_id = str(row.get("offering_id") or "").strip()
    offering_name = str(row.get("offering_name") or offering_id).strip()
    return offering_name or offering_id


def _label_for_project_row(row: dict[str, Any]) -> str:
    project_id = str(row.get("project_id") or "").strip()
    project_name = str(row.get("project_name") or project_id).strip()
    return project_name or project_id


def _label_for_invoice_row(row: dict[str, Any]) -> str:
    invoice_id = str(row.get("invoice_id") or "").strip()
    invoice_number = str(row.get("invoice_number") or invoice_id).strip()
    return invoice_number or invoice_id


def _label_for_payment_row(row: dict[str, Any]) -> str:
    payment_id = str(row.get("payment_id") or "").strip()
    payment_reference = str(row.get("payment_reference") or payment_id).strip()
    return payment_reference or payment_id


class ImportMatchContext:
    def __init__(self, repo) -> None:
        self.repo = repo
        self._vendor_profile_cache: dict[str, dict[str, Any] | None] = {}
        self._offering_cache: dict[str, dict[str, Any] | None] = {}
        self._project_cache: dict[str, dict[str, Any] | None] = {}
        self._invoice_search_cache: dict[tuple[str, str, str, str, int], list[dict[str, Any]]] = {}
        self._vendor_search_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
        self._offering_search_cache: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
        self._project_search_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
        self._contact_maps_loaded = False
        self._vendor_ids_by_email: dict[str, set[str]] = {}
        self._vendor_ids_by_email_domain: dict[str, set[str]] = {}
        self._vendor_ids_by_phone: dict[str, set[str]] = {}
        self._vendor_ids_by_phone_suffix: dict[str, set[str]] = {}

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

    def search_invoices(
        self,
        *,
        invoice_id: str,
        invoice_number: str,
        vendor_id: str,
        offering_id: str,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        if not hasattr(self.repo, "find_offering_invoice_candidates"):
            return []
        lookup = (
            str(invoice_id or "").strip().lower(),
            str(invoice_number or "").strip().lower(),
            str(vendor_id or "").strip().lower(),
            str(offering_id or "").strip().lower(),
            int(limit),
        )
        if lookup in self._invoice_search_cache:
            return self._invoice_search_cache[lookup]
        rows = self.repo.find_offering_invoice_candidates(
            invoice_id=invoice_id or None,
            invoice_number=invoice_number or None,
            vendor_id=vendor_id or None,
            offering_id=offering_id or None,
            limit=limit,
        ).to_dict("records")
        self._invoice_search_cache[lookup] = rows
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
            email_domain = _email_domain(email)
            phone = _normalize_phone(str(row.get("phone") or ""))
            phone_suffix = _phone_suffix(phone, size=7)
            if email:
                self._vendor_ids_by_email.setdefault(email, set()).add(vendor_id)
            if email_domain:
                self._vendor_ids_by_email_domain.setdefault(email_domain, set()).add(vendor_id)
            if len(phone) >= 7:
                self._vendor_ids_by_phone.setdefault(phone, set()).add(vendor_id)
            if phone_suffix:
                self._vendor_ids_by_phone_suffix.setdefault(phone_suffix, set()).add(vendor_id)

    def _vendor_label(self, vendor_id: str) -> str:
        existing = self.vendor_profile(vendor_id) or {"vendor_id": vendor_id}
        return _label_for_vendor_row(existing)

    @staticmethod
    def _stable_ids(ids: set[str]) -> list[str]:
        return sorted([str(v or "").strip() for v in ids if str(v or "").strip()])

    def match_vendor_by_contact(self, *, email: str, phone: str) -> tuple[str, str]:
        self._load_contact_maps()
        normalized_email = _normalize_email(email)
        domain = _email_domain(normalized_email)
        normalized_phone = _normalize_phone(phone)
        phone_tail = _phone_suffix(normalized_phone, size=7)
        email_matches = self._vendor_ids_by_email.get(normalized_email, set()) if normalized_email else set()
        email_domain_matches = self._vendor_ids_by_email_domain.get(domain, set()) if domain else set()
        phone_matches = self._vendor_ids_by_phone.get(normalized_phone, set()) if len(normalized_phone) >= 7 else set()
        phone_tail_matches = self._vendor_ids_by_phone_suffix.get(phone_tail, set()) if phone_tail else set()

        if normalized_email and len(email_matches) == 1:
            return next(iter(email_matches)), "Matched vendor via support/contact email."
        if normalized_phone and len(phone_matches) == 1:
            return next(iter(phone_matches)), "Matched vendor via support/contact phone."
        if domain and len(email_domain_matches) == 1:
            return next(iter(email_domain_matches)), "Matched vendor via support/contact email domain."
        if phone_tail and len(phone_tail_matches) == 1:
            return next(iter(phone_tail_matches)), "Matched vendor via support/contact phone suffix."
        if normalized_email and len(email_matches) > 1:
            return "", "Support/contact email matched multiple vendors."
        if normalized_phone and len(phone_matches) > 1:
            return "", "Support/contact phone matched multiple vendors."
        if domain and len(email_domain_matches) > 1:
            return "", "Support/contact email domain matched multiple vendors."
        if phone_tail and len(phone_tail_matches) > 1:
            return "", "Support/contact phone suffix matched multiple vendors."
        return "", ""

    def candidate_vendors_by_contact(self, *, email: str, phone: str) -> tuple[list[dict[str, str]], list[str]]:
        self._load_contact_maps()
        normalized_email = _normalize_email(email)
        domain = _email_domain(normalized_email)
        normalized_phone = _normalize_phone(phone)
        phone_tail = _phone_suffix(normalized_phone, size=7)

        notes: list[str] = []
        ranked_ids: list[str] = []
        seen: set[str] = set()

        def add_ids(ids: set[str], reason: str) -> None:
            stable = self._stable_ids(ids)
            if not stable:
                return
            if len(stable) == 1:
                notes.append(reason)
            else:
                notes.append(f"{reason} ({len(stable)} candidates)")
            for item in stable:
                if item in seen:
                    continue
                seen.add(item)
                ranked_ids.append(item)

        if normalized_email:
            add_ids(self._vendor_ids_by_email.get(normalized_email, set()), "Exact support/contact email match")
        if normalized_phone and len(normalized_phone) >= 7:
            add_ids(self._vendor_ids_by_phone.get(normalized_phone, set()), "Exact support/contact phone match")
        if domain:
            add_ids(self._vendor_ids_by_email_domain.get(domain, set()), "Support/contact email domain match")
        if phone_tail:
            add_ids(self._vendor_ids_by_phone_suffix.get(phone_tail, set()), "Support/contact phone suffix match")

        options = [{"id": vendor_id, "label": self._vendor_label(vendor_id)} for vendor_id in ranked_ids[:12]]
        return options, notes


def _suggest_vendor_match(repo, row_data: dict[str, str], ctx: ImportMatchContext) -> tuple[str, str, list[str]]:
    notes: list[str] = []
    explicit_vendor_id = str(row_data.get("vendor_id") or "").strip()
    if explicit_vendor_id:
        existing = ctx.vendor_profile(explicit_vendor_id)
        if existing is not None:
            return explicit_vendor_id, _label_for_vendor_row(existing), notes
        notes.append(f"vendor_id '{explicit_vendor_id}' was not found.")

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


def _append_option(options: list[dict[str, str]], *, target_id: str, label: str) -> None:
    item_id = str(target_id or "").strip()
    if not item_id:
        return
    if any(str(existing.get("id") or "").strip() == item_id for existing in options):
        return
    options.append({"id": item_id, "label": str(label or item_id).strip() or item_id})


def _collect_vendor_merge_options(
    *,
    row_data: dict[str, str],
    ctx: ImportMatchContext,
    suggested_target_id: str,
    suggested_target_label: str,
) -> tuple[list[dict[str, str]], list[str]]:
    options: list[dict[str, str]] = []
    notes: list[str] = []
    _append_option(options, target_id=suggested_target_id, label=suggested_target_label)

    explicit_vendor_id = str(row_data.get("vendor_id") or "").strip()
    if explicit_vendor_id:
        existing = ctx.vendor_profile(explicit_vendor_id)
        if existing is not None:
            _append_option(
                options,
                target_id=str(existing.get("vendor_id") or "").strip(),
                label=_label_for_vendor_row(existing),
            )

    for query in (
        str(row_data.get("legal_name") or "").strip(),
        str(row_data.get("display_name") or "").strip(),
        str(row_data.get("vendor_name") or "").strip(),
    ):
        if not query:
            continue
        for candidate in ctx.search_vendors(q=query, limit=12):
            _append_option(
                options,
                target_id=str(candidate.get("vendor_id") or "").strip(),
                label=_label_for_vendor_row(candidate),
            )

    contact_options, contact_notes = ctx.candidate_vendors_by_contact(
        email=str(row_data.get("support_email") or row_data.get("vendor_contact_email") or "").strip(),
        phone=str(row_data.get("support_phone") or row_data.get("vendor_support_phone") or "").strip(),
    )
    notes.extend(contact_notes)
    for option in contact_options:
        _append_option(
            options,
            target_id=str(option.get("id") or "").strip(),
            label=str(option.get("label") or "").strip(),
        )
    return options[:15], notes


def _collect_offering_merge_options(
    *,
    row_data: dict[str, str],
    ctx: ImportMatchContext,
    suggested_target_id: str,
    suggested_target_label: str,
) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    _append_option(options, target_id=suggested_target_id, label=suggested_target_label)

    explicit_offering_id = str(row_data.get("offering_id") or "").strip()
    if explicit_offering_id:
        existing = ctx.offering_by_id(explicit_offering_id)
        if existing is not None:
            _append_option(
                options,
                target_id=str(existing.get("offering_id") or "").strip(),
                label=_label_for_offering_row(existing),
            )

    query = str(row_data.get("offering_name") or "").strip()
    vendor_id = str(row_data.get("vendor_id") or "").strip()
    if query:
        for candidate in ctx.search_offerings(vendor_id=vendor_id or None, q=query, limit=12):
            _append_option(
                options,
                target_id=str(candidate.get("offering_id") or "").strip(),
                label=_label_for_offering_row(candidate),
            )
    return options[:15]


def _collect_project_merge_options(
    *,
    row_data: dict[str, str],
    ctx: ImportMatchContext,
    suggested_target_id: str,
    suggested_target_label: str,
) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    _append_option(options, target_id=suggested_target_id, label=suggested_target_label)

    explicit_project_id = str(row_data.get("project_id") or "").strip()
    if explicit_project_id:
        existing = ctx.project_by_id(explicit_project_id)
        if existing:
            _append_option(
                options,
                target_id=str(existing.get("project_id") or "").strip(),
                label=_label_for_project_row(existing),
            )

    query = str(row_data.get("project_name") or "").strip()
    vendor_filter = str(row_data.get("vendor_id") or "").strip()
    if query:
        candidates = ctx.search_projects(q=query, limit=12)
        for candidate in candidates:
            if vendor_filter and str(candidate.get("vendor_id") or "").strip() != vendor_filter:
                continue
            _append_option(
                options,
                target_id=str(candidate.get("project_id") or "").strip(),
                label=_label_for_project_row(candidate),
            )
    return options[:15]


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


def _resolve_vendor_by_name(row_data: dict[str, str], ctx: ImportMatchContext) -> tuple[str, list[str]]:
    notes: list[str] = []
    explicit_vendor_id = str(row_data.get("vendor_id") or "").strip()
    if explicit_vendor_id:
        if ctx.vendor_profile(explicit_vendor_id) is not None:
            return explicit_vendor_id, notes
        notes.append(f"vendor_id '{explicit_vendor_id}' was not found.")

    vendor_name = str(row_data.get("vendor_name") or row_data.get("legal_name") or row_data.get("display_name") or "").strip()
    if not vendor_name:
        return "", notes
    candidates = ctx.search_vendors(q=vendor_name, limit=10)
    lowered = vendor_name.lower()
    exact = [
        row
        for row in candidates
        if str(row.get("vendor_id") or "").strip().lower() == lowered
        or str(row.get("display_name") or "").strip().lower() == lowered
        or str(row.get("legal_name") or "").strip().lower() == lowered
    ]
    if len(exact) == 1:
        notes.append("Inferred vendor from vendor_name.")
        return str(exact[0].get("vendor_id") or "").strip(), notes
    if len(candidates) == 1:
        notes.append("Single near-match found for vendor_name.")
        return str(candidates[0].get("vendor_id") or "").strip(), notes
    if len(candidates) > 1:
        notes.append("vendor_name matched multiple vendors.")
    return "", notes


def _resolve_offering_for_invoice(row_data: dict[str, str], *, vendor_id: str, ctx: ImportMatchContext) -> tuple[str, list[str]]:
    notes: list[str] = []
    explicit_offering_id = str(row_data.get("offering_id") or "").strip()
    if explicit_offering_id:
        existing = ctx.offering_by_id(explicit_offering_id)
        if existing is not None:
            return explicit_offering_id, notes
        notes.append(f"offering_id '{explicit_offering_id}' was not found.")

    offering_name = str(row_data.get("offering_name") or "").strip()
    if not offering_name:
        return "", notes
    candidates = ctx.search_offerings(vendor_id=vendor_id or None, q=offering_name, limit=10)
    lowered = offering_name.lower()
    exact = [
        row
        for row in candidates
        if str(row.get("offering_name") or "").strip().lower() == lowered
        or str(row.get("offering_id") or "").strip().lower() == lowered
    ]
    if len(exact) == 1:
        notes.append("Inferred offering from offering_name.")
        return str(exact[0].get("offering_id") or "").strip(), notes
    if len(candidates) == 1:
        notes.append("Single near-match found for offering_name.")
        return str(candidates[0].get("offering_id") or "").strip(), notes
    if len(candidates) > 1:
        notes.append("offering_name matched multiple offerings.")
    return "", notes


def _suggest_invoice_match(row_data: dict[str, str], ctx: ImportMatchContext) -> tuple[str, str, str, str, list[str]]:
    notes: list[str] = []
    vendor_id, vendor_notes = _resolve_vendor_by_name(row_data, ctx)
    notes.extend(vendor_notes)
    offering_id, offering_notes = _resolve_offering_for_invoice(row_data, vendor_id=vendor_id, ctx=ctx)
    notes.extend(offering_notes)

    invoice_id = str(row_data.get("invoice_id") or "").strip()
    invoice_number = str(row_data.get("invoice_number") or "").strip()
    candidates = ctx.search_invoices(
        invoice_id=invoice_id,
        invoice_number=invoice_number,
        vendor_id=vendor_id,
        offering_id=offering_id,
        limit=12,
    )
    if candidates:
        chosen = candidates[0]
        resolved_invoice_id = str(chosen.get("invoice_id") or "").strip()
        resolved_vendor_id = str(chosen.get("vendor_id") or "").strip() or vendor_id
        resolved_offering_id = str(chosen.get("offering_id") or "").strip() or offering_id
        if resolved_invoice_id:
            notes.append("Existing invoice candidate found.")
            return (
                resolved_invoice_id,
                resolved_vendor_id,
                resolved_offering_id,
                _label_for_invoice_row(chosen),
                notes,
            )
    return "", vendor_id, offering_id, "", notes


def _suggest_payment_match(row_data: dict[str, str], ctx: ImportMatchContext) -> tuple[str, str, str, str, list[str]]:
    notes: list[str] = []
    invoice_id = str(row_data.get("invoice_id") or "").strip()
    invoice_number = str(row_data.get("invoice_number") or "").strip()
    vendor_id, vendor_notes = _resolve_vendor_by_name(row_data, ctx)
    notes.extend(vendor_notes)
    offering_id, offering_notes = _resolve_offering_for_invoice(row_data, vendor_id=vendor_id, ctx=ctx)
    notes.extend(offering_notes)
    candidates = ctx.search_invoices(
        invoice_id=invoice_id,
        invoice_number=invoice_number,
        vendor_id=vendor_id,
        offering_id=offering_id,
        limit=12,
    )
    if candidates:
        chosen = candidates[0]
        resolved_invoice_id = str(chosen.get("invoice_id") or "").strip()
        resolved_vendor_id = str(chosen.get("vendor_id") or "").strip() or vendor_id
        resolved_offering_id = str(chosen.get("offering_id") or "").strip() or offering_id
        return (
            resolved_invoice_id,
            resolved_vendor_id,
            resolved_offering_id,
            _label_for_invoice_row(chosen),
            notes,
        )
    return "", vendor_id, offering_id, "", notes


def _collect_invoice_merge_options(
    *,
    row_data: dict[str, str],
    ctx: ImportMatchContext,
    suggested_target_id: str,
    suggested_target_label: str,
) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    _append_option(options, target_id=suggested_target_id, label=suggested_target_label)
    for row in ctx.search_invoices(
        invoice_id=str(row_data.get("invoice_id") or "").strip(),
        invoice_number=str(row_data.get("invoice_number") or "").strip(),
        vendor_id=str(row_data.get("vendor_id") or "").strip(),
        offering_id=str(row_data.get("offering_id") or "").strip(),
        limit=12,
    ):
        _append_option(
            options,
            target_id=str(row.get("invoice_id") or "").strip(),
            label=_label_for_invoice_row(row),
        )
    return options[:15]


def build_preview_rows(
    repo,
    layout_key: str,
    rows: list[dict[str, str]],
    *,
    source_rows: list[dict[str, str]] | None = None,
    source_target_mapping: dict[str, str] | None = None,
    mapping_profile_id: str = "",
    resolved_record_selector: str = "",
) -> list[dict[str, Any]]:
    preview_rows: list[dict[str, Any]] = []
    ctx = ImportMatchContext(repo)
    source_row_list = [dict(item) for item in list(source_rows or [])]
    mapped_source_keys = {
        str(source_key or "").strip()
        for source_key, target_key in dict(source_target_mapping or {}).items()
        if str(source_key or "").strip() and str(target_key or "").strip()
    }
    normalized_mapping_profile_id = str(mapping_profile_id or "").strip()
    normalized_selector = str(resolved_record_selector or "").strip()
    for idx, row_data in enumerate(rows, start=1):
        source_row_raw = dict(source_row_list[idx - 1]) if idx - 1 < len(source_row_list) else {}
        source_row_raw.pop("_line", None)
        unmapped_source_fields = {
            str(key): str(value or "").strip()
            for key, value in source_row_raw.items()
            if str(key or "").strip()
            and str(key or "").strip() not in mapped_source_keys
            and str(value or "").strip()
        }
        errors: list[str] = []
        notes: list[str] = []
        blocked_reasons: list[str] = []
        suggested_target_id = ""
        suggested_target_vendor_id = ""
        suggested_target_label = ""
        merge_options: list[dict[str, str]] = []
        if layout_key == "vendors":
            suggested_target_id, suggested_target_label, notes = _suggest_vendor_match(repo, row_data, ctx)
            merge_options, extra_notes = _collect_vendor_merge_options(
                row_data=row_data,
                ctx=ctx,
                suggested_target_id=suggested_target_id,
                suggested_target_label=suggested_target_label,
            )
            if extra_notes:
                notes.extend([note for note in extra_notes if note not in notes])
        elif layout_key == "offerings":
            suggested_target_id, suggested_target_vendor_id, suggested_target_label, notes = _suggest_offering_match(
                repo,
                row_data,
                ctx,
            )
            merge_options = _collect_offering_merge_options(
                row_data=row_data,
                ctx=ctx,
                suggested_target_id=suggested_target_id,
                suggested_target_label=suggested_target_label,
            )
        elif layout_key == "invoices":
            (
                suggested_target_id,
                suggested_target_vendor_id,
                suggested_target_offering_id,
                suggested_target_label,
                notes,
            ) = _suggest_invoice_match(row_data, ctx)
            merge_options = _collect_invoice_merge_options(
                row_data=row_data,
                ctx=ctx,
                suggested_target_id=suggested_target_id,
                suggested_target_label=suggested_target_label,
            )
            if not suggested_target_vendor_id:
                blocked_reasons.append("Missing vendor dependency.")
            if not suggested_target_offering_id:
                blocked_reasons.append("Missing offering dependency.")
        elif layout_key == "payments":
            (
                suggested_target_invoice_id,
                suggested_target_vendor_id,
                suggested_target_offering_id,
                suggested_target_label,
                notes,
            ) = _suggest_payment_match(row_data, ctx)
            if suggested_target_invoice_id:
                suggested_target_id = suggested_target_invoice_id
            if not suggested_target_invoice_id:
                blocked_reasons.append("Missing invoice dependency.")
            if not suggested_target_offering_id:
                blocked_reasons.append("Missing offering dependency.")
        else:
            suggested_target_id, suggested_target_vendor_id, suggested_target_label, notes = _suggest_project_match(
                repo,
                row_data,
                ctx,
            )
            merge_options = _collect_project_merge_options(
                row_data=row_data,
                ctx=ctx,
                suggested_target_id=suggested_target_id,
                suggested_target_label=suggested_target_label,
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
        if layout_key == "invoices":
            if not str(row_data.get("invoice_date") or "").strip():
                errors.append("invoice_date is required for new records.")
            if not str(row_data.get("amount") or "").strip():
                errors.append("amount is required for new records.")
        if layout_key == "payments":
            if not str(row_data.get("payment_date") or "").strip():
                errors.append("payment_date is required for new records.")
            if not str(row_data.get("amount") or "").strip():
                errors.append("amount is required for new records.")
            if not str(row_data.get("invoice_id") or row_data.get("invoice_number") or "").strip():
                errors.append("invoice_id or invoice_number is required for new records.")

        row_status = "ready"
        if errors:
            row_status = "error"
        elif blocked_reasons:
            row_status = "blocked"
        elif notes:
            row_status = "review"
        combined_notes = list(notes)
        if blocked_reasons:
            combined_notes.extend([reason for reason in blocked_reasons if reason not in combined_notes])
        suggested_action = "merge" if suggested_target_id else "new"
        if layout_key in {"invoices", "payments"}:
            suggested_action = "new"

        preview_rows.append(
            {
                "row_index": idx,
                "line_number": str(row_data.get("_line") or ""),
                "row_data": {k: v for k, v in row_data.items() if k != "_line"},
                "suggested_action": suggested_action,
                "suggested_target_id": suggested_target_id,
                "suggested_target_vendor_id": suggested_target_vendor_id,
                "suggested_target_label": suggested_target_label,
                "merge_options": merge_options,
                "notes": combined_notes,
                "errors": errors,
                "row_status": row_status,
                "source_row_raw": source_row_raw,
                "unmapped_source_fields": unmapped_source_fields,
                "mapping_profile_id": normalized_mapping_profile_id,
                "resolved_record_selector": normalized_selector,
            }
        )
    return preview_rows

