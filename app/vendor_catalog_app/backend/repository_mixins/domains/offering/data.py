from __future__ import annotations

import logging
import uuid
from typing import Any

import pandas as pd
from vendor_catalog_app.core.repository_constants import *

LOGGER = logging.getLogger(__name__)
class RepositoryOfferingDataMixin:
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

    def list_offering_invoices(self, vendor_id: str, offering_id: str) -> pd.DataFrame:
        self._ensure_local_offering_extension_tables()
        rows = self._query_file(
            "ingestion/select_offering_invoices.sql",
            params=(offering_id, vendor_id),
            columns=[
                "invoice_id",
                "offering_id",
                "vendor_id",
                "invoice_number",
                "invoice_date",
                "amount",
                "currency_code",
                "invoice_status",
                "notes",
                "active_flag",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ],
            app_offering_invoice=self._table("app_offering_invoice"),
        )
        if rows.empty:
            return rows
        rows["amount"] = pd.to_numeric(rows.get("amount"), errors="coerce").fillna(0.0)
        return self._decorate_user_columns(rows, ["created_by", "updated_by"])

    def get_offering_invoice(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        invoice_id: str,
    ) -> dict[str, Any] | None:
        self._ensure_local_offering_extension_tables()
        rows = self._query_file(
            "ingestion/select_offering_invoice_by_id.sql",
            params=(invoice_id, offering_id, vendor_id),
            columns=[
                "invoice_id",
                "offering_id",
                "vendor_id",
                "invoice_number",
                "invoice_date",
                "amount",
                "currency_code",
                "invoice_status",
                "notes",
                "active_flag",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ],
            app_offering_invoice=self._table("app_offering_invoice"),
        )
        if rows.empty:
            return None
        out = rows.iloc[0].to_dict()
        try:
            out["amount"] = float(out.get("amount") or 0.0)
        except Exception:
            out["amount"] = 0.0
        return out

    def add_offering_invoice(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        invoice_number: str | None,
        invoice_date: str,
        amount: float,
        currency_code: str | None,
        invoice_status: str | None,
        notes: str | None,
        actor_user_principal: str,
    ) -> str:
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to this vendor.")

        parsed_invoice_date = pd.to_datetime(str(invoice_date or "").strip(), errors="coerce")
        if pd.isna(parsed_invoice_date):
            raise ValueError("Invoice date is required and must be valid.")
        invoice_date_value = parsed_invoice_date.date().isoformat()

        try:
            amount_value = float(amount)
        except Exception as exc:
            raise ValueError("Invoice amount must be numeric.") from exc
        if amount_value <= 0:
            raise ValueError("Invoice amount must be greater than zero.")

        status_value = str(invoice_status or "").strip().lower() or "received"
        allowed_statuses = {"received", "approved", "paid", "disputed", "void"}
        if status_value not in allowed_statuses:
            raise ValueError(f"Invoice status must be one of: {', '.join(sorted(allowed_statuses))}.")

        currency_value = str(currency_code or "").strip().upper() or "USD"
        if len(currency_value) > 8:
            raise ValueError("Currency code must be 8 characters or fewer.")

        invoice_id = self._new_id("oinv")
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        row = {
            "invoice_id": invoice_id,
            "offering_id": offering_id,
            "vendor_id": vendor_id,
            "invoice_number": str(invoice_number or "").strip() or None,
            "invoice_date": invoice_date_value,
            "amount": amount_value,
            "currency_code": currency_value,
            "invoice_status": status_value,
            "notes": str(notes or "").strip() or None,
            "active_flag": True,
            "created_at": now.isoformat(),
            "created_by": actor_ref,
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }
        self._ensure_local_offering_extension_tables()
        self._execute_file(
            "inserts/create_offering_invoice.sql",
            params=(
                row["invoice_id"],
                row["offering_id"],
                row["vendor_id"],
                row["invoice_number"],
                row["invoice_date"],
                row["amount"],
                row["currency_code"],
                row["invoice_status"],
                row["notes"],
                row["active_flag"],
                now,
                actor_ref,
                now,
                actor_ref,
            ),
            app_offering_invoice=self._table("app_offering_invoice"),
        )
        self._write_audit_entity_change(
            entity_name="app_offering_invoice",
            entity_id=invoice_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return invoice_id

    def remove_offering_invoice(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        invoice_id: str,
        actor_user_principal: str,
    ) -> None:
        current = self.get_offering_invoice(vendor_id=vendor_id, offering_id=offering_id, invoice_id=invoice_id)
        if current is None:
            raise ValueError("Offering invoice was not found.")
        actor_ref = self._actor_ref(actor_user_principal)
        now = self._now()
        self._execute_file(
            "updates/remove_offering_invoice_soft.sql",
            params=(now, actor_ref, invoice_id, offering_id, vendor_id),
            app_offering_invoice=self._table("app_offering_invoice"),
        )
        self._write_audit_entity_change(
            entity_name="app_offering_invoice",
            entity_id=invoice_id,
            action_type="delete",
            actor_user_principal=actor_user_principal,
            before_json=current,
            after_json=None,
            request_id=None,
        )

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


