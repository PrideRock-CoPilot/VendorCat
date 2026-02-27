from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from vendor_catalog_app.core.repository_constants import *
from vendor_catalog_app.infrastructure.db import (
    DataConnectionError,
    DataExecutionError,
)

LOGGER = logging.getLogger(__name__)


class RepositoryWorkflowRequestMixin:
    def create_access_request(
        self,
        *,
        requestor_user_principal: str,
        requested_role: str,
        justification: str,
    ) -> str:
        requestor_raw = str(requestor_user_principal or "").strip()
        role_code = str(requested_role or "").strip().lower()
        if not requestor_raw:
            raise ValueError("Requester principal is required.")
        if not role_code:
            raise ValueError("Requested role is required.")
        justification_text = str(justification or "").strip()
        if not justification_text:
            raise ValueError("Justification is required.")
        profile = self.get_user_directory_profile(requestor_raw) or {}
        payload = {
            "requested_role": role_code,
            "reason": justification_text,
            "requestor_login_identifier": str(profile.get("login_identifier") or requestor_raw).strip(),
            "requestor_email": str(profile.get("email") or "").strip() or None,
            "requestor_network_id": str(profile.get("network_id") or "").strip() or None,
            "requestor_first_name": str(profile.get("first_name") or "").strip() or None,
            "requestor_last_name": str(profile.get("last_name") or "").strip() or None,
            "requestor_employee_id": str(profile.get("employee_id") or "").strip() or None,
            "requestor_manager_id": str(profile.get("manager_id") or "").strip() or None,
        }
        return self.create_vendor_change_request(
            vendor_id=GLOBAL_CHANGE_VENDOR_ID,
            requestor_user_principal=requestor_raw,
            change_type="request_access",
            payload=payload,
        )

    def create_vendor_change_request(
        self, vendor_id: str, requestor_user_principal: str, change_type: str, payload: dict
    ) -> str:
        request_id = str(uuid.uuid4())
        now = self._now()
        change_type_clean = (change_type or "").strip().lower()
        vendor_id_clean = str(vendor_id or "").strip() or GLOBAL_CHANGE_VENDOR_ID
        payload_clean = self._prepare_change_request_payload(change_type_clean, payload or {})
        requestor_ref = self._actor_ref(requestor_user_principal)

        try:
            self._execute_file(
                "inserts/create_vendor_change_request.sql",
                params=(
                    request_id,
                    vendor_id_clean,
                    requestor_ref,
                    change_type_clean,
                    self._serialize_payload(payload_clean),
                    "submitted",
                    now,
                    now,
                ),
                app_vendor_change_request=self._table("app_vendor_change_request"),
            )
        except Exception as exc:
            raise RuntimeError("Could not persist change request.") from exc

        try:
            self._execute_file(
                "inserts/create_workflow_event.sql",
                params=(
                    str(uuid.uuid4()),
                    "vendor_change_request",
                    request_id,
                    None,
                    "submitted",
                    requestor_ref,
                    now,
                    f"{change_type_clean} request created",
                ),
                audit_workflow_event=self._table("audit_workflow_event"),
            )
        except Exception:
            LOGGER.debug(
                "Failed to write workflow creation event for request '%s'.",
                request_id,
                exc_info=True,
            )

        return request_id

    def apply_vendor_profile_update(
        self,
        vendor_id: str,
        actor_user_principal: str,
        updates: dict[str, Any],
        reason: str,
    ) -> dict[str, str]:
        normalized_update_keys = {str(key or "").strip().lower() for key in dict(updates or {}).keys()}
        if "lob" in normalized_update_keys:
            raise ValueError("Field 'lob' is no longer supported. Use 'business_unit' instead.")

        allowed_fields = {
            "legal_name",
            "display_name",
            "lifecycle_state",
            "owner_org_id",
            "business_unit_ids",
            "risk_tier",
            "vendor_category",
            "compliance_category",
            "gl_category",
            "delegated_vendor_flag",
            "health_care_vendor_flag",
        }
        clean_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        if not reason.strip():
            raise ValueError("A reason is required for audited updates.")

        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        request_id = str(uuid.uuid4())
        change_event_id = str(uuid.uuid4())

        existing = self._query_file(
            "ingestion/select_vendor_profile_by_id.sql",
            params=(vendor_id,),
            columns=[],
            core_vendor=self._report_table("core_vendor"),
        )
        if existing.empty:
            raise ValueError("Vendor not found.")
        old_row = existing.iloc[0].to_dict()
        existing_columns = {str(column).strip().lower() for column in list(existing.columns)}
        canonical_only_updates = {}
        if "business_unit_ids" in clean_updates:
            canonical_only_updates["business_unit_ids"] = clean_updates.get("business_unit_ids")
        core_updates = {
            k: v
            for k, v in clean_updates.items()
            if k != "business_unit_ids" and str(k).strip().lower() in existing_columns
        }
        if not core_updates and not canonical_only_updates:
            raise ValueError("No editable fields were provided.")

        # Create and immediately approve a change request so all direct edits remain traceable.
        try:
            self._execute_file(
                "inserts/create_vendor_change_request.sql",
                params=(
                    request_id,
                    vendor_id,
                    actor_ref,
                    "direct_update_vendor_profile",
                    self._serialize_payload({"updates": clean_updates, "reason": reason}),
                    "approved",
                    now,
                    now,
                ),
                app_vendor_change_request=self._table("app_vendor_change_request"),
            )
            self._execute_file(
                "inserts/create_workflow_event.sql",
                params=(
                    str(uuid.uuid4()),
                    "vendor_change_request",
                    request_id,
                    "submitted",
                    "approved",
                    actor_ref,
                    now,
                    "Direct vendor profile update approved and applied.",
                ),
                audit_workflow_event=self._table("audit_workflow_event"),
            )
        except (DataExecutionError, DataConnectionError):
            # Continue to apply update even if app workflow tables are unavailable.
            LOGGER.warning(
                "Failed to persist direct update workflow records for vendor '%s'.",
                vendor_id,
                exc_info=True,
            )

        if core_updates:
            set_clause = ", ".join([f"{field} = %s" for field in core_updates])
            params = list(core_updates.values()) + [now, actor_ref, vendor_id]
            self._execute_file(
                "updates/apply_vendor_profile_update.sql",
                params=tuple(params),
                core_vendor=self._table("core_vendor"),
                set_clause=set_clause,
            )
            updated = self._query_file(
                "ingestion/select_vendor_profile_by_id.sql",
                params=(vendor_id,),
                columns=[],
                core_vendor=self._report_table("core_vendor"),
            )
            new_row = updated.iloc[0].to_dict() if not updated.empty else {**old_row, **core_updates}
        else:
            new_row = dict(old_row)

        self._canonical_upsert_vendor(
            vendor_id=vendor_id,
            legal_name=str(
                clean_updates.get("legal_name")
                or new_row.get("legal_name")
                or old_row.get("legal_name")
                or vendor_id
            ),
            display_name=str(
                clean_updates.get("display_name")
                or new_row.get("display_name")
                or old_row.get("display_name")
                or vendor_id
            ),
            lifecycle_state=(
                clean_updates.get("lifecycle_state")
                or new_row.get("lifecycle_state")
                or old_row.get("lifecycle_state")
                or "draft"
            ),
            owner_org_id=clean_updates.get("owner_org_id", new_row.get("owner_org_id", old_row.get("owner_org_id"))),
            risk_tier=clean_updates.get("risk_tier", new_row.get("risk_tier", old_row.get("risk_tier"))),
            source_system=new_row.get("source_system") if "source_system" in new_row else old_row.get("source_system"),
            vendor_category=(
                clean_updates.get("vendor_category")
                if "vendor_category" in clean_updates
                else new_row.get("vendor_category", old_row.get("vendor_category"))
            ),
            compliance_category=(
                clean_updates.get("compliance_category")
                if "compliance_category" in clean_updates
                else new_row.get("compliance_category", old_row.get("compliance_category"))
            ),
            gl_category=(
                clean_updates.get("gl_category")
                if "gl_category" in clean_updates
                else new_row.get("gl_category", old_row.get("gl_category"))
            ),
            delegated_vendor_flag=(
                clean_updates.get("delegated_vendor_flag")
                if "delegated_vendor_flag" in clean_updates
                else new_row.get("delegated_vendor_flag", old_row.get("delegated_vendor_flag"))
            ),
            health_care_vendor_flag=(
                clean_updates.get("health_care_vendor_flag")
                if "health_care_vendor_flag" in clean_updates
                else new_row.get("health_care_vendor_flag", old_row.get("health_care_vendor_flag"))
            ),
            updated_by=actor_user_principal,
            updated_at=now,
            create_lookup_if_missing=True,
            sync_primary_business_unit_assignment=True,
            source_key_for_primary=f"apply_vendor_profile_update:{vendor_id}",
        )

        business_unit_ids_value = canonical_only_updates.get("business_unit_ids")
        if isinstance(business_unit_ids_value, list):
            primary_candidate = str(core_updates.get("owner_org_id") or new_row.get("owner_org_id") or "").strip()
            for candidate in business_unit_ids_value:
                business_unit_value = str(candidate or "").strip()
                if not business_unit_value:
                    continue
                self._canonical_upsert_vendor_business_unit_assignment(
                    vendor_id=vendor_id,
                    business_unit_value=business_unit_value,
                    source_system="api_update",
                    source_key=f"business_unit_ids:{vendor_id}",
                    is_primary=bool(primary_candidate and primary_candidate.lower() == business_unit_value.lower()),
                    active_flag=True,
                    actor_user_principal=actor_user_principal,
                )

        new_row.update(core_updates)
        if "business_unit_ids" in canonical_only_updates:
            new_row["business_unit_ids"] = canonical_only_updates["business_unit_ids"]

        # Maintain SCD-style vendor history.
        try:
            version_df = self._query_file(
                "ingestion/select_next_hist_vendor_version.sql",
                params=(vendor_id,),
                columns=["next_version"],
                hist_vendor=self._table("hist_vendor"),
            )
            next_version = int(version_df.iloc[0]["next_version"]) if not version_df.empty else 1

            self._execute_file(
                "updates/apply_vendor_hist_close_current.sql",
                params=(now, vendor_id),
                hist_vendor=self._table("hist_vendor"),
            )
            self._execute_file(
                "inserts/apply_vendor_hist_insert.sql",
                params=(
                    str(uuid.uuid4()),
                    vendor_id,
                    next_version,
                    now,
                    None,
                    True,
                    json.dumps(new_row, default=str),
                    actor_ref,
                    reason,
                ),
                hist_vendor=self._table("hist_vendor"),
            )
        except (DataExecutionError, DataConnectionError):
            LOGGER.warning("Failed to maintain vendor history for '%s'.", vendor_id, exc_info=True)

        try:
            self._execute_file(
                "inserts/audit_entity_change.sql",
                params=(
                    change_event_id,
                    "core_vendor",
                    vendor_id,
                    "update",
                    json.dumps(old_row, default=str),
                    json.dumps(new_row, default=str),
                    actor_ref,
                    now,
                    request_id,
                ),
                audit_entity_change=self._table("audit_entity_change"),
            )
        except (DataExecutionError, DataConnectionError):
            LOGGER.warning("Failed to write vendor audit record for '%s'.", vendor_id, exc_info=True)

        return {"request_id": request_id, "change_event_id": change_event_id}
