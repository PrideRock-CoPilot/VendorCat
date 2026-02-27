from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Any

LOGGER = logging.getLogger(__name__)


class RepositoryCoreCanonicalMixin:
    _CANONICAL_LOOKUP_META: dict[str, dict[str, str]] = {
        "business_unit": {
            "table": "lkp_business_unit",
            "id_col": "business_unit_id",
            "code_col": "business_unit_code",
            "name_col": "business_unit_name",
        },
        "owner_organization": {
            "table": "lkp_owner_organization",
            "id_col": "owner_organization_id",
            "code_col": "owner_organization_code",
            "name_col": "owner_organization_name",
        },
        "service_type": {
            "table": "lkp_service_type",
            "id_col": "service_type_id",
            "code_col": "service_type_code",
            "name_col": "service_type_name",
        },
        "owner_role": {
            "table": "lkp_owner_role",
            "id_col": "owner_role_id",
            "code_col": "owner_role_code",
            "name_col": "owner_role_name",
        },
        "contact_type": {
            "table": "lkp_contact_type",
            "id_col": "contact_type_id",
            "code_col": "contact_type_code",
            "name_col": "contact_type_name",
        },
        "lifecycle_state": {
            "table": "lkp_lifecycle_state",
            "id_col": "lifecycle_state_id",
            "code_col": "lifecycle_state_code",
            "name_col": "lifecycle_state_name",
        },
        "risk_tier": {
            "table": "lkp_risk_tier",
            "id_col": "risk_tier_id",
            "code_col": "risk_tier_code",
            "name_col": "risk_tier_name",
        },
        "vendor_category": {
            "table": "lkp_vendor_category",
            "id_col": "vendor_category_id",
            "code_col": "vendor_category_code",
            "name_col": "vendor_category_name",
        },
        "compliance_category": {
            "table": "lkp_compliance_category",
            "id_col": "compliance_category_id",
            "code_col": "compliance_category_code",
            "name_col": "compliance_category_name",
        },
        "gl_category": {
            "table": "lkp_gl_category",
            "id_col": "gl_category_id",
            "code_col": "gl_category_code",
            "name_col": "gl_category_name",
        },
    }

    @staticmethod
    def _canonical_token(value: Any) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        text = re.sub(r"[^a-z0-9]+", "_", text)
        text = re.sub(r"_+", "_", text)
        return text.strip("_")

    def _canonical_lookup_rows(self, lookup_key: str) -> list[dict[str, Any]]:
        meta = self._CANONICAL_LOOKUP_META[lookup_key]
        rows = self._query_or_empty(
            (
                f"SELECT {meta['id_col']} AS lookup_id, "
                f"{meta['code_col']} AS lookup_code, "
                f"{meta['name_col']} AS lookup_name, "
                "coalesce(active_flag, 1) AS active_flag "
                f"FROM {self._table(meta['table'])}"
            ),
            columns=["lookup_id", "lookup_code", "lookup_name", "active_flag"],
        )
        if rows.empty:
            return []
        return rows.to_dict("records")

    def _canonical_lookup_id(
        self,
        lookup_key: str,
        value: Any,
        *,
        field_name: str,
        allow_blank: bool = True,
        strict: bool = True,
        create_if_missing: bool = False,
    ) -> str | None:
        candidate = str(value or "").strip()
        if not candidate:
            if allow_blank:
                return None
            raise ValueError(f"{field_name} is required.")

        candidate_token = self._canonical_token(candidate)
        rows = self._canonical_lookup_rows(lookup_key)
        if rows:
            active_rows: list[dict[str, Any]] = []
            inactive_rows: list[dict[str, Any]] = []
            as_bool = getattr(self, "_as_bool", lambda raw: str(raw).strip() in {"1", "true", "True"})
            for row in rows:
                if as_bool(row.get("active_flag")):
                    active_rows.append(row)
                else:
                    inactive_rows.append(row)

            for pool in (active_rows, inactive_rows):
                for row in pool:
                    options = {
                        self._canonical_token(row.get("lookup_id")),
                        self._canonical_token(row.get("lookup_code")),
                        self._canonical_token(row.get("lookup_name")),
                    }
                    if candidate_token and candidate_token in options:
                        return str(row.get("lookup_id") or "").strip() or None

        if create_if_missing:
            return self._canonical_insert_lookup_row(lookup_key=lookup_key, candidate_value=candidate)
        if strict:
            raise ValueError(f"{field_name} must be a managed lookup value.")
        return None

    def _canonical_insert_lookup_row(self, *, lookup_key: str, candidate_value: str) -> str:
        meta = self._CANONICAL_LOOKUP_META[lookup_key]
        code_token = self._canonical_token(candidate_value) or f"value_{uuid.uuid4().hex[:10]}"
        label_value = str(candidate_value or "").strip() or code_token
        row_id = f"{lookup_key}-{code_token}"

        try:
            self.client.execute(
                (
                    f"INSERT INTO {self._table(meta['table'])} "
                    f"({meta['id_col']}, {meta['code_col']}, {meta['name_col']}) "
                    "VALUES (%s, %s, %s)"
                ),
                (row_id, code_token, label_value),
            )
            return row_id
        except Exception:
            existing = self._canonical_lookup_id(
                lookup_key,
                candidate_value,
                field_name=lookup_key.replace("_", " ").title(),
                allow_blank=False,
                strict=False,
                create_if_missing=False,
            )
            if existing:
                return existing
            raise

    def _canonical_option_membership(self, value: Any, options: list[str]) -> bool:
        candidate_token = self._canonical_token(value)
        if not candidate_token:
            return False
        option_tokens = {self._canonical_token(item) for item in list(options or [])}
        return candidate_token in option_tokens

    def _canonical_resolve_owner_organization_id(
        self,
        owner_org_id: Any,
        *,
        allow_blank: bool = True,
        create_if_missing: bool = False,
        strict: bool = True,
    ) -> str | None:
        candidate = str(owner_org_id or "").strip()
        if not candidate:
            return None
        owner_options = list(getattr(self, "list_owner_organization_options", lambda: [])() or [])
        bu_options = list(getattr(self, "list_offering_business_unit_options", lambda: [])() or [])
        appears_owner = self._canonical_option_membership(candidate, owner_options)
        appears_bu = self._canonical_option_membership(candidate, bu_options)
        if appears_bu and not appears_owner:
            return None
        return self._canonical_lookup_id(
            "owner_organization",
            candidate,
            field_name="Owner organization",
            allow_blank=allow_blank,
            strict=strict,
            create_if_missing=create_if_missing and appears_owner,
        )

    def _canonical_resolve_business_unit_id(
        self,
        business_unit: Any,
        *,
        allow_blank: bool = True,
        create_if_missing: bool = False,
        strict: bool = True,
    ) -> str | None:
        return self._canonical_lookup_id(
            "business_unit",
            business_unit,
            field_name="Business Unit",
            allow_blank=allow_blank,
            strict=strict,
            create_if_missing=create_if_missing,
        )

    def _canonical_resolve_lifecycle_state_id(
        self,
        lifecycle_state: Any,
        *,
        create_if_missing: bool = False,
    ) -> str:
        lifecycle_value = str(lifecycle_state or "").strip() or "draft"
        resolved = self._canonical_lookup_id(
            "lifecycle_state",
            lifecycle_value,
            field_name="Lifecycle state",
            allow_blank=False,
            strict=True,
            create_if_missing=create_if_missing,
        )
        return str(resolved or "")

    def _canonical_resolve_risk_tier_id(
        self,
        risk_tier: Any,
        *,
        create_if_missing: bool = False,
    ) -> str:
        risk_value = str(risk_tier or "").strip() or "medium"
        resolved = self._canonical_lookup_id(
            "risk_tier",
            risk_value,
            field_name="Risk tier",
            allow_blank=False,
            strict=True,
            create_if_missing=create_if_missing,
        )
        return str(resolved or "")

    def _canonical_resolve_service_type_id(
        self,
        service_type: Any,
        *,
        create_if_missing: bool = False,
        strict: bool = True,
    ) -> str | None:
        return self._canonical_lookup_id(
            "service_type",
            service_type,
            field_name="Service type",
            allow_blank=True,
            strict=strict,
            create_if_missing=create_if_missing,
        )

    def _canonical_resolve_owner_role_id(
        self,
        owner_role: Any,
        *,
        create_if_missing: bool = False,
    ) -> str:
        role_value = str(owner_role or "").strip() or "business_owner"
        resolved = self._canonical_lookup_id(
            "owner_role",
            role_value,
            field_name="Owner role",
            allow_blank=False,
            strict=True,
            create_if_missing=create_if_missing,
        )
        return str(resolved or "")

    def _canonical_resolve_contact_type_id(
        self,
        contact_type: Any,
        *,
        create_if_missing: bool = False,
    ) -> str:
        type_value = str(contact_type or "").strip() or "business"
        resolved = self._canonical_lookup_id(
            "contact_type",
            type_value,
            field_name="Contact type",
            allow_blank=False,
            strict=True,
            create_if_missing=create_if_missing,
        )
        return str(resolved or "")

    def _canonical_resolve_optional_category_id(
        self,
        lookup_key: str,
        value: Any,
        *,
        create_if_missing: bool = False,
    ) -> str | None:
        if value in (None, ""):
            return None
        return self._canonical_lookup_id(
            lookup_key,
            value,
            field_name=lookup_key.replace("_", " ").title(),
            allow_blank=True,
            strict=False,
            create_if_missing=create_if_missing,
        )

    @staticmethod
    def _canonical_bool(value: Any, *, default: bool = False) -> bool:
        if value in (None, ""):
            return bool(default)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return int(value) != 0
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    def _canonical_owner_principal_ref(self, user_principal: Any) -> str:
        candidate = str(user_principal or "").strip()
        if not candidate:
            return ""
        try:
            resolved = self._actor_ref(candidate)
        except Exception:
            LOGGER.debug("Could not resolve canonical owner principal '%s'; using raw value.", candidate, exc_info=True)
            resolved = candidate
        return str(resolved or candidate).strip() or candidate

    def _canonical_vendor_exists(self, vendor_id: str) -> bool:
        rows = self._query_or_empty(
            f"SELECT vendor_id FROM {self._table('vendor')} WHERE vendor_id = %s LIMIT 1",
            params=(vendor_id,),
            columns=["vendor_id"],
        )
        return not rows.empty

    def _canonical_offering_exists(self, offering_id: str) -> bool:
        rows = self._query_or_empty(
            f"SELECT offering_id FROM {self._table('offering')} WHERE offering_id = %s LIMIT 1",
            params=(offering_id,),
            columns=["offering_id"],
        )
        return not rows.empty

    def _canonical_ensure_vendor_from_core(self, vendor_id: str, *, actor_user_principal: str) -> None:
        if not str(vendor_id or "").strip() or self._canonical_vendor_exists(vendor_id):
            return
        self._canonical_sync_vendor_from_core(
            vendor_id=vendor_id,
            actor_user_principal=actor_user_principal,
            sync_primary_business_unit_assignment=True,
            source_key_for_primary=f"core_vendor.owner_org_id:{vendor_id}",
        )

    def _canonical_ensure_offering_from_core(
        self,
        *,
        offering_id: str,
        actor_user_principal: str,
    ) -> None:
        if not str(offering_id or "").strip() or self._canonical_offering_exists(offering_id):
            return
        self._canonical_sync_offering_from_core(
            offering_id=offering_id,
            actor_user_principal=actor_user_principal,
            sync_primary_business_unit_assignment=True,
            source_key_for_primary=f"core_vendor_offering.business_unit:{offering_id}",
        )

    def _canonical_sync_vendor_from_core(
        self,
        *,
        vendor_id: str,
        actor_user_principal: str,
        sync_primary_business_unit_assignment: bool = True,
        source_key_for_primary: str | None = None,
    ) -> None:
        vendor_key = str(vendor_id or "").strip()
        if not vendor_key:
            return
        core_rows = self._query_or_empty(
            f"SELECT * FROM {self._table('core_vendor')} WHERE vendor_id = %s LIMIT 1",
            params=(vendor_key,),
            columns=[],
        )
        if core_rows.empty:
            return
        row = core_rows.iloc[0].to_dict()
        self._canonical_upsert_vendor(
            vendor_id=vendor_key,
            legal_name=str(row.get("legal_name") or vendor_key),
            display_name=str(row.get("display_name") or row.get("legal_name") or vendor_key),
            lifecycle_state=str(row.get("lifecycle_state") or "draft"),
            owner_org_id=row.get("owner_org_id"),
            risk_tier=str(row.get("risk_tier") or "medium"),
            source_system=str(row.get("source_system") or "legacy_core"),
            vendor_category=row.get("vendor_category"),
            compliance_category=row.get("compliance_category"),
            gl_category=row.get("gl_category"),
            delegated_vendor_flag=row.get("delegated_vendor_flag"),
            health_care_vendor_flag=row.get("health_care_vendor_flag"),
            updated_by=actor_user_principal,
            create_lookup_if_missing=True,
            sync_primary_business_unit_assignment=sync_primary_business_unit_assignment,
            source_key_for_primary=source_key_for_primary or f"core_vendor.owner_org_id:{vendor_key}",
        )

    def _canonical_sync_offering_from_core(
        self,
        *,
        offering_id: str,
        actor_user_principal: str,
        sync_primary_business_unit_assignment: bool = True,
        source_key_for_primary: str | None = None,
    ) -> None:
        offering_key = str(offering_id or "").strip()
        if not offering_key:
            return
        core_rows = self._query_or_empty(
            f"SELECT * FROM {self._table('core_vendor_offering')} WHERE offering_id = %s LIMIT 1",
            params=(offering_key,),
            columns=[],
        )
        if core_rows.empty:
            return
        row = core_rows.iloc[0].to_dict()
        vendor_id = str(row.get("vendor_id") or "").strip()
        if not vendor_id:
            return
        self._canonical_sync_vendor_from_core(
            vendor_id=vendor_id,
            actor_user_principal=actor_user_principal,
            sync_primary_business_unit_assignment=True,
            source_key_for_primary=f"core_vendor.owner_org_id:{vendor_id}",
        )
        self._canonical_upsert_offering(
            offering_id=offering_key,
            vendor_id=vendor_id,
            offering_name=str(row.get("offering_name") or offering_key),
            lifecycle_state=str(row.get("lifecycle_state") or "draft"),
            business_unit=row.get("business_unit"),
            service_type=row.get("service_type"),
            criticality_tier=row.get("criticality_tier"),
            updated_by=actor_user_principal,
            create_lookup_if_missing=True,
            sync_primary_business_unit_assignment=sync_primary_business_unit_assignment,
            source_key_for_primary=source_key_for_primary or f"core_vendor_offering.business_unit:{offering_key}",
        )

    def _canonical_sync_vendor_related_from_core(
        self,
        *,
        vendor_id: str,
        actor_user_principal: str,
    ) -> None:
        vendor_key = str(vendor_id or "").strip()
        if not vendor_key:
            return
        self._canonical_sync_vendor_from_core(
            vendor_id=vendor_key,
            actor_user_principal=actor_user_principal,
            sync_primary_business_unit_assignment=False,
        )
        owner_rows = self._query_or_empty(
            (
                f"SELECT vendor_owner_id, owner_user_principal, owner_role, active_flag "
                f"FROM {self._table('core_vendor_business_owner')} "
                "WHERE vendor_id = %s"
            ),
            params=(vendor_key,),
            columns=["vendor_owner_id", "owner_user_principal", "owner_role", "active_flag"],
        )
        for row in owner_rows.to_dict("records"):
            assignment_id = str(row.get("vendor_owner_id") or "").strip()
            if not assignment_id:
                continue
            self._canonical_upsert_vendor_owner_assignment(
                assignment_id=assignment_id,
                vendor_id=vendor_key,
                owner_user_principal=str(row.get("owner_user_principal") or "").strip(),
                owner_role=str(row.get("owner_role") or "business_owner").strip() or "business_owner",
                actor_user_principal=actor_user_principal,
                active_flag=self._canonical_bool(row.get("active_flag"), default=True),
            )
        contact_rows = self._query_or_empty(
            (
                f"SELECT vendor_contact_id, contact_type, full_name, email, phone, active_flag "
                f"FROM {self._table('core_vendor_contact')} "
                "WHERE vendor_id = %s"
            ),
            params=(vendor_key,),
            columns=["vendor_contact_id", "contact_type", "full_name", "email", "phone", "active_flag"],
        )
        for row in contact_rows.to_dict("records"):
            contact_id = str(row.get("vendor_contact_id") or "").strip()
            if not contact_id:
                continue
            self._canonical_upsert_vendor_contact(
                contact_id=contact_id,
                vendor_id=vendor_key,
                contact_type=str(row.get("contact_type") or "business").strip() or "business",
                full_name=str(row.get("full_name") or "").strip(),
                email=str(row.get("email") or "").strip() or None,
                phone=str(row.get("phone") or "").strip() or None,
                actor_user_principal=actor_user_principal,
                active_flag=self._canonical_bool(row.get("active_flag"), default=True),
            )
        org_rows = self._query_or_empty(
            (
                f"SELECT vendor_org_assignment_id, org_id, assignment_type, active_flag "
                f"FROM {self._table('core_vendor_org_assignment')} "
                "WHERE vendor_id = %s"
            ),
            params=(vendor_key,),
            columns=["vendor_org_assignment_id", "org_id", "assignment_type", "active_flag"],
        )
        for row in org_rows.to_dict("records"):
            assignment_id = str(row.get("vendor_org_assignment_id") or "").strip()
            if not assignment_id:
                continue
            assignment_active = self._canonical_bool(row.get("active_flag"), default=True)
            assignment_primary = str(row.get("assignment_type") or "").strip().lower() == "primary"
            try:
                self._canonical_upsert_vendor_business_unit_assignment(
                    assignment_id=assignment_id,
                    vendor_id=vendor_key,
                    business_unit_value=str(row.get("org_id") or "").strip(),
                    source_system="core_vendor_org_assignment",
                    source_key=f"core_vendor_org_assignment:{assignment_id}",
                    is_primary=assignment_primary and assignment_active,
                    active_flag=assignment_active,
                    actor_user_principal=actor_user_principal,
                )
            except Exception:
                if not assignment_active:
                    raise
                self._canonical_upsert_vendor_business_unit_assignment(
                    assignment_id=assignment_id,
                    vendor_id=vendor_key,
                    business_unit_value=str(row.get("org_id") or "").strip(),
                    source_system="core_vendor_org_assignment",
                    source_key=f"core_vendor_org_assignment:{assignment_id}",
                    is_primary=False,
                    active_flag=False,
                    actor_user_principal=actor_user_principal,
                )

    def _canonical_sync_offering_related_from_core(
        self,
        *,
        offering_id: str,
        actor_user_principal: str,
    ) -> None:
        offering_key = str(offering_id or "").strip()
        if not offering_key:
            return
        self._canonical_sync_offering_from_core(
            offering_id=offering_key,
            actor_user_principal=actor_user_principal,
            sync_primary_business_unit_assignment=True,
        )
        owner_rows = self._query_or_empty(
            (
                f"SELECT offering_owner_id, owner_user_principal, owner_role, active_flag "
                f"FROM {self._table('core_offering_business_owner')} "
                "WHERE offering_id = %s"
            ),
            params=(offering_key,),
            columns=["offering_owner_id", "owner_user_principal", "owner_role", "active_flag"],
        )
        for row in owner_rows.to_dict("records"):
            assignment_id = str(row.get("offering_owner_id") or "").strip()
            if not assignment_id:
                continue
            self._canonical_upsert_offering_owner_assignment(
                assignment_id=assignment_id,
                offering_id=offering_key,
                owner_user_principal=str(row.get("owner_user_principal") or "").strip(),
                owner_role=str(row.get("owner_role") or "business_owner").strip() or "business_owner",
                actor_user_principal=actor_user_principal,
                active_flag=self._canonical_bool(row.get("active_flag"), default=True),
            )
        contact_rows = self._query_or_empty(
            (
                f"SELECT offering_contact_id, contact_type, full_name, email, phone, active_flag "
                f"FROM {self._table('core_offering_contact')} "
                "WHERE offering_id = %s"
            ),
            params=(offering_key,),
            columns=["offering_contact_id", "contact_type", "full_name", "email", "phone", "active_flag"],
        )
        for row in contact_rows.to_dict("records"):
            contact_id = str(row.get("offering_contact_id") or "").strip()
            if not contact_id:
                continue
            self._canonical_upsert_offering_contact(
                contact_id=contact_id,
                offering_id=offering_key,
                contact_type=str(row.get("contact_type") or "business").strip() or "business",
                full_name=str(row.get("full_name") or "").strip(),
                email=str(row.get("email") or "").strip() or None,
                phone=str(row.get("phone") or "").strip() or None,
                actor_user_principal=actor_user_principal,
                active_flag=self._canonical_bool(row.get("active_flag"), default=True),
            )

    def _canonical_upsert_vendor(
        self,
        *,
        vendor_id: str,
        legal_name: str,
        display_name: str | None,
        lifecycle_state: Any,
        owner_org_id: Any,
        risk_tier: Any,
        source_system: Any,
        vendor_category: Any = None,
        compliance_category: Any = None,
        gl_category: Any = None,
        delegated_vendor_flag: Any = None,
        health_care_vendor_flag: Any = None,
        updated_by: str,
        updated_at: datetime | None = None,
        create_lookup_if_missing: bool = False,
        sync_primary_business_unit_assignment: bool = True,
        source_key_for_primary: str | None = None,
    ) -> dict[str, Any]:
        vendor_key = str(vendor_id or "").strip()
        if not vendor_key:
            raise ValueError("Vendor ID is required.")
        now = updated_at or self._now()
        actor_ref = self._actor_ref(updated_by)
        lifecycle_state_id = self._canonical_resolve_lifecycle_state_id(
            lifecycle_state,
            create_if_missing=create_lookup_if_missing,
        )
        risk_tier_id = self._canonical_resolve_risk_tier_id(
            risk_tier,
            create_if_missing=create_lookup_if_missing,
        )
        owner_org_lookup_id = self._canonical_resolve_owner_organization_id(
            owner_org_id,
            allow_blank=True,
            create_if_missing=create_lookup_if_missing,
            strict=False,
        )
        primary_business_unit_id = self._canonical_resolve_business_unit_id(
            owner_org_id,
            allow_blank=True,
            create_if_missing=create_lookup_if_missing,
            strict=False,
        )
        vendor_category_id = self._canonical_resolve_optional_category_id(
            "vendor_category",
            vendor_category,
            create_if_missing=create_lookup_if_missing,
        )
        compliance_category_id = self._canonical_resolve_optional_category_id(
            "compliance_category",
            compliance_category,
            create_if_missing=create_lookup_if_missing,
        )
        gl_category_id = self._canonical_resolve_optional_category_id(
            "gl_category",
            gl_category,
            create_if_missing=create_lookup_if_missing,
        )
        delegated_flag = 1 if self._canonical_bool(delegated_vendor_flag) else 0
        health_flag = 1 if self._canonical_bool(health_care_vendor_flag) else 0

        exists = self._canonical_vendor_exists(vendor_key)
        if exists:
            self.client.execute(
                (
                    f"UPDATE {self._table('vendor')} "
                    "SET legal_name = %s, "
                    "display_name = %s, "
                    "lifecycle_state_id = %s, "
                    "risk_tier_id = %s, "
                    "primary_business_unit_id = %s, "
                    "primary_owner_organization_id = %s, "
                    "vendor_category_id = %s, "
                    "compliance_category_id = %s, "
                    "gl_category_id = %s, "
                    "delegated_vendor_flag = %s, "
                    "health_care_vendor_flag = %s, "
                    "source_system = %s, "
                    "updated_at = %s, "
                    "updated_by = %s "
                    "WHERE vendor_id = %s"
                ),
                (
                    str(legal_name or vendor_key).strip(),
                    str(display_name or legal_name or vendor_key).strip(),
                    lifecycle_state_id,
                    risk_tier_id,
                    primary_business_unit_id,
                    owner_org_lookup_id,
                    vendor_category_id,
                    compliance_category_id,
                    gl_category_id,
                    delegated_flag,
                    health_flag,
                    str(source_system or "").strip() or None,
                    now,
                    actor_ref,
                    vendor_key,
                ),
            )
        else:
            self.client.execute(
                (
                    f"INSERT INTO {self._table('vendor')} ("
                    "vendor_id, legal_name, display_name, lifecycle_state_id, risk_tier_id, "
                    "primary_business_unit_id, primary_owner_organization_id, vendor_category_id, "
                    "compliance_category_id, gl_category_id, delegated_vendor_flag, health_care_vendor_flag, "
                    "source_system, created_at, updated_at, updated_by"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                ),
                (
                    vendor_key,
                    str(legal_name or vendor_key).strip(),
                    str(display_name or legal_name or vendor_key).strip(),
                    lifecycle_state_id,
                    risk_tier_id,
                    primary_business_unit_id,
                    owner_org_lookup_id,
                    vendor_category_id,
                    compliance_category_id,
                    gl_category_id,
                    delegated_flag,
                    health_flag,
                    str(source_system or "").strip() or None,
                    now,
                    now,
                    actor_ref,
                ),
            )

        if sync_primary_business_unit_assignment and primary_business_unit_id:
            self._canonical_upsert_vendor_business_unit_assignment(
                vendor_id=vendor_key,
                business_unit_id=primary_business_unit_id,
                source_system=str(source_system or "").strip() or "runtime",
                source_key=str(source_key_for_primary or f"vendor.primary_business_unit_id:{vendor_key}"),
                is_primary=True,
                active_flag=True,
                actor_user_principal=updated_by,
            )

        return {
            "vendor_id": vendor_key,
            "primary_business_unit_id": primary_business_unit_id,
            "primary_owner_organization_id": owner_org_lookup_id,
        }

    def _canonical_upsert_offering(
        self,
        *,
        offering_id: str,
        vendor_id: str,
        offering_name: str,
        lifecycle_state: Any,
        business_unit: Any,
        service_type: Any,
        criticality_tier: Any,
        updated_by: str,
        updated_at: datetime | None = None,
        create_lookup_if_missing: bool = False,
        sync_primary_business_unit_assignment: bool = True,
        source_key_for_primary: str | None = None,
    ) -> dict[str, Any]:
        offering_key = str(offering_id or "").strip()
        vendor_key = str(vendor_id or "").strip()
        if not offering_key:
            raise ValueError("Offering ID is required.")
        if not vendor_key:
            raise ValueError("Vendor ID is required.")

        self._canonical_ensure_vendor_from_core(vendor_key, actor_user_principal=updated_by)
        now = updated_at or self._now()
        actor_ref = self._actor_ref(updated_by)
        lifecycle_state_id = self._canonical_resolve_lifecycle_state_id(
            lifecycle_state,
            create_if_missing=create_lookup_if_missing,
        )
        primary_business_unit_id = self._canonical_resolve_business_unit_id(
            business_unit,
            allow_blank=True,
            create_if_missing=create_lookup_if_missing,
            strict=False,
        )
        service_type_id = self._canonical_resolve_service_type_id(
            service_type,
            create_if_missing=create_lookup_if_missing,
            strict=False,
        )
        criticality_value = str(criticality_tier or "").strip() or None

        exists = self._canonical_offering_exists(offering_key)
        if exists:
            self.client.execute(
                (
                    f"UPDATE {self._table('offering')} "
                    "SET vendor_id = %s, "
                    "offering_name = %s, "
                    "lifecycle_state_id = %s, "
                    "primary_business_unit_id = %s, "
                    "primary_service_type_id = %s, "
                    "criticality_tier = %s, "
                    "updated_at = %s, "
                    "updated_by = %s "
                    "WHERE offering_id = %s"
                ),
                (
                    vendor_key,
                    str(offering_name or offering_key).strip(),
                    lifecycle_state_id,
                    primary_business_unit_id,
                    service_type_id,
                    criticality_value,
                    now,
                    actor_ref,
                    offering_key,
                ),
            )
        else:
            self.client.execute(
                (
                    f"INSERT INTO {self._table('offering')} ("
                    "offering_id, vendor_id, offering_name, lifecycle_state_id, "
                    "primary_business_unit_id, primary_service_type_id, criticality_tier, "
                    "created_at, updated_at, updated_by"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                ),
                (
                    offering_key,
                    vendor_key,
                    str(offering_name or offering_key).strip(),
                    lifecycle_state_id,
                    primary_business_unit_id,
                    service_type_id,
                    criticality_value,
                    now,
                    now,
                    actor_ref,
                ),
            )

        if sync_primary_business_unit_assignment and primary_business_unit_id:
            self._canonical_upsert_offering_business_unit_assignment(
                offering_id=offering_key,
                business_unit_id=primary_business_unit_id,
                source_system="runtime",
                source_key=str(source_key_for_primary or f"offering.primary_business_unit_id:{offering_key}"),
                is_primary=True,
                active_flag=True,
                actor_user_principal=updated_by,
            )
        return {"offering_id": offering_key, "primary_business_unit_id": primary_business_unit_id}

    def _canonical_upsert_vendor_business_unit_assignment(
        self,
        *,
        vendor_id: str,
        business_unit_id: str | None = None,
        business_unit_value: Any = None,
        assignment_id: str | None = None,
        source_system: str | None,
        source_key: str | None,
        is_primary: bool,
        active_flag: bool,
        actor_user_principal: str,
    ) -> str | None:
        vendor_key = str(vendor_id or "").strip()
        if not vendor_key:
            return None
        if not self._canonical_vendor_exists(vendor_key):
            self._canonical_ensure_vendor_from_core(vendor_key, actor_user_principal=actor_user_principal)

        resolved_business_unit_id = str(business_unit_id or "").strip() or str(
            self._canonical_resolve_business_unit_id(
                business_unit_value,
                allow_blank=True,
                create_if_missing=True,
                strict=False,
            )
            or ""
        ).strip()
        if not resolved_business_unit_id:
            return None

        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        assignment_key = str(assignment_id or "").strip()
        if not assignment_key:
            existing = self._query_or_empty(
                (
                    f"SELECT assignment_id FROM {self._table('vendor_business_unit_assignment')} "
                    "WHERE vendor_id = %s AND business_unit_id = %s "
                    "AND coalesce(active_flag, 1) IN (1, '1', true)"
                    " LIMIT 1"
                ),
                params=(vendor_key, resolved_business_unit_id),
                columns=["assignment_id"],
            )
            if not existing.empty:
                assignment_key = str(existing.iloc[0]["assignment_id"])
        if not assignment_key:
            assignment_key = f"vbu-{uuid.uuid4()}"

        exists = self._query_or_empty(
            (
                f"SELECT assignment_id FROM {self._table('vendor_business_unit_assignment')} "
                "WHERE assignment_id = %s LIMIT 1"
            ),
            params=(assignment_key,),
            columns=["assignment_id"],
        )
        if not exists.empty:
            self.client.execute(
                (
                    f"UPDATE {self._table('vendor_business_unit_assignment')} "
                    "SET vendor_id = %s, business_unit_id = %s, source_system = %s, source_key = %s, "
                    "is_primary = %s, active_flag = %s, updated_at = %s, updated_by = %s "
                    "WHERE assignment_id = %s"
                ),
                (
                    vendor_key,
                    resolved_business_unit_id,
                    str(source_system or "").strip() or None,
                    str(source_key or "").strip() or None,
                    1 if bool(is_primary) else 0,
                    1 if bool(active_flag) else 0,
                    now,
                    actor_ref,
                    assignment_key,
                ),
            )
        else:
            self.client.execute(
                (
                    f"INSERT INTO {self._table('vendor_business_unit_assignment')} ("
                    "assignment_id, vendor_id, business_unit_id, source_system, source_key, "
                    "is_primary, active_flag, created_at, created_by, updated_at, updated_by"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                ),
                (
                    assignment_key,
                    vendor_key,
                    resolved_business_unit_id,
                    str(source_system or "").strip() or None,
                    str(source_key or "").strip() or None,
                    1 if bool(is_primary) else 0,
                    1 if bool(active_flag) else 0,
                    now,
                    actor_ref,
                    now,
                    actor_ref,
                ),
            )

        if bool(is_primary):
            self.client.execute(
                (
                    f"UPDATE {self._table('vendor_business_unit_assignment')} "
                    "SET is_primary = 0, updated_at = %s, updated_by = %s "
                    "WHERE vendor_id = %s AND assignment_id <> %s "
                    "AND coalesce(active_flag, 1) IN (1, '1', true)"
                ),
                (now, actor_ref, vendor_key, assignment_key),
            )
            self.client.execute(
                (
                    f"UPDATE {self._table('vendor')} "
                    "SET primary_business_unit_id = %s, updated_at = %s, updated_by = %s "
                    "WHERE vendor_id = %s"
                ),
                (resolved_business_unit_id, now, actor_ref, vendor_key),
            )

        return assignment_key

    def _canonical_upsert_offering_business_unit_assignment(
        self,
        *,
        offering_id: str,
        business_unit_id: str | None = None,
        business_unit_value: Any = None,
        assignment_id: str | None = None,
        source_system: str | None,
        source_key: str | None,
        is_primary: bool,
        active_flag: bool,
        actor_user_principal: str,
    ) -> str | None:
        offering_key = str(offering_id or "").strip()
        if not offering_key:
            return None
        if not self._canonical_offering_exists(offering_key):
            self._canonical_ensure_offering_from_core(offering_id=offering_key, actor_user_principal=actor_user_principal)

        resolved_business_unit_id = str(business_unit_id or "").strip() or str(
            self._canonical_resolve_business_unit_id(
                business_unit_value,
                allow_blank=True,
                create_if_missing=True,
                strict=False,
            )
            or ""
        ).strip()
        if not resolved_business_unit_id:
            return None

        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        assignment_key = str(assignment_id or "").strip()
        if not assignment_key:
            existing = self._query_or_empty(
                (
                    f"SELECT assignment_id FROM {self._table('offering_business_unit_assignment')} "
                    "WHERE offering_id = %s AND business_unit_id = %s "
                    "AND coalesce(active_flag, 1) IN (1, '1', true)"
                    " LIMIT 1"
                ),
                params=(offering_key, resolved_business_unit_id),
                columns=["assignment_id"],
            )
            if not existing.empty:
                assignment_key = str(existing.iloc[0]["assignment_id"])
        if not assignment_key:
            assignment_key = f"obu-{uuid.uuid4()}"

        exists = self._query_or_empty(
            (
                f"SELECT assignment_id FROM {self._table('offering_business_unit_assignment')} "
                "WHERE assignment_id = %s LIMIT 1"
            ),
            params=(assignment_key,),
            columns=["assignment_id"],
        )
        if not exists.empty:
            self.client.execute(
                (
                    f"UPDATE {self._table('offering_business_unit_assignment')} "
                    "SET offering_id = %s, business_unit_id = %s, source_system = %s, source_key = %s, "
                    "is_primary = %s, active_flag = %s, updated_at = %s, updated_by = %s "
                    "WHERE assignment_id = %s"
                ),
                (
                    offering_key,
                    resolved_business_unit_id,
                    str(source_system or "").strip() or None,
                    str(source_key or "").strip() or None,
                    1 if bool(is_primary) else 0,
                    1 if bool(active_flag) else 0,
                    now,
                    actor_ref,
                    assignment_key,
                ),
            )
        else:
            self.client.execute(
                (
                    f"INSERT INTO {self._table('offering_business_unit_assignment')} ("
                    "assignment_id, offering_id, business_unit_id, source_system, source_key, "
                    "is_primary, active_flag, created_at, created_by, updated_at, updated_by"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                ),
                (
                    assignment_key,
                    offering_key,
                    resolved_business_unit_id,
                    str(source_system or "").strip() or None,
                    str(source_key or "").strip() or None,
                    1 if bool(is_primary) else 0,
                    1 if bool(active_flag) else 0,
                    now,
                    actor_ref,
                    now,
                    actor_ref,
                ),
            )

        if bool(is_primary):
            self.client.execute(
                (
                    f"UPDATE {self._table('offering_business_unit_assignment')} "
                    "SET is_primary = 0, updated_at = %s, updated_by = %s "
                    "WHERE offering_id = %s AND assignment_id <> %s "
                    "AND coalesce(active_flag, 1) IN (1, '1', true)"
                ),
                (now, actor_ref, offering_key, assignment_key),
            )
            self.client.execute(
                (
                    f"UPDATE {self._table('offering')} "
                    "SET primary_business_unit_id = %s, updated_at = %s, updated_by = %s "
                    "WHERE offering_id = %s"
                ),
                (resolved_business_unit_id, now, actor_ref, offering_key),
            )
        return assignment_key

    def _canonical_reassign_vendor_owner_assignment(
        self,
        *,
        assignment_id: str,
        owner_user_principal: str,
    ) -> None:
        self.client.execute(
            (
                f"UPDATE {self._table('vendor_owner_assignment')} "
                "SET user_principal = %s "
                "WHERE assignment_id = %s "
                "AND coalesce(active_flag, 1) IN (1, '1', true)"
            ),
            (self._canonical_owner_principal_ref(owner_user_principal), assignment_id),
        )

    def _canonical_reassign_offering_owner_assignment(
        self,
        *,
        assignment_id: str,
        owner_user_principal: str,
    ) -> None:
        self.client.execute(
            (
                f"UPDATE {self._table('offering_owner_assignment')} "
                "SET user_principal = %s "
                "WHERE assignment_id = %s "
                "AND coalesce(active_flag, 1) IN (1, '1', true)"
            ),
            (self._canonical_owner_principal_ref(owner_user_principal), assignment_id),
        )

    def _canonical_upsert_vendor_owner_assignment(
        self,
        *,
        assignment_id: str,
        vendor_id: str,
        owner_user_principal: str,
        owner_role: str,
        actor_user_principal: str,
        active_flag: bool = True,
    ) -> None:
        vendor_key = str(vendor_id or "").strip()
        if not vendor_key:
            return
        if not self._canonical_vendor_exists(vendor_key):
            self._canonical_ensure_vendor_from_core(vendor_key, actor_user_principal=actor_user_principal)
        role_id = self._canonical_resolve_owner_role_id(owner_role, create_if_missing=True)
        owner_ref = self._canonical_owner_principal_ref(owner_user_principal)
        assignment_key = str(assignment_id or "").strip() or f"voa-{uuid.uuid4()}"
        now = self._now()

        existing = self._query_or_empty(
            f"SELECT assignment_id FROM {self._table('vendor_owner_assignment')} WHERE assignment_id = %s LIMIT 1",
            params=(assignment_key,),
            columns=["assignment_id"],
        )
        if existing.empty:
            self.client.execute(
                (
                    f"INSERT INTO {self._table('vendor_owner_assignment')} ("
                    "assignment_id, vendor_id, owner_role_id, user_principal, active_flag, created_at, ended_at"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s)"
                ),
                (
                    assignment_key,
                    vendor_key,
                    role_id,
                    owner_ref,
                    1 if active_flag else 0,
                    now,
                    None if active_flag else now,
                ),
            )
        else:
            self.client.execute(
                (
                    f"UPDATE {self._table('vendor_owner_assignment')} "
                    "SET vendor_id = %s, owner_role_id = %s, user_principal = %s, active_flag = %s, ended_at = %s "
                    "WHERE assignment_id = %s"
                ),
                (
                    vendor_key,
                    role_id,
                    owner_ref,
                    1 if active_flag else 0,
                    None if active_flag else now,
                    assignment_key,
                ),
            )

    def _canonical_upsert_offering_owner_assignment(
        self,
        *,
        assignment_id: str,
        offering_id: str,
        owner_user_principal: str,
        owner_role: str,
        actor_user_principal: str,
        active_flag: bool = True,
    ) -> None:
        offering_key = str(offering_id or "").strip()
        if not offering_key:
            return
        if not self._canonical_offering_exists(offering_key):
            self._canonical_ensure_offering_from_core(offering_id=offering_key, actor_user_principal=actor_user_principal)
        role_id = self._canonical_resolve_owner_role_id(owner_role, create_if_missing=True)
        owner_ref = self._canonical_owner_principal_ref(owner_user_principal)
        assignment_key = str(assignment_id or "").strip() or f"ooa-{uuid.uuid4()}"
        now = self._now()

        existing = self._query_or_empty(
            f"SELECT assignment_id FROM {self._table('offering_owner_assignment')} WHERE assignment_id = %s LIMIT 1",
            params=(assignment_key,),
            columns=["assignment_id"],
        )
        if existing.empty:
            self.client.execute(
                (
                    f"INSERT INTO {self._table('offering_owner_assignment')} ("
                    "assignment_id, offering_id, owner_role_id, user_principal, active_flag, created_at, ended_at"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s)"
                ),
                (
                    assignment_key,
                    offering_key,
                    role_id,
                    owner_ref,
                    1 if active_flag else 0,
                    now,
                    None if active_flag else now,
                ),
            )
        else:
            self.client.execute(
                (
                    f"UPDATE {self._table('offering_owner_assignment')} "
                    "SET offering_id = %s, owner_role_id = %s, user_principal = %s, active_flag = %s, ended_at = %s "
                    "WHERE assignment_id = %s"
                ),
                (
                    offering_key,
                    role_id,
                    owner_ref,
                    1 if active_flag else 0,
                    None if active_flag else now,
                    assignment_key,
                ),
            )

    def _canonical_deactivate_offering_owner_assignment(self, *, assignment_id: str, offering_id: str) -> None:
        now = self._now()
        self.client.execute(
            (
                f"UPDATE {self._table('offering_owner_assignment')} "
                "SET active_flag = 0, ended_at = %s "
                "WHERE assignment_id = %s AND offering_id = %s"
            ),
            (now, assignment_id, offering_id),
        )

    def _canonical_upsert_vendor_contact(
        self,
        *,
        contact_id: str,
        vendor_id: str,
        contact_type: str,
        full_name: str,
        email: str | None,
        phone: str | None,
        actor_user_principal: str,
        active_flag: bool = True,
    ) -> None:
        vendor_key = str(vendor_id or "").strip()
        if not vendor_key:
            return
        if not self._canonical_vendor_exists(vendor_key):
            self._canonical_ensure_vendor_from_core(vendor_key, actor_user_principal=actor_user_principal)
        type_id = self._canonical_resolve_contact_type_id(contact_type, create_if_missing=True)
        contact_key = str(contact_id or "").strip() or f"vcon-{uuid.uuid4()}"
        now = self._now()

        existing = self._query_or_empty(
            f"SELECT vendor_contact_id FROM {self._table('vendor_contact')} WHERE vendor_contact_id = %s LIMIT 1",
            params=(contact_key,),
            columns=["vendor_contact_id"],
        )
        if existing.empty:
            self.client.execute(
                (
                    f"INSERT INTO {self._table('vendor_contact')} ("
                    "vendor_contact_id, vendor_id, contact_type_id, full_name, email, phone, active_flag, created_at, ended_at"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                ),
                (
                    contact_key,
                    vendor_key,
                    type_id,
                    str(full_name or "").strip(),
                    str(email or "").strip() or None,
                    str(phone or "").strip() or None,
                    1 if active_flag else 0,
                    now,
                    None if active_flag else now,
                ),
            )
        else:
            self.client.execute(
                (
                    f"UPDATE {self._table('vendor_contact')} "
                    "SET vendor_id = %s, contact_type_id = %s, full_name = %s, email = %s, phone = %s, "
                    "active_flag = %s, ended_at = %s "
                    "WHERE vendor_contact_id = %s"
                ),
                (
                    vendor_key,
                    type_id,
                    str(full_name or "").strip(),
                    str(email or "").strip() or None,
                    str(phone or "").strip() or None,
                    1 if active_flag else 0,
                    None if active_flag else now,
                    contact_key,
                ),
            )

    def _canonical_upsert_offering_contact(
        self,
        *,
        contact_id: str,
        offering_id: str,
        contact_type: str,
        full_name: str,
        email: str | None,
        phone: str | None,
        actor_user_principal: str,
        active_flag: bool = True,
    ) -> None:
        offering_key = str(offering_id or "").strip()
        if not offering_key:
            return
        if not self._canonical_offering_exists(offering_key):
            self._canonical_ensure_offering_from_core(offering_id=offering_key, actor_user_principal=actor_user_principal)
        type_id = self._canonical_resolve_contact_type_id(contact_type, create_if_missing=True)
        contact_key = str(contact_id or "").strip() or f"ocon-{uuid.uuid4()}"
        now = self._now()

        existing = self._query_or_empty(
            f"SELECT offering_contact_id FROM {self._table('offering_contact')} WHERE offering_contact_id = %s LIMIT 1",
            params=(contact_key,),
            columns=["offering_contact_id"],
        )
        if existing.empty:
            self.client.execute(
                (
                    f"INSERT INTO {self._table('offering_contact')} ("
                    "offering_contact_id, offering_id, contact_type_id, full_name, email, phone, active_flag, created_at, ended_at"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                ),
                (
                    contact_key,
                    offering_key,
                    type_id,
                    str(full_name or "").strip(),
                    str(email or "").strip() or None,
                    str(phone or "").strip() or None,
                    1 if active_flag else 0,
                    now,
                    None if active_flag else now,
                ),
            )
        else:
            self.client.execute(
                (
                    f"UPDATE {self._table('offering_contact')} "
                    "SET offering_id = %s, contact_type_id = %s, full_name = %s, email = %s, phone = %s, "
                    "active_flag = %s, ended_at = %s "
                    "WHERE offering_contact_id = %s"
                ),
                (
                    offering_key,
                    type_id,
                    str(full_name or "").strip(),
                    str(email or "").strip() or None,
                    str(phone or "").strip() or None,
                    1 if active_flag else 0,
                    None if active_flag else now,
                    contact_key,
                ),
            )

    def _canonical_deactivate_offering_contact(self, *, contact_id: str, offering_id: str) -> None:
        now = self._now()
        self.client.execute(
            (
                f"UPDATE {self._table('offering_contact')} "
                "SET active_flag = 0, ended_at = %s "
                "WHERE offering_contact_id = %s AND offering_id = %s"
            ),
            (now, contact_id, offering_id),
        )
