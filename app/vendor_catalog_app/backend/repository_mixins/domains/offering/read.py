from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from vendor_catalog_app.core.repository_constants import *

LOGGER = logging.getLogger(__name__)
class RepositoryOfferingReadMixin:
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


