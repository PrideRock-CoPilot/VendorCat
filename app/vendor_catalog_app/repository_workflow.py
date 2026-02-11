from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from vendor_catalog_app.db import DataConnectionError, DataExecutionError, DataQueryError
from vendor_catalog_app.repository_constants import *
from vendor_catalog_app.repository_errors import SchemaBootstrapRequiredError
from vendor_catalog_app.security import (
    CHANGE_APPROVAL_LEVELS,
    ROLE_ADMIN,
    ROLE_APPROVER,
    ROLE_CHOICES,
    ROLE_STEWARD,
    ROLE_SYSTEM_ADMIN,
    ROLE_VIEWER,
    default_change_permissions_for_role,
    default_role_definitions,
    required_approval_level,
)

LOGGER = logging.getLogger(__name__)

class RepositoryWorkflowMixin:
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

        set_clause = ", ".join([f"{field} = %s" for field in clean_updates.keys()])
        params = list(clean_updates.values()) + [now, actor_user_principal, vendor_id]
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

    def demo_outcomes(self) -> pd.DataFrame:
        return self.client.query(
            self._sql(
                "reporting/demo_outcomes.sql",
                core_vendor_demo=self._table("core_vendor_demo"),
            )
        )

    def create_demo_outcome(
        self,
        vendor_id: str,
        offering_id: str | None,
        demo_date: str,
        overall_score: float,
        selection_outcome: str,
        non_selection_reason_code: str | None,
        notes: str,
        actor_user_principal: str,
    ) -> str:
        demo_id = str(uuid.uuid4())
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        self._execute_file(
            "inserts/create_demo_outcome.sql",
            params=(
                demo_id,
                vendor_id,
                offering_id,
                demo_date,
                overall_score,
                selection_outcome,
                non_selection_reason_code,
                notes,
                now,
                actor_ref,
            ),
            core_vendor_demo=self._table("core_vendor_demo"),
        )

        self._write_audit_entity_change(
            entity_name="core_vendor_demo",
            entity_id=demo_id,
            action_type="insert",
            actor_user_principal=actor_ref,
            before_json=None,
            after_json={
                "vendor_id": vendor_id,
                "offering_id": offering_id,
                "demo_date": demo_date,
                "overall_score": overall_score,
                "selection_outcome": selection_outcome,
                "non_selection_reason_code": non_selection_reason_code,
                "notes": notes,
            },
            request_id=None,
        )
        return demo_id

    def contract_cancellations(self) -> pd.DataFrame:
        return self.client.query(
            self._sql(
                "reporting/contract_cancellations.sql",
                rpt_contract_cancellations=self._table("rpt_contract_cancellations"),
            )
        )

