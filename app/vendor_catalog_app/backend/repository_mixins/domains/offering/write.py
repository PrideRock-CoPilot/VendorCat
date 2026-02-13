from __future__ import annotations

import logging
import uuid
from typing import Any

import pandas as pd
from vendor_catalog_app.core.repository_constants import *

LOGGER = logging.getLogger(__name__)
class RepositoryOfferingWriteMixin:
    def create_vendor_profile(
        self,
        *,
        actor_user_principal: str,
        legal_name: str,
        display_name: str | None = None,
        lifecycle_state: str = "draft",
        owner_org_id: str | None = None,
        risk_tier: str | None = None,
        source_system: str | None = "manual",
    ) -> str:
        legal_name = legal_name.strip()
        if not legal_name:
            raise ValueError("Legal name is required.")
        owner_org_id = (owner_org_id or "").strip()
        if not owner_org_id:
            raise ValueError("Owner Org ID is required.")
        vendor_id = self._new_id("vnd")
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        row = {
            "vendor_id": vendor_id,
            "legal_name": legal_name,
            "display_name": (display_name or legal_name).strip(),
            "lifecycle_state": lifecycle_state,
            "owner_org_id": owner_org_id,
            "risk_tier": (risk_tier or "").strip() or None,
            "source_system": (source_system or "manual").strip() or "manual",
            "source_record_id": f"manual-{vendor_id}",
            "source_batch_id": f"manual-{now.strftime('%Y%m%d%H%M%S')}",
            "source_extract_ts": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        self._execute_file(
            "inserts/create_vendor_profile.sql",
            params=(
                vendor_id,
                row["legal_name"],
                row["display_name"],
                row["lifecycle_state"],
                row["owner_org_id"],
                row["risk_tier"],
                row["source_system"],
                now,
                actor_ref,
            ),
            core_vendor=self._table("core_vendor"),
        )
        self._write_audit_entity_change(
            entity_name="core_vendor",
            entity_id=vendor_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return vendor_id

    def create_offering(
        self,
        *,
        vendor_id: str,
        actor_user_principal: str,
        offering_name: str,
        offering_type: str | None = None,
        lob: str | None = None,
        service_type: str | None = None,
        lifecycle_state: str = "draft",
        criticality_tier: str | None = None,
    ) -> str:
        offering_name = offering_name.strip()
        if not offering_name:
            raise ValueError("Offering name is required.")
        profile = self.get_vendor_profile(vendor_id)
        if profile.empty:
            raise ValueError("Vendor not found.")

        offering_id = self._new_id("off")
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        row = {
            "offering_id": offering_id,
            "vendor_id": vendor_id,
            "offering_name": offering_name,
            "offering_type": (offering_type or "").strip() or None,
            "lob": (lob or "").strip() or None,
            "service_type": (service_type or "").strip() or None,
            "lifecycle_state": lifecycle_state,
            "criticality_tier": (criticality_tier or "").strip() or None,
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }

        self._ensure_local_offering_columns()
        self._execute_file(
            "inserts/create_offering.sql",
            params=(
                offering_id,
                vendor_id,
                row["offering_name"],
                row["offering_type"],
                row["lob"],
                row["service_type"],
                row["lifecycle_state"],
                row["criticality_tier"],
                now,
                actor_ref,
            ),
            core_vendor_offering=self._table("core_vendor_offering"),
        )
        self._write_audit_entity_change(
            entity_name="core_vendor_offering",
            entity_id=offering_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return offering_id

    def create_contract(
        self,
        *,
        vendor_id: str,
        actor_user_principal: str,
        contract_number: str,
        contract_status: str = "active",
        offering_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        annual_value: float | None = None,
    ) -> str:
        profile = self.get_vendor_profile(vendor_id)
        if profile.empty:
            raise ValueError("Vendor not found.")

        normalized_offering_id = self._normalize_offering_id(offering_id)
        if normalized_offering_id and not self.offering_belongs_to_vendor(vendor_id, normalized_offering_id):
            raise ValueError("Selected offering does not belong to this vendor.")

        contract_number_value = str(contract_number or "").strip()
        if not contract_number_value:
            raise ValueError("Contract number is required.")

        allowed_statuses = {"draft", "pending", "active", "retired", "expired", "cancelled"}
        status_value = str(contract_status or "").strip().lower() or "active"
        if status_value not in allowed_statuses:
            raise ValueError(f"Contract status must be one of: {', '.join(sorted(allowed_statuses))}.")

        start_value = str(start_date or "").strip()
        start_date_value: str | None = None
        if start_value:
            parsed_start = pd.to_datetime(start_value, errors="coerce")
            if pd.isna(parsed_start):
                raise ValueError("Start date must be a valid date.")
            start_date_value = parsed_start.date().isoformat()

        end_value = str(end_date or "").strip()
        end_date_value: str | None = None
        if end_value:
            parsed_end = pd.to_datetime(end_value, errors="coerce")
            if pd.isna(parsed_end):
                raise ValueError("End date must be a valid date.")
            end_date_value = parsed_end.date().isoformat()

        if start_date_value and end_date_value and end_date_value < start_date_value:
            raise ValueError("End date must be on or after start date.")

        annual_value_value: float | None = None
        if annual_value not in (None, ""):
            try:
                annual_value_value = float(annual_value)
            except Exception as exc:
                raise ValueError("Annual value must be numeric.") from exc
            if annual_value_value < 0:
                raise ValueError("Annual value must be zero or greater.")

        contract_id = self._new_id("ctr")
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        cancelled_flag = bool(status_value == "cancelled")
        row = {
            "contract_id": contract_id,
            "vendor_id": vendor_id,
            "offering_id": normalized_offering_id,
            "contract_number": contract_number_value,
            "contract_status": status_value,
            "start_date": start_date_value,
            "end_date": end_date_value,
            "cancelled_flag": cancelled_flag,
            "annual_value": annual_value_value,
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }

        self._execute_file(
            "inserts/create_contract.sql",
            params=(
                contract_id,
                vendor_id,
                normalized_offering_id,
                contract_number_value,
                status_value,
                start_date_value,
                end_date_value,
                cancelled_flag,
                annual_value_value,
                now,
                actor_ref,
            ),
            core_contract=self._table("core_contract"),
        )
        self._write_audit_entity_change(
            entity_name="core_contract",
            entity_id=contract_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return contract_id

    def update_contract(
        self,
        *,
        vendor_id: str,
        contract_id: str,
        actor_user_principal: str,
        updates: dict[str, Any],
        reason: str,
    ) -> dict[str, str]:
        if not reason.strip():
            raise ValueError("Reason is required.")

        contracts = self.get_vendor_contracts(vendor_id)
        target = contracts[contracts["contract_id"].astype(str) == str(contract_id)]
        if target.empty:
            raise ValueError("Contract does not belong to this vendor.")

        before = target.iloc[0].to_dict()
        clean_updates: dict[str, Any] = {}
        allowed_statuses = {"draft", "pending", "active", "retired", "expired", "cancelled"}
        allowed_fields = {"contract_number", "offering_id", "contract_status", "start_date", "end_date", "annual_value"}

        for field, raw_value in (updates or {}).items():
            field_name = str(field or "").strip()
            if field_name not in allowed_fields:
                continue

            if field_name == "contract_number":
                value = str(raw_value or "").strip()
                if not value:
                    raise ValueError("Contract number is required.")
                if value != str(before.get("contract_number") or "").strip():
                    clean_updates[field_name] = value
                continue

            if field_name == "offering_id":
                value = self._normalize_offering_id(raw_value)
                if value and not self.offering_belongs_to_vendor(vendor_id, value):
                    raise ValueError("Selected offering does not belong to this vendor.")
                before_value = self._normalize_offering_id(before.get("offering_id"))
                if value != before_value:
                    clean_updates[field_name] = value
                continue

            if field_name == "contract_status":
                value = str(raw_value or "").strip().lower()
                if value not in allowed_statuses:
                    raise ValueError(f"Contract status must be one of: {', '.join(sorted(allowed_statuses))}.")
                before_value = str(before.get("contract_status") or "").strip().lower()
                if value != before_value:
                    clean_updates[field_name] = value
                    clean_updates["cancelled_flag"] = bool(value == "cancelled")
                continue

            if field_name in {"start_date", "end_date"}:
                text = str(raw_value or "").strip()
                value: str | None = None
                if text:
                    parsed = pd.to_datetime(text, errors="coerce")
                    if pd.isna(parsed):
                        raise ValueError(f"{field_name.replace('_', ' ').title()} must be a valid date.")
                    value = parsed.date().isoformat()
                before_raw = str(before.get(field_name) or "").strip()
                before_value = before_raw.split(" ")[0] if before_raw else None
                if value != before_value:
                    clean_updates[field_name] = value
                continue

            if field_name == "annual_value":
                text = str(raw_value or "").strip()
                value: float | None = None
                if text:
                    try:
                        value = float(text)
                    except Exception as exc:
                        raise ValueError("Annual value must be numeric.") from exc
                    if value < 0:
                        raise ValueError("Annual value must be zero or greater.")
                before_raw = before.get("annual_value")
                try:
                    before_value = float(before_raw) if before_raw not in (None, "") else None
                except Exception:
                    before_value = None
                if value != before_value:
                    clean_updates[field_name] = value
                continue

        start_date_value = clean_updates.get("start_date")
        if start_date_value is None:
            existing_start = str(before.get("start_date") or "").strip()
            start_date_value = existing_start.split(" ")[0] if existing_start else None
        end_date_value = clean_updates.get("end_date")
        if end_date_value is None:
            existing_end = str(before.get("end_date") or "").strip()
            end_date_value = existing_end.split(" ")[0] if existing_end else None
        if start_date_value and end_date_value and str(end_date_value) < str(start_date_value):
            raise ValueError("End date must be on or after start date.")

        if not clean_updates:
            raise ValueError("No contract fields changed.")

        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        set_columns = list(clean_updates.keys())
        set_clause = ", ".join([f"{column} = %s" for column in set_columns])
        params = tuple(clean_updates[column] for column in set_columns) + (now, actor_ref, contract_id, vendor_id)

        self._execute_file(
            "updates/update_contract_fields.sql",
            params=params,
            core_contract=self._table("core_contract"),
            set_clause=set_clause,
        )

        after = dict(before)
        after.update(clean_updates)
        request_id = str(uuid.uuid4())
        change_event_id = self._write_audit_entity_change(
            entity_name="core_contract",
            entity_id=contract_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def update_offering_fields(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        actor_user_principal: str,
        updates: dict[str, Any],
        reason: str,
    ) -> dict[str, str]:
        allowed = {"offering_name", "offering_type", "lob", "service_type", "lifecycle_state", "criticality_tier"}
        clean_updates = {k: v for k, v in updates.items() if k in allowed}
        if not clean_updates:
            raise ValueError("No editable fields were provided.")
        if not reason.strip():
            raise ValueError("Reason is required.")

        current = self.get_offering_record(vendor_id, offering_id)
        if current is None:
            raise ValueError("Offering not found for vendor.")
        before = dict(current)
        after = dict(current)
        after.update(clean_updates)

        request_id = str(uuid.uuid4())
        set_clause = ", ".join([f"{k} = %s" for k in clean_updates.keys()])
        params = list(clean_updates.values()) + [offering_id, vendor_id]
        self._ensure_local_offering_columns()
        self._execute_file(
            "updates/update_offering_fields.sql",
            params=tuple(params),
            core_vendor_offering=self._table("core_vendor_offering"),
            set_clause=set_clause,
        )
        change_event_id = self._write_audit_entity_change(
            entity_name="core_vendor_offering",
            entity_id=offering_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def map_contract_to_offering(
        self,
        *,
        contract_id: str,
        vendor_id: str,
        offering_id: str | None,
        actor_user_principal: str,
        reason: str,
    ) -> dict[str, str]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        offering_id = self._normalize_offering_id(offering_id)
        contracts = self.get_vendor_contracts(vendor_id)
        target = contracts[contracts["contract_id"].astype(str) == str(contract_id)]
        if target.empty:
            raise ValueError("Contract does not belong to this vendor.")
        if offering_id and not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Selected offering does not belong to this vendor.")

        before = target.iloc[0].to_dict()
        after = dict(before)
        after["offering_id"] = offering_id
        request_id = str(uuid.uuid4())

        self._execute_file(
            "updates/map_contract_to_offering.sql",
            params=(offering_id, self._now(), self._actor_ref(actor_user_principal), contract_id, vendor_id),
            core_contract=self._table("core_contract"),
        )
        change_event_id = self._write_audit_entity_change(
            entity_name="core_contract",
            entity_id=contract_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def map_demo_to_offering(
        self,
        *,
        demo_id: str,
        vendor_id: str,
        offering_id: str | None,
        actor_user_principal: str,
        reason: str,
    ) -> dict[str, str]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        offering_id = self._normalize_offering_id(offering_id)
        demos = self.get_vendor_demos(vendor_id)
        target = demos[demos["demo_id"].astype(str) == str(demo_id)]
        if target.empty:
            raise ValueError("Demo does not belong to this vendor.")
        if offering_id and not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Selected offering does not belong to this vendor.")

        before = target.iloc[0].to_dict()
        after = dict(before)
        after["offering_id"] = offering_id
        request_id = str(uuid.uuid4())

        self._execute_file(
            "updates/map_demo_to_offering.sql",
            params=(offering_id, self._now(), self._actor_ref(actor_user_principal), demo_id, vendor_id),
            core_vendor_demo=self._table("core_vendor_demo"),
        )
        change_event_id = self._write_audit_entity_change(
            entity_name="core_vendor_demo",
            entity_id=demo_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def bulk_map_contracts_to_offering(
        self,
        *,
        contract_ids: list[str],
        vendor_id: str,
        offering_id: str,
        actor_user_principal: str,
        reason: str,
    ) -> dict[str, Any]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        cleaned_contract_ids: list[str] = []
        seen_ids: set[str] = set()
        for contract_id in contract_ids:
            cleaned = str(contract_id or "").strip()
            if not cleaned or cleaned in seen_ids:
                continue
            cleaned_contract_ids.append(cleaned)
            seen_ids.add(cleaned)
        if not cleaned_contract_ids:
            raise ValueError("At least one contract is required.")
        normalized_offering_id = self._normalize_offering_id(offering_id)
        if not normalized_offering_id:
            raise ValueError("Offering ID is required.")
        if not self.offering_belongs_to_vendor(vendor_id, normalized_offering_id):
            raise ValueError("Selected offering does not belong to this vendor.")

        contracts = self.get_vendor_contracts(vendor_id)
        by_contract_id: dict[str, dict[str, Any]] = {}
        for row in contracts.to_dict("records"):
            key = str(row.get("contract_id") or "").strip()
            if key:
                by_contract_id[key] = row
        missing_ids = [contract_id for contract_id in cleaned_contract_ids if contract_id not in by_contract_id]
        if missing_ids:
            preview = ", ".join(missing_ids[:5])
            if len(missing_ids) > 5:
                preview = f"{preview}, +{len(missing_ids) - 5} more"
            raise ValueError(f"Contracts do not belong to this vendor: {preview}")

        request_ids: list[str] = []
        change_event_ids: list[str] = []
        skipped_count = 0
        actor_ref = self._actor_ref(actor_user_principal)
        statement = self._sql(
            "updates/map_contract_to_offering.sql",
            core_contract=self._table("core_contract"),
        )
        for contract_id in cleaned_contract_ids:
            before = dict(by_contract_id[contract_id])
            current_offering = self._normalize_offering_id(before.get("offering_id"))
            if current_offering == normalized_offering_id:
                skipped_count += 1
                continue
            after = dict(before)
            after["offering_id"] = normalized_offering_id
            request_id = str(uuid.uuid4())
            self.client.execute(
                statement,
                (normalized_offering_id, self._now(), actor_ref, contract_id, vendor_id),
            )
            change_event_id = self._write_audit_entity_change(
                entity_name="core_contract",
                entity_id=contract_id,
                action_type="update",
                actor_user_principal=actor_user_principal,
                before_json=before,
                after_json=after,
                request_id=request_id,
            )
            request_ids.append(request_id)
            change_event_ids.append(change_event_id)
        self._cache_clear()
        return {
            "mapped_count": len(change_event_ids),
            "skipped_count": skipped_count,
            "request_ids": request_ids,
            "change_event_ids": change_event_ids,
        }

    def bulk_map_demos_to_offering(
        self,
        *,
        demo_ids: list[str],
        vendor_id: str,
        offering_id: str,
        actor_user_principal: str,
        reason: str,
    ) -> dict[str, Any]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        cleaned_demo_ids: list[str] = []
        seen_ids: set[str] = set()
        for demo_id in demo_ids:
            cleaned = str(demo_id or "").strip()
            if not cleaned or cleaned in seen_ids:
                continue
            cleaned_demo_ids.append(cleaned)
            seen_ids.add(cleaned)
        if not cleaned_demo_ids:
            raise ValueError("At least one demo is required.")
        normalized_offering_id = self._normalize_offering_id(offering_id)
        if not normalized_offering_id:
            raise ValueError("Offering ID is required.")
        if not self.offering_belongs_to_vendor(vendor_id, normalized_offering_id):
            raise ValueError("Selected offering does not belong to this vendor.")

        demos = self.get_vendor_demos(vendor_id)
        by_demo_id: dict[str, dict[str, Any]] = {}
        for row in demos.to_dict("records"):
            key = str(row.get("demo_id") or "").strip()
            if key:
                by_demo_id[key] = row
        missing_ids = [demo_id for demo_id in cleaned_demo_ids if demo_id not in by_demo_id]
        if missing_ids:
            preview = ", ".join(missing_ids[:5])
            if len(missing_ids) > 5:
                preview = f"{preview}, +{len(missing_ids) - 5} more"
            raise ValueError(f"Demos do not belong to this vendor: {preview}")

        request_ids: list[str] = []
        change_event_ids: list[str] = []
        skipped_count = 0
        actor_ref = self._actor_ref(actor_user_principal)
        statement = self._sql(
            "updates/map_demo_to_offering.sql",
            core_vendor_demo=self._table("core_vendor_demo"),
        )
        for demo_id in cleaned_demo_ids:
            before = dict(by_demo_id[demo_id])
            current_offering = self._normalize_offering_id(before.get("offering_id"))
            if current_offering == normalized_offering_id:
                skipped_count += 1
                continue
            after = dict(before)
            after["offering_id"] = normalized_offering_id
            request_id = str(uuid.uuid4())
            self.client.execute(
                statement,
                (normalized_offering_id, self._now(), actor_ref, demo_id, vendor_id),
            )
            change_event_id = self._write_audit_entity_change(
                entity_name="core_vendor_demo",
                entity_id=demo_id,
                action_type="update",
                actor_user_principal=actor_user_principal,
                before_json=before,
                after_json=after,
                request_id=request_id,
            )
            request_ids.append(request_id)
            change_event_ids.append(change_event_id)
        self._cache_clear()
        return {
            "mapped_count": len(change_event_ids),
            "skipped_count": skipped_count,
            "request_ids": request_ids,
            "change_event_ids": change_event_ids,
        }

    def add_vendor_owner(
        self,
        *,
        vendor_id: str,
        owner_user_principal: str,
        owner_role: str,
        actor_user_principal: str,
    ) -> str:
        if self.get_vendor_profile(vendor_id).empty:
            raise ValueError("Vendor not found.")
        owner_principal = owner_user_principal.strip()
        if not owner_principal:
            raise ValueError("Owner principal is required.")
        owner_ref = self.resolve_user_id(owner_principal, allow_create=True)
        if not owner_ref:
            raise ValueError("Owner must exist in the app user directory.")
        owner_role_options = self.list_owner_role_options() or ["business_owner"]
        owner_role_value = self._normalize_choice(
            owner_role,
            field_name="Owner role",
            allowed=set(owner_role_options),
            default=owner_role_options[0],
        )
        owner_id = self._new_id("vown")
        now = self._now()
        row = {
            "vendor_owner_id": owner_id,
            "vendor_id": vendor_id,
            "owner_user_principal": owner_ref,
            "owner_role": owner_role_value,
            "active_flag": True,
            "updated_at": now.isoformat(),
            "updated_by": self._actor_ref(actor_user_principal),
        }
        actor_ref = self._actor_ref(actor_user_principal)
        self._execute_file(
            "inserts/add_vendor_owner.sql",
            params=(
                owner_id,
                vendor_id,
                row["owner_user_principal"],
                row["owner_role"],
                True,
                now,
                actor_ref,
            ),
            core_vendor_business_owner=self._table("core_vendor_business_owner"),
        )
        self._write_audit_entity_change(
            entity_name="core_vendor_business_owner",
            entity_id=owner_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return owner_id

    def add_vendor_org_assignment(
        self,
        *,
        vendor_id: str,
        org_id: str,
        assignment_type: str,
        actor_user_principal: str,
    ) -> str:
        if self.get_vendor_profile(vendor_id).empty:
            raise ValueError("Vendor not found.")
        org_value = org_id.strip()
        if not org_value:
            raise ValueError("Org ID is required.")
        assignment_options = self.list_assignment_type_options() or ["consumer"]
        assignment_type_value = self._normalize_choice(
            assignment_type,
            field_name="Assignment type",
            allowed=set(assignment_options),
            default=assignment_options[0],
        )
        assignment_id = self._new_id("voa")
        now = self._now()
        row = {
            "vendor_org_assignment_id": assignment_id,
            "vendor_id": vendor_id,
            "org_id": org_value,
            "assignment_type": assignment_type_value,
            "active_flag": True,
            "updated_at": now.isoformat(),
            "updated_by": self._actor_ref(actor_user_principal),
        }
        actor_ref = self._actor_ref(actor_user_principal)
        self._execute_file(
            "inserts/add_vendor_org_assignment.sql",
            params=(
                assignment_id,
                vendor_id,
                row["org_id"],
                row["assignment_type"],
                True,
                now,
                actor_ref,
            ),
            core_vendor_org_assignment=self._table("core_vendor_org_assignment"),
        )
        self._write_audit_entity_change(
            entity_name="core_vendor_org_assignment",
            entity_id=assignment_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return assignment_id

    def add_vendor_contact(
        self,
        *,
        vendor_id: str,
        full_name: str,
        contact_type: str,
        email: str | None,
        phone: str | None,
        actor_user_principal: str,
    ) -> str:
        if self.get_vendor_profile(vendor_id).empty:
            raise ValueError("Vendor not found.")
        contact_name = full_name.strip()
        if not contact_name:
            raise ValueError("Contact name is required.")
        contact_type_options = self.list_contact_type_options() or ["business"]
        contact_type_value = self._normalize_choice(
            contact_type,
            field_name="Contact type",
            allowed=set(contact_type_options),
            default=contact_type_options[0],
        )
        contact_id = self._new_id("con")
        now = self._now()
        row = {
            "vendor_contact_id": contact_id,
            "vendor_id": vendor_id,
            "contact_type": contact_type_value,
            "full_name": contact_name,
            "email": (email or "").strip() or None,
            "phone": (phone or "").strip() or None,
            "active_flag": True,
            "updated_at": now.isoformat(),
            "updated_by": self._actor_ref(actor_user_principal),
        }
        actor_ref = self._actor_ref(actor_user_principal)
        self._execute_file(
            "inserts/add_vendor_contact.sql",
            params=(
                contact_id,
                vendor_id,
                row["contact_type"],
                row["full_name"],
                row["email"],
                row["phone"],
                True,
                now,
                actor_ref,
            ),
            core_vendor_contact=self._table("core_vendor_contact"),
        )
        self._write_audit_entity_change(
            entity_name="core_vendor_contact",
            entity_id=contact_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return contact_id

    def add_offering_owner(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        owner_user_principal: str,
        owner_role: str,
        actor_user_principal: str,
    ) -> str:
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to vendor.")
        if not owner_user_principal.strip():
            raise ValueError("Owner principal is required.")
        owner_ref = self.resolve_user_id(owner_user_principal, allow_create=True)
        if not owner_ref:
            raise ValueError("Owner must exist in the app user directory.")
        owner_role_options = self.list_owner_role_options() or ["business_owner"]
        owner_role_value = self._normalize_choice(
            owner_role,
            field_name="Owner role",
            allowed=set(owner_role_options),
            default=owner_role_options[0],
        )
        owner_id = self._new_id("oown")
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        row = {
            "offering_owner_id": owner_id,
            "offering_id": offering_id,
            "owner_user_principal": owner_ref,
            "owner_role": owner_role_value,
            "active_flag": True,
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }
        self._execute_file(
            "inserts/add_offering_owner.sql",
            params=(
                owner_id,
                offering_id,
                row["owner_user_principal"],
                row["owner_role"],
                True,
                now,
                actor_ref,
            ),
            core_offering_business_owner=self._table("core_offering_business_owner"),
        )
        self._write_audit_entity_change(
            entity_name="core_offering_business_owner",
            entity_id=owner_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return owner_id

    def remove_offering_owner(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        offering_owner_id: str,
        actor_user_principal: str,
    ) -> None:
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to vendor.")
        self._execute_file(
            "updates/remove_offering_owner_soft.sql",
            params=(offering_owner_id, offering_id),
            core_offering_business_owner=self._table("core_offering_business_owner"),
        )
        self._write_audit_entity_change(
            entity_name="core_offering_business_owner",
            entity_id=str(offering_owner_id),
            action_type="delete",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=None,
            request_id=None,
        )

    def add_offering_contact(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        full_name: str,
        contact_type: str,
        email: str | None,
        phone: str | None,
        actor_user_principal: str,
    ) -> str:
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to vendor.")
        if not full_name.strip():
            raise ValueError("Contact name is required.")
        contact_type_options = self.list_contact_type_options() or ["business"]
        contact_type_value = self._normalize_choice(
            contact_type,
            field_name="Contact type",
            allowed=set(contact_type_options),
            default=contact_type_options[0],
        )
        contact_id = self._new_id("ocon")
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        row = {
            "offering_contact_id": contact_id,
            "offering_id": offering_id,
            "contact_type": contact_type_value,
            "full_name": full_name.strip(),
            "email": (email or "").strip() or None,
            "phone": (phone or "").strip() or None,
            "active_flag": True,
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }
        self._execute_file(
            "inserts/add_offering_contact.sql",
            params=(
                contact_id,
                offering_id,
                row["contact_type"],
                row["full_name"],
                row["email"],
                row["phone"],
                True,
                now,
                actor_ref,
            ),
            core_offering_contact=self._table("core_offering_contact"),
        )
        self._write_audit_entity_change(
            entity_name="core_offering_contact",
            entity_id=contact_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return contact_id

    def remove_offering_contact(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        offering_contact_id: str,
        actor_user_principal: str,
    ) -> None:
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to vendor.")
        self._execute_file(
            "updates/remove_offering_contact_soft.sql",
            params=(offering_contact_id, offering_id),
            core_offering_contact=self._table("core_offering_contact"),
        )
        self._write_audit_entity_change(
            entity_name="core_offering_contact",
            entity_id=str(offering_contact_id),
            action_type="delete",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=None,
            request_id=None,
        )


