from __future__ import annotations

import logging
import uuid
from typing import Any

import pandas as pd
from vendor_catalog_app.core.repository_constants import *

LOGGER = logging.getLogger(__name__)


class RepositoryWorkflowDemoMixin:
    def demo_outcomes(self) -> pd.DataFrame:
        return self._cached(
            ("demo_outcomes",),
            lambda: self.client.query(
                self._sql(
                    "reporting/demo_outcomes.sql",
                    core_vendor_demo=self._table("core_vendor_demo"),
                )
            ),
            ttl_seconds=60,
        )

    def get_demo_outcome_by_id(self, demo_id: str) -> dict[str, Any] | None:
        demo_key = str(demo_id or "").strip()
        if not demo_key:
            return None
        rows = self._query_file(
            "ingestion/select_demo_outcome_by_id.sql",
            params=(demo_key,),
            columns=[
                "demo_id",
                "vendor_id",
                "offering_id",
                "demo_date",
                "overall_score",
                "selection_outcome",
                "non_selection_reason_code",
                "notes",
                "updated_at",
                "updated_by",
            ],
            core_vendor_demo=self._table("core_vendor_demo"),
        )
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def list_demo_notes_by_demo(
        self,
        demo_id: str,
        *,
        note_type: str | None = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        demo_key = str(demo_id or "").strip()
        if not demo_key:
            return pd.DataFrame(columns=["demo_note_id", "demo_id", "note_type", "note_text", "created_at", "created_by"])
        normalized_note_type = str(note_type or "").strip() or None
        safe_limit = max(1, min(int(limit or 500), 5000))
        return self._cached(
            ("demo_notes_by_demo", demo_key, normalized_note_type or "__all__", safe_limit),
            lambda: self._query_file(
                "ingestion/select_demo_notes_by_demo.sql",
                params=(demo_key, normalized_note_type, normalized_note_type),
                columns=["demo_note_id", "demo_id", "note_type", "note_text", "created_at", "created_by"],
                limit=safe_limit,
                core_vendor_demo_note=self._table("core_vendor_demo_note"),
            ),
            ttl_seconds=60,
        )

    def create_demo_note(
        self,
        *,
        demo_id: str,
        note_type: str,
        note_text: str,
        actor_user_principal: str,
    ) -> str:
        demo_key = str(demo_id or "").strip()
        note_type_key = str(note_type or "").strip().lower()
        payload_text = str(note_text or "").strip()
        if not demo_key:
            raise ValueError("Demo ID is required.")
        if not note_type_key:
            raise ValueError("Note type is required.")
        if not payload_text:
            raise ValueError("Note text is required.")

        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        note_id = str(uuid.uuid4())
        self._execute_file(
            "inserts/create_demo_note.sql",
            params=(note_id, demo_key, note_type_key, payload_text, now, actor_ref),
            core_vendor_demo_note=self._table("core_vendor_demo_note"),
        )
        self._write_audit_entity_change(
            entity_name="core_vendor_demo_note",
            entity_id=note_id,
            action_type="insert",
            actor_user_principal=actor_ref,
            before_json=None,
            after_json={
                "demo_id": demo_key,
                "note_type": note_type_key,
                "note_text": payload_text,
            },
            request_id=None,
        )
        return note_id

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

