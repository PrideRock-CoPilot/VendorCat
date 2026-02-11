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

class RepositoryOfferingMixin:
    def _new_id(self, prefix: str) -> str:
        return f"{str(prefix).strip().lower()}-{uuid.uuid4()}"

    @staticmethod
    def _normalize_offering_id(offering_id: str | None) -> str | None:
        if offering_id is None:
            return None
        cleaned = str(offering_id).strip()
        return cleaned or None

    def get_offering_record(self, vendor_id: str, offering_id: str) -> dict[str, Any] | None:
        offerings = self.get_vendor_offerings(vendor_id)
        if offerings.empty:
            return None
        matched = offerings[offerings["offering_id"].astype(str) == str(offering_id)]
        if matched.empty:
            return None
        return matched.iloc[0].to_dict()

    def get_offering_profile(self, vendor_id: str, offering_id: str) -> dict[str, Any]:
        default = {
            "offering_id": offering_id,
            "vendor_id": vendor_id,
            "estimated_monthly_cost": None,
            "implementation_notes": None,
            "data_sent": None,
            "data_received": None,
            "integration_method": None,
            "inbound_method": None,
            "inbound_landing_zone": None,
            "inbound_identifiers": None,
            "inbound_reporting_layer": None,
            "inbound_ingestion_notes": None,
            "outbound_method": None,
            "outbound_creation_process": None,
            "outbound_delivery_process": None,
            "outbound_responsible_owner": None,
            "outbound_notes": None,
            "updated_at": None,
            "updated_by": None,
        }
        self._ensure_local_offering_extension_tables()
        rows = self._query_file(
            "ingestion/select_offering_profile.sql",
            params=(offering_id, vendor_id),
            columns=[
                "offering_id",
                "vendor_id",
                "estimated_monthly_cost",
                "implementation_notes",
                "data_sent",
                "data_received",
                "integration_method",
                "inbound_method",
                "inbound_landing_zone",
                "inbound_identifiers",
                "inbound_reporting_layer",
                "inbound_ingestion_notes",
                "outbound_method",
                "outbound_creation_process",
                "outbound_delivery_process",
                "outbound_responsible_owner",
                "outbound_notes",
                "updated_at",
                "updated_by",
            ],
            app_offering_profile=self._table("app_offering_profile"),
        )
        if rows.empty:
            return default
        row = rows.iloc[0].to_dict()
        out = dict(default)
        out.update(row)
        return out

    def save_offering_profile(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        actor_user_principal: str,
        updates: dict[str, Any],
        reason: str,
    ) -> dict[str, str]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to this vendor.")

        allowed = {
            "estimated_monthly_cost",
            "implementation_notes",
            "data_sent",
            "data_received",
            "integration_method",
            "inbound_method",
            "inbound_landing_zone",
            "inbound_identifiers",
            "inbound_reporting_layer",
            "inbound_ingestion_notes",
            "outbound_method",
            "outbound_creation_process",
            "outbound_delivery_process",
            "outbound_responsible_owner",
            "outbound_notes",
        }
        clean_updates = {k: v for k, v in updates.items() if k in allowed}
        if not clean_updates:
            raise ValueError("No profile fields were provided.")
        if "outbound_responsible_owner" in clean_updates:
            candidate_owner = str(clean_updates.get("outbound_responsible_owner") or "").strip()
            if candidate_owner:
                resolved_owner = self.resolve_user_id(candidate_owner, allow_create=True)
                if not resolved_owner:
                    raise ValueError("Outbound responsible owner must exist in the app user directory.")
                clean_updates["outbound_responsible_owner"] = resolved_owner
            else:
                clean_updates["outbound_responsible_owner"] = None

        current = self.get_offering_profile(vendor_id, offering_id)
        had_existing = any(current.get(field) not in (None, "") for field in allowed)
        before = dict(current)
        after = dict(current)
        after.update(clean_updates)

        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        request_id = str(uuid.uuid4())
        payload = {
            "offering_id": offering_id,
            "vendor_id": vendor_id,
            "estimated_monthly_cost": after.get("estimated_monthly_cost"),
            "implementation_notes": after.get("implementation_notes"),
            "data_sent": after.get("data_sent"),
            "data_received": after.get("data_received"),
            "integration_method": after.get("integration_method"),
            "inbound_method": after.get("inbound_method"),
            "inbound_landing_zone": after.get("inbound_landing_zone"),
            "inbound_identifiers": after.get("inbound_identifiers"),
            "inbound_reporting_layer": after.get("inbound_reporting_layer"),
            "inbound_ingestion_notes": after.get("inbound_ingestion_notes"),
            "outbound_method": after.get("outbound_method"),
            "outbound_creation_process": after.get("outbound_creation_process"),
            "outbound_delivery_process": after.get("outbound_delivery_process"),
            "outbound_responsible_owner": after.get("outbound_responsible_owner"),
            "outbound_notes": after.get("outbound_notes"),
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }

        self._ensure_local_offering_extension_tables()
        existing = self._query_file(
            "ingestion/select_offering_profile.sql",
            params=(offering_id, vendor_id),
            columns=["offering_id"],
            app_offering_profile=self._table("app_offering_profile"),
        )
        if existing.empty:
            self._execute_file(
                "inserts/create_offering_profile.sql",
                params=(
                    offering_id,
                    vendor_id,
                    payload["estimated_monthly_cost"],
                    payload["implementation_notes"],
                    payload["data_sent"],
                    payload["data_received"],
                    payload["integration_method"],
                    payload["inbound_method"],
                    payload["inbound_landing_zone"],
                    payload["inbound_identifiers"],
                    payload["inbound_reporting_layer"],
                    payload["inbound_ingestion_notes"],
                    payload["outbound_method"],
                    payload["outbound_creation_process"],
                    payload["outbound_delivery_process"],
                    payload["outbound_responsible_owner"],
                    payload["outbound_notes"],
                    now,
                    actor_ref,
                ),
                app_offering_profile=self._table("app_offering_profile"),
            )
            action_type = "insert"
            before_json = None
        else:
            self._execute_file(
                "updates/update_offering_profile.sql",
                params=(
                    payload["estimated_monthly_cost"],
                    payload["implementation_notes"],
                    payload["data_sent"],
                    payload["data_received"],
                    payload["integration_method"],
                    payload["inbound_method"],
                    payload["inbound_landing_zone"],
                    payload["inbound_identifiers"],
                    payload["inbound_reporting_layer"],
                    payload["inbound_ingestion_notes"],
                    payload["outbound_method"],
                    payload["outbound_creation_process"],
                    payload["outbound_delivery_process"],
                    payload["outbound_responsible_owner"],
                    payload["outbound_notes"],
                    now,
                    actor_ref,
                    offering_id,
                    vendor_id,
                ),
                app_offering_profile=self._table("app_offering_profile"),
            )
            action_type = "update"
            before_json = before

        change_event_id = self._write_audit_entity_change(
            entity_name="app_offering_profile",
            entity_id=offering_id,
            action_type=action_type,
            actor_user_principal=actor_user_principal,
            before_json=before_json,
            after_json=payload,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def list_offering_data_flows(self, vendor_id: str, offering_id: str) -> pd.DataFrame:
        self._ensure_local_offering_extension_tables()
        rows = self._query_file(
            "ingestion/select_offering_data_flows.sql",
            params=(offering_id, vendor_id),
            columns=[
                "data_flow_id",
                "offering_id",
                "vendor_id",
                "direction",
                "flow_name",
                "method",
                "data_description",
                "endpoint_details",
                "identifiers",
                "reporting_layer",
                "creation_process",
                "delivery_process",
                "owner_user_principal",
                "notes",
                "active_flag",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ],
            app_offering_data_flow=self._table("app_offering_data_flow"),
        )
        return self._decorate_user_columns(rows, ["owner_user_principal", "created_by", "updated_by"])

    def get_offering_data_flow(self, *, vendor_id: str, offering_id: str, data_flow_id: str) -> dict[str, Any] | None:
        self._ensure_local_offering_extension_tables()
        rows = self._query_file(
            "ingestion/select_offering_data_flow_by_id.sql",
            params=(data_flow_id, offering_id, vendor_id),
            columns=[
                "data_flow_id",
                "offering_id",
                "vendor_id",
                "direction",
                "flow_name",
                "method",
                "data_description",
                "endpoint_details",
                "identifiers",
                "reporting_layer",
                "creation_process",
                "delivery_process",
                "owner_user_principal",
                "notes",
                "active_flag",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ],
            app_offering_data_flow=self._table("app_offering_data_flow"),
        )
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def add_offering_data_flow(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        direction: str,
        flow_name: str,
        method: str | None,
        data_description: str | None,
        endpoint_details: str | None,
        identifiers: str | None,
        reporting_layer: str | None,
        creation_process: str | None,
        delivery_process: str | None,
        owner_user_principal: str | None,
        notes: str | None,
        actor_user_principal: str,
    ) -> str:
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to this vendor.")
        clean_direction = str(direction or "").strip().lower()
        if clean_direction not in {"inbound", "outbound"}:
            raise ValueError("Direction must be inbound or outbound.")
        clean_flow_name = str(flow_name or "").strip()
        if not clean_flow_name:
            raise ValueError("Data flow name is required.")
        clean_method = str(method or "").strip().lower() or None
        clean_data_description = str(data_description or "").strip() or None
        clean_endpoint_details = str(endpoint_details or "").strip() or None
        clean_identifiers = str(identifiers or "").strip() or None
        clean_reporting_layer = str(reporting_layer or "").strip() or None
        clean_creation_process = str(creation_process or "").strip() or None
        clean_delivery_process = str(delivery_process or "").strip() or None
        clean_notes = str(notes or "").strip() or None
        clean_owner = str(owner_user_principal or "").strip()
        resolved_owner: str | None = None
        if clean_owner:
            resolved_owner = self.resolve_user_id(clean_owner, allow_create=True)
            if not resolved_owner:
                raise ValueError("Owner must exist in the app user directory.")

        data_flow_id = self._new_id("odf")
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        row = {
            "data_flow_id": data_flow_id,
            "offering_id": offering_id,
            "vendor_id": vendor_id,
            "direction": clean_direction,
            "flow_name": clean_flow_name,
            "method": clean_method,
            "data_description": clean_data_description,
            "endpoint_details": clean_endpoint_details,
            "identifiers": clean_identifiers,
            "reporting_layer": clean_reporting_layer,
            "creation_process": clean_creation_process,
            "delivery_process": clean_delivery_process,
            "owner_user_principal": resolved_owner,
            "notes": clean_notes,
            "active_flag": True,
            "created_at": now.isoformat(),
            "created_by": actor_ref,
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }
        self._ensure_local_offering_extension_tables()
        self._execute_file(
            "inserts/create_offering_data_flow.sql",
            params=(
                data_flow_id,
                offering_id,
                vendor_id,
                clean_direction,
                clean_flow_name,
                clean_method,
                clean_data_description,
                clean_endpoint_details,
                clean_identifiers,
                clean_reporting_layer,
                clean_creation_process,
                clean_delivery_process,
                resolved_owner,
                clean_notes,
                True,
                now,
                actor_ref,
                now,
                actor_ref,
            ),
            app_offering_data_flow=self._table("app_offering_data_flow"),
        )
        self._write_audit_entity_change(
            entity_name="app_offering_data_flow",
            entity_id=data_flow_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return data_flow_id

    def remove_offering_data_flow(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        data_flow_id: str,
        actor_user_principal: str,
    ) -> None:
        current = self.get_offering_data_flow(
            vendor_id=vendor_id,
            offering_id=offering_id,
            data_flow_id=data_flow_id,
        )
        if current is None:
            raise ValueError("Offering data flow was not found.")
        actor_ref = self._actor_ref(actor_user_principal)
        self._execute_file(
            "updates/remove_offering_data_flow_soft.sql",
            params=(self._now(), actor_ref, data_flow_id, offering_id, vendor_id),
            app_offering_data_flow=self._table("app_offering_data_flow"),
        )
        self._write_audit_entity_change(
            entity_name="app_offering_data_flow",
            entity_id=data_flow_id,
            action_type="delete",
            actor_user_principal=actor_user_principal,
            before_json=current,
            after_json=None,
            request_id=None,
        )

    def update_offering_data_flow(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        data_flow_id: str,
        actor_user_principal: str,
        updates: dict[str, Any],
        reason: str,
    ) -> dict[str, str]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to this vendor.")
        current = self.get_offering_data_flow(
            vendor_id=vendor_id,
            offering_id=offering_id,
            data_flow_id=data_flow_id,
        )
        if current is None:
            raise ValueError("Offering data flow was not found.")

        allowed = {
            "direction",
            "flow_name",
            "method",
            "data_description",
            "endpoint_details",
            "identifiers",
            "reporting_layer",
            "creation_process",
            "delivery_process",
            "owner_user_principal",
            "notes",
        }
        clean_updates = {k: v for k, v in updates.items() if k in allowed}
        if not clean_updates:
            raise ValueError("No data flow fields were provided.")

        if "direction" in clean_updates:
            direction = str(clean_updates.get("direction") or "").strip().lower()
            if direction not in {"inbound", "outbound"}:
                raise ValueError("Direction must be inbound or outbound.")
            clean_updates["direction"] = direction
        if "flow_name" in clean_updates:
            flow_name = str(clean_updates.get("flow_name") or "").strip()
            if not flow_name:
                raise ValueError("Data flow name is required.")
            clean_updates["flow_name"] = flow_name
        if "method" in clean_updates:
            clean_updates["method"] = str(clean_updates.get("method") or "").strip().lower() or None
        for optional_text_key in {
            "data_description",
            "endpoint_details",
            "identifiers",
            "reporting_layer",
            "creation_process",
            "delivery_process",
            "notes",
        }:
            if optional_text_key in clean_updates:
                clean_updates[optional_text_key] = str(clean_updates.get(optional_text_key) or "").strip() or None
        if "owner_user_principal" in clean_updates:
            owner_candidate = str(clean_updates.get("owner_user_principal") or "").strip()
            if owner_candidate:
                resolved_owner = self.resolve_user_id(owner_candidate, allow_create=True)
                if not resolved_owner:
                    raise ValueError("Owner must exist in the app user directory.")
                clean_updates["owner_user_principal"] = resolved_owner
            else:
                clean_updates["owner_user_principal"] = None

        before = dict(current)
        after = dict(current)
        after.update(clean_updates)
        request_id = str(uuid.uuid4())
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        clean_updates["updated_at"] = now.isoformat()
        clean_updates["updated_by"] = actor_ref

        set_clause = ", ".join(
            [f"{key} = %s" for key in clean_updates.keys() if key not in {"updated_at", "updated_by"}]
        )
        params = [clean_updates[key] for key in clean_updates.keys() if key not in {"updated_at", "updated_by"}]
        self._execute_file(
            "updates/update_offering_data_flow.sql",
            params=tuple(params + [now, actor_ref, data_flow_id, offering_id, vendor_id]),
            app_offering_data_flow=self._table("app_offering_data_flow"),
            set_clause=set_clause,
        )

        after.update(clean_updates)
        change_event_id = self._write_audit_entity_change(
            entity_name="app_offering_data_flow",
            entity_id=data_flow_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def list_offering_tickets(self, vendor_id: str, offering_id: str) -> pd.DataFrame:
        self._ensure_local_offering_extension_tables()
        rows = self._query_file(
            "ingestion/select_offering_tickets.sql",
            params=(offering_id, vendor_id),
            columns=[
                "ticket_id",
                "offering_id",
                "vendor_id",
                "ticket_system",
                "external_ticket_id",
                "title",
                "status",
                "priority",
                "opened_date",
                "closed_date",
                "notes",
                "active_flag",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ],
            app_offering_ticket=self._table("app_offering_ticket"),
        )
        return self._decorate_user_columns(rows, ["created_by", "updated_by"])

    def add_offering_ticket(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        title: str,
        ticket_system: str | None,
        external_ticket_id: str | None,
        status: str,
        priority: str | None,
        opened_date: str | None,
        notes: str | None,
        actor_user_principal: str,
    ) -> str:
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to this vendor.")
        clean_title = str(title or "").strip()
        clean_status = str(status or "").strip().lower() or "open"
        if not clean_title:
            raise ValueError("Ticket title is required.")

        ticket_id = self._new_id("otk")
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        row = {
            "ticket_id": ticket_id,
            "offering_id": offering_id,
            "vendor_id": vendor_id,
            "ticket_system": str(ticket_system or "").strip() or None,
            "external_ticket_id": str(external_ticket_id or "").strip() or None,
            "title": clean_title,
            "status": clean_status,
            "priority": str(priority or "").strip().lower() or None,
            "opened_date": str(opened_date or "").strip() or None,
            "closed_date": None,
            "notes": str(notes or "").strip() or None,
            "active_flag": True,
            "created_at": now.isoformat(),
            "created_by": actor_ref,
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }

        self._ensure_local_offering_extension_tables()
        self._execute_file(
            "inserts/create_offering_ticket.sql",
            params=(
                ticket_id,
                offering_id,
                vendor_id,
                row["ticket_system"],
                row["external_ticket_id"],
                clean_title,
                clean_status,
                row["priority"],
                row["opened_date"],
                row["closed_date"],
                row["notes"],
                True,
                now,
                actor_ref,
                now,
                actor_ref,
            ),
            app_offering_ticket=self._table("app_offering_ticket"),
        )
        self._write_audit_entity_change(
            entity_name="app_offering_ticket",
            entity_id=ticket_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return ticket_id

    def update_offering_ticket(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        ticket_id: str,
        actor_user_principal: str,
        updates: dict[str, Any],
        reason: str,
    ) -> dict[str, str]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to this vendor.")

        allowed = {
            "ticket_system",
            "external_ticket_id",
            "title",
            "status",
            "priority",
            "opened_date",
            "closed_date",
            "notes",
        }
        clean_updates = {k: v for k, v in updates.items() if k in allowed}
        if not clean_updates:
            raise ValueError("No ticket fields were provided.")

        self._ensure_local_offering_extension_tables()
        match = self._query_file(
            "ingestion/select_offering_ticket_by_id.sql",
            params=(ticket_id, offering_id, vendor_id),
            columns=[
                "ticket_id",
                "offering_id",
                "vendor_id",
                "ticket_system",
                "external_ticket_id",
                "title",
                "status",
                "priority",
                "opened_date",
                "closed_date",
                "notes",
                "active_flag",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ],
            app_offering_ticket=self._table("app_offering_ticket"),
        )

        if match.empty:
            raise ValueError("Ticket not found for this offering.")
        current = match.iloc[0].to_dict()
        before = dict(current)
        after = dict(current)
        after.update(clean_updates)
        request_id = str(uuid.uuid4())
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        clean_updates["updated_at"] = now.isoformat()
        clean_updates["updated_by"] = actor_ref

        set_clause = ", ".join([f"{key} = %s" for key in clean_updates.keys() if key not in {"updated_at", "updated_by"}])
        params = [clean_updates[key] for key in clean_updates.keys() if key not in {"updated_at", "updated_by"}]
        self._execute_file(
            "updates/update_offering_ticket.sql",
            params=tuple(params + [now, actor_ref, ticket_id, offering_id, vendor_id]),
            app_offering_ticket=self._table("app_offering_ticket"),
            set_clause=set_clause,
        )

        after.update(clean_updates)
        change_event_id = self._write_audit_entity_change(
            entity_name="app_offering_ticket",
            entity_id=ticket_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def list_offering_notes(self, offering_id: str, note_type: str | None = None) -> pd.DataFrame:
        normalized_type = str(note_type or "").strip().lower()
        note_type_clause = "AND lower(note_type) = lower(%s)" if normalized_type else ""
        params: tuple[Any, ...] = (offering_id, normalized_type) if normalized_type else (offering_id,)
        rows = self._query_file(
            "ingestion/select_offering_notes.sql",
            params=params,
            columns=["note_id", "entity_name", "entity_id", "note_type", "note_text", "created_at", "created_by"],
            note_type_clause=note_type_clause,
            app_note=self._table("app_note"),
        )
        return self._decorate_user_columns(rows, ["created_by"])

    def add_offering_note(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        note_type: str,
        note_text: str,
        actor_user_principal: str,
    ) -> str:
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to this vendor.")
        clean_note_type = str(note_type or "").strip().lower() or "general"
        clean_note_text = str(note_text or "").strip()
        if not clean_note_text:
            raise ValueError("Note text is required.")

        note_id = self._new_id("ont")
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        row = {
            "note_id": note_id,
            "entity_name": "offering",
            "entity_id": offering_id,
            "note_type": clean_note_type,
            "note_text": clean_note_text,
            "created_at": now.isoformat(),
            "created_by": actor_ref,
        }
        self._execute_file(
            "inserts/add_offering_note.sql",
            params=(
                note_id,
                "offering",
                offering_id,
                clean_note_type,
                clean_note_text,
                now,
                actor_ref,
            ),
            app_note=self._table("app_note"),
        )
        self._write_audit_entity_change(
            entity_name="app_note",
            entity_id=note_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return note_id

    def get_offering_activity(self, vendor_id: str, offering_id: str) -> pd.DataFrame:
        self._ensure_local_offering_extension_tables()
        out = self._query_file(
            "ingestion/select_offering_activity.sql",
            params=(offering_id, offering_id, offering_id, offering_id, offering_id),
            columns=[
                "change_event_id",
                "entity_name",
                "entity_id",
                "action_type",
                "before_json",
                "after_json",
                "event_ts",
                "actor_user_principal",
                "request_id",
            ],
            audit_entity_change=self._table("audit_entity_change"),
            app_offering_data_flow=self._table("app_offering_data_flow"),
            app_offering_ticket=self._table("app_offering_ticket"),
            app_note=self._table("app_note"),
            app_document_link=self._table("app_document_link"),
        )
        out = self._with_audit_change_summaries(out)
        return self._decorate_user_columns(out, ["actor_user_principal"])

    def offering_belongs_to_vendor(self, vendor_id: str, offering_id: str) -> bool:
        if not offering_id:
            return False
        check = self._query_file(
            "ingestion/select_offering_belongs_to_vendor.sql",
            params=(vendor_id, offering_id),
            columns=["present"],
            core_vendor_offering=self._table("core_vendor_offering"),
        )
        return not check.empty

    def get_unassigned_contracts(self, vendor_id: str) -> pd.DataFrame:
        contracts = self.get_vendor_contracts(vendor_id).copy()
        if contracts.empty or "offering_id" not in contracts.columns:
            return contracts
        return contracts[
            contracts["offering_id"].isna()
            | (contracts["offering_id"].astype(str).str.strip() == "")
        ].copy()

    def get_unassigned_demos(self, vendor_id: str) -> pd.DataFrame:
        demos = self.get_vendor_demos(vendor_id).copy()
        if demos.empty or "offering_id" not in demos.columns:
            return demos
        return demos[
            demos["offering_id"].isna()
            | (demos["offering_id"].astype(str).str.strip() == "")
        ].copy()

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
        row = {
            "offering_owner_id": owner_id,
            "offering_id": offering_id,
            "owner_user_principal": owner_ref,
            "owner_role": owner_role_value,
            "active_flag": True,
        }
        self._execute_file(
            "inserts/add_offering_owner.sql",
            params=(owner_id, offering_id, row["owner_user_principal"], row["owner_role"], True),
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
        row = {
            "offering_contact_id": contact_id,
            "offering_id": offering_id,
            "contact_type": contact_type_value,
            "full_name": full_name.strip(),
            "email": (email or "").strip() or None,
            "phone": (phone or "").strip() or None,
            "active_flag": True,
        }
        self._execute_file(
            "inserts/add_offering_contact.sql",
            params=(contact_id, offering_id, row["contact_type"], row["full_name"], row["email"], row["phone"], True),
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

