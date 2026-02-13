from __future__ import annotations

import logging
import uuid
from typing import Any

import pandas as pd
from vendor_catalog_app.core.repository_constants import *

LOGGER = logging.getLogger(__name__)


class RepositoryProjectDemoMixin:
    def list_project_demos(self, vendor_id: str | None, project_id: str) -> pd.DataFrame:
        vendor_clause = "AND vendor_id = %s" if vendor_id else ""
        params: tuple[Any, ...] = (project_id, vendor_id) if vendor_id else (project_id,)
        rows = self._query_file(
            "ingestion/select_project_demos.sql",
            params=params,
            columns=[
                "project_demo_id",
                "project_id",
                "vendor_id",
                "demo_name",
                "demo_datetime_start",
                "demo_datetime_end",
                "demo_type",
                "outcome",
                "score",
                "attendees_internal",
                "attendees_vendor",
                "notes",
                "followups",
                "linked_offering_id",
                "linked_vendor_demo_id",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ],
            vendor_clause=vendor_clause,
            app_project_demo=self._table("app_project_demo"),
        )
        return self._decorate_user_columns(rows, ["created_by", "updated_by"])

    def get_project_demo(self, vendor_id: str | None, project_id: str, project_demo_id: str) -> dict[str, Any] | None:
        demos = self.list_project_demos(vendor_id, project_id)
        if demos.empty:
            return None
        matched = demos[demos["project_demo_id"].astype(str) == str(project_demo_id)]
        if matched.empty:
            return None
        return matched.iloc[0].to_dict()

    def create_project_demo(
        self,
        *,
        vendor_id: str,
        project_id: str,
        actor_user_principal: str,
        demo_name: str,
        demo_datetime_start: str | None = None,
        demo_datetime_end: str | None = None,
        demo_type: str | None = None,
        outcome: str | None = None,
        score: float | None = None,
        attendees_internal: str | None = None,
        attendees_vendor: str | None = None,
        notes: str | None = None,
        followups: str | None = None,
        linked_offering_id: str | None = None,
        linked_vendor_demo_id: str | None = None,
    ) -> str:
        if not self.project_belongs_to_vendor(vendor_id, project_id):
            raise ValueError("Project does not belong to vendor.")
        clean_name = (demo_name or "").strip()
        if not clean_name:
            raise ValueError("Demo name is required.")
        linked_offering_id = self._normalize_offering_id(linked_offering_id)
        if linked_offering_id and not self.offering_belongs_to_vendor(vendor_id, linked_offering_id):
            raise ValueError("Linked offering does not belong to vendor.")
        if linked_vendor_demo_id:
            vendor_demos = self.get_vendor_demos(vendor_id)
            if vendor_demos[vendor_demos["demo_id"].astype(str) == str(linked_vendor_demo_id)].empty:
                raise ValueError("Linked vendor demo does not belong to vendor.")

        demo_id = self._new_id("pdm")
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        row = {
            "project_demo_id": demo_id,
            "project_id": project_id,
            "vendor_id": vendor_id,
            "demo_name": clean_name,
            "demo_datetime_start": (demo_datetime_start or "").strip() or None,
            "demo_datetime_end": (demo_datetime_end or "").strip() or None,
            "demo_type": (demo_type or "").strip() or "live",
            "outcome": (outcome or "").strip() or "unknown",
            "score": score,
            "attendees_internal": (attendees_internal or "").strip() or None,
            "attendees_vendor": (attendees_vendor or "").strip() or None,
            "notes": (notes or "").strip() or None,
            "followups": (followups or "").strip() or None,
            "linked_offering_id": linked_offering_id,
            "linked_vendor_demo_id": (linked_vendor_demo_id or "").strip() or None,
            "active_flag": True,
            "created_at": now.isoformat(),
            "created_by": actor_ref,
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }
        self._execute_file(
            "inserts/create_project_demo.sql",
            params=(
                demo_id,
                project_id,
                vendor_id,
                row["demo_name"],
                row["demo_datetime_start"],
                row["demo_datetime_end"],
                row["demo_type"],
                row["outcome"],
                row["score"],
                row["attendees_internal"],
                row["attendees_vendor"],
                row["notes"],
                row["followups"],
                row["linked_offering_id"],
                row["linked_vendor_demo_id"],
                True,
                now,
                actor_ref,
                now,
                actor_ref,
            ),
            app_project_demo=self._table("app_project_demo"),
        )
        self._write_audit_entity_change(
            entity_name="app_project_demo",
            entity_id=demo_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return demo_id

    def update_project_demo(
        self,
        *,
        vendor_id: str,
        project_id: str,
        project_demo_id: str,
        actor_user_principal: str,
        updates: dict[str, Any],
        reason: str,
    ) -> dict[str, str]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        current = self.get_project_demo(vendor_id, project_id, project_demo_id)
        if current is None:
            raise ValueError("Project demo not found.")
        allowed = {
            "demo_name",
            "demo_datetime_start",
            "demo_datetime_end",
            "demo_type",
            "outcome",
            "score",
            "attendees_internal",
            "attendees_vendor",
            "notes",
            "followups",
            "linked_offering_id",
        }
        clean_updates = {k: v for k, v in updates.items() if k in allowed}
        if "linked_offering_id" in clean_updates:
            clean_updates["linked_offering_id"] = self._normalize_offering_id(clean_updates.get("linked_offering_id"))
            if clean_updates["linked_offering_id"] and not self.offering_belongs_to_vendor(
                vendor_id, clean_updates["linked_offering_id"]
            ):
                raise ValueError("Linked offering does not belong to vendor.")
        if "demo_name" in clean_updates and not str(clean_updates["demo_name"]).strip():
            raise ValueError("Demo name is required.")
        if not clean_updates:
            raise ValueError("No updates were provided.")

        request_id = str(uuid.uuid4())
        before = dict(current)
        after = dict(current)
        after.update(clean_updates)
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        set_clause = ", ".join([f"{k} = %s" for k in clean_updates.keys()])
        params = list(clean_updates.values()) + [now, actor_ref, project_demo_id, project_id, vendor_id]
        self._execute_file(
            "updates/update_project_demo.sql",
            params=tuple(params),
            app_project_demo=self._table("app_project_demo"),
            set_clause=set_clause,
        )
        change_event_id = self._write_audit_entity_change(
            entity_name="app_project_demo",
            entity_id=project_demo_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def remove_project_demo(
        self,
        *,
        vendor_id: str,
        project_id: str,
        project_demo_id: str,
        actor_user_principal: str,
    ) -> None:
        current = self.get_project_demo(vendor_id, project_id, project_demo_id)
        if current is None:
            raise ValueError("Project demo not found.")
        self._execute_file(
            "updates/remove_project_demo_soft.sql",
            params=(self._now(), self._actor_ref(actor_user_principal), project_demo_id, project_id, vendor_id),
            app_project_demo=self._table("app_project_demo"),
        )
        self._write_audit_entity_change(
            entity_name="app_project_demo",
            entity_id=project_demo_id,
            action_type="delete",
            actor_user_principal=actor_user_principal,
            before_json=current,
            after_json=None,
            request_id=None,
        )

    def map_vendor_demo_to_project(
        self,
        *,
        vendor_id: str,
        project_id: str,
        vendor_demo_id: str,
        actor_user_principal: str,
    ) -> str:
        vendor_demos = self.get_vendor_demos(vendor_id)
        matched = vendor_demos[vendor_demos["demo_id"].astype(str) == str(vendor_demo_id)]
        if matched.empty:
            raise ValueError("Vendor demo does not belong to vendor.")
        row = matched.iloc[0].to_dict()
        demo_name = f"Mapped Demo {vendor_demo_id}"
        return self.create_project_demo(
            vendor_id=vendor_id,
            project_id=project_id,
            actor_user_principal=actor_user_principal,
            demo_name=demo_name,
            demo_datetime_start=str(row.get("demo_date") or "") or None,
            demo_type="live",
            outcome=str(row.get("selection_outcome") or "unknown"),
            score=float(row.get("overall_score")) if row.get("overall_score") is not None else None,
            attendees_internal=None,
            attendees_vendor=None,
            notes=str(row.get("notes") or "") or None,
            followups=None,
            linked_offering_id=self._normalize_offering_id(str(row.get("offering_id") or "")),
            linked_vendor_demo_id=vendor_demo_id,
        )

