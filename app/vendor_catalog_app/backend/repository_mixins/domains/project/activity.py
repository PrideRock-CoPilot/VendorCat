from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from vendor_catalog_app.core.repository_constants import *

LOGGER = logging.getLogger(__name__)


class RepositoryProjectActivityMixin:
    def list_project_notes(self, vendor_id: str | None, project_id: str) -> pd.DataFrame:
        vendor_clause = "AND vendor_id = %s" if vendor_id else ""
        params: tuple[Any, ...] = (project_id, vendor_id) if vendor_id else (project_id,)
        rows = self._query_file(
            "ingestion/select_project_notes.sql",
            params=params,
            columns=[
                "project_note_id",
                "project_id",
                "vendor_id",
                "note_text",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ],
            vendor_clause=vendor_clause,
            app_project_note=self._table("app_project_note"),
        )
        return self._decorate_user_columns(rows, ["created_by", "updated_by"])

    def add_project_note(
        self,
        *,
        vendor_id: str,
        project_id: str,
        note_text: str,
        actor_user_principal: str,
    ) -> str:
        effective_vendor_id = str(vendor_id or "").strip()
        if not effective_vendor_id:
            vendor_ids = self._project_vendor_ids(project_id)
            effective_vendor_id = vendor_ids[0] if vendor_ids else ""
        if not effective_vendor_id or not self.project_belongs_to_vendor(effective_vendor_id, project_id):
            raise ValueError("Attach a vendor to this project before adding notes.")
        clean_note = (note_text or "").strip()
        if not clean_note:
            raise ValueError("Note text is required.")
        note_id = self._new_id("pnt")
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        row = {
            "project_note_id": note_id,
            "project_id": project_id,
            "vendor_id": effective_vendor_id,
            "note_text": clean_note,
            "active_flag": True,
            "created_at": now.isoformat(),
            "created_by": actor_ref,
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }
        self._execute_file(
            "inserts/add_project_note.sql",
            params=(
                note_id,
                project_id,
                effective_vendor_id,
                clean_note,
                True,
                now,
                actor_ref,
                now,
                actor_ref,
            ),
            app_project_note=self._table("app_project_note"),
        )
        self._write_audit_entity_change(
            entity_name="app_project_note",
            entity_id=note_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return note_id

    def get_project_activity(self, vendor_id: str | None, project_id: str) -> pd.DataFrame:
        out = self._query_file(
            "ingestion/select_project_activity.sql",
            params=(project_id, project_id, vendor_id, vendor_id, project_id, project_id, vendor_id, vendor_id),
            columns=[
                "change_event_id",
                "entity_name",
                "entity_id",
                "action_type",
                "event_ts",
                "actor_user_principal",
                "before_json",
                "after_json",
                "request_id",
            ],
            audit_entity_change=self._table("audit_entity_change"),
            app_project_demo=self._table("app_project_demo"),
            app_document_link=self._table("app_document_link"),
            app_project_note=self._table("app_project_note"),
        )
        out = self._with_audit_change_summaries(out)
        return self._decorate_user_columns(out, ["actor_user_principal"])

