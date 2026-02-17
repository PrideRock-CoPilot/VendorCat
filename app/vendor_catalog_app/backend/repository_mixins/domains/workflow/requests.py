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
        allowed_fields = {"legal_name", "display_name", "lifecycle_state", "owner_org_id", "risk_tier"}
        clean_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        if not clean_updates:
            raise ValueError("No editable fields were provided.")
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
            core_vendor=self._table("core_vendor"),
        )
        if existing.empty:
            raise ValueError("Vendor not found.")
        old_row = existing.iloc[0].to_dict()

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

        set_clause = ", ".join([f"{field} = %s" for field in clean_updates])
        params = list(clean_updates.values()) + [now, actor_ref, vendor_id]
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
            core_vendor=self._table("core_vendor"),
        )
        new_row = updated.iloc[0].to_dict() if not updated.empty else {**old_row, **clean_updates}

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
