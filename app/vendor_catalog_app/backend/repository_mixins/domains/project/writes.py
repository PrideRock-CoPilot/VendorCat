from __future__ import annotations

import logging
import uuid
from typing import Any

from vendor_catalog_app.core.repository_constants import *

LOGGER = logging.getLogger(__name__)


class RepositoryProjectWriteMixin:
    def create_project(
        self,
        *,
        vendor_id: str | None = None,
        vendor_ids: list[str] | None = None,
        actor_user_principal: str,
        project_name: str,
        project_type: str | None = None,
        status: str = "draft",
        start_date: str | None = None,
        target_date: str | None = None,
        owner_principal: str | None = None,
        description: str | None = None,
        linked_offering_ids: list[str] | None = None,
    ) -> str:
        clean_name = (project_name or "").strip()
        if not clean_name:
            raise ValueError("Project name is required.")

        normalized_vendor_ids: list[str] = []
        if vendor_id and str(vendor_id).strip():
            normalized_vendor_ids.append(str(vendor_id).strip())
        normalized_vendor_ids.extend([str(x).strip() for x in (vendor_ids or []) if str(x).strip()])
        normalized_vendor_ids = list(dict.fromkeys(normalized_vendor_ids))

        linked_offering_ids = list(
            dict.fromkeys([str(x).strip() for x in (linked_offering_ids or []) if str(x).strip()])
        )
        offerings = self._query_file(
            "ingestion/select_offering_vendor_pairs.sql",
            columns=["offering_id", "vendor_id"],
            core_vendor_offering=self._table("core_vendor_offering"),
        )
        offering_vendor_map = (
            {str(r["offering_id"]): str(r["vendor_id"]) for r in offerings.to_dict("records")}
            if not offerings.empty
            else {}
        )
        for offering_id in linked_offering_ids:
            mapped_vendor = offering_vendor_map.get(str(offering_id))
            if not mapped_vendor:
                raise ValueError(f"Offering {offering_id} was not found.")
            if mapped_vendor not in normalized_vendor_ids:
                normalized_vendor_ids.append(mapped_vendor)

        for mapped_vendor_id in normalized_vendor_ids:
            if self.get_vendor_profile(mapped_vendor_id).empty:
                raise ValueError(f"Vendor {mapped_vendor_id} not found.")

        now = self._now()
        project_id = self._new_id("prj")
        actor_ref = self._actor_ref(actor_user_principal)
        owner_ref = self.resolve_user_id(owner_principal, allow_create=False) if owner_principal else None
        if owner_principal and not owner_ref:
            raise ValueError("Project owner must exist in the app user directory.")
        primary_vendor_id = normalized_vendor_ids[0] if normalized_vendor_ids else None
        row = {
            "project_id": project_id,
            "vendor_id": primary_vendor_id,
            "project_name": clean_name,
            "project_type": (project_type or "").strip() or "other",
            "status": (status or "draft").strip() or "draft",
            "start_date": (start_date or "").strip() or None,
            "target_date": (target_date or "").strip() or None,
            "owner_principal": owner_ref,
            "description": (description or "").strip() or None,
            "active_flag": True,
            "created_at": now.isoformat(),
            "created_by": actor_ref,
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }

        self._execute_file(
            "inserts/create_project.sql",
            params=(
                project_id,
                row["vendor_id"],
                row["project_name"],
                row["project_type"],
                row["status"],
                row["start_date"],
                row["target_date"],
                row["owner_principal"],
                row["description"],
                True,
                now,
                actor_ref,
                now,
                actor_ref,
            ),
            app_project=self._table("app_project"),
        )
        for mapped_vendor_id in normalized_vendor_ids:
            self._execute_file(
                "inserts/create_project_vendor_map.sql",
                params=(
                    self._new_id("pvm"),
                    project_id,
                    mapped_vendor_id,
                    True,
                    now,
                    actor_ref,
                    now,
                    actor_ref,
                ),
                app_project_vendor_map=self._table("app_project_vendor_map"),
            )
        for offering_id in linked_offering_ids:
            mapped_vendor_id = offering_vendor_map.get(offering_id) or row["vendor_id"]
            self._execute_file(
                "inserts/create_project_offering_map.sql",
                params=(
                    self._new_id("pom"),
                    project_id,
                    mapped_vendor_id,
                    offering_id,
                    True,
                    now,
                    actor_ref,
                    now,
                    actor_ref,
                ),
                app_project_offering_map=self._table("app_project_offering_map"),
            )
        self._write_audit_entity_change(
            entity_name="app_project",
            entity_id=project_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return project_id

    def update_project(
        self,
        *,
        vendor_id: str | None,
        project_id: str,
        actor_user_principal: str,
        updates: dict[str, Any],
        vendor_ids: list[str] | None = None,
        linked_offering_ids: list[str] | None = None,
        reason: str,
    ) -> dict[str, str]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        current = self.get_project_by_id(project_id)
        if current is None:
            raise ValueError("Project not found.")
        if vendor_id and not self.project_belongs_to_vendor(vendor_id, project_id):
            raise ValueError("Project not found for vendor.")

        allowed = {
            "project_name",
            "project_type",
            "status",
            "start_date",
            "target_date",
            "owner_principal",
            "description",
        }
        clean_updates = {k: v for k, v in updates.items() if k in allowed}
        if "project_name" in clean_updates and not str(clean_updates["project_name"]).strip():
            raise ValueError("Project name is required.")

        target_vendor_ids = None
        if vendor_ids is not None:
            target_vendor_ids = list(dict.fromkeys([str(x).strip() for x in vendor_ids if str(x).strip()]))

        target_offering_ids = None
        if linked_offering_ids is not None:
            target_offering_ids = list(dict.fromkeys([str(x).strip() for x in linked_offering_ids if str(x).strip()]))
            offerings = self._query_file(
                "ingestion/select_offering_vendor_pairs.sql",
                columns=["offering_id", "vendor_id"],
                core_vendor_offering=self._table("core_vendor_offering"),
            )
            offering_vendor_map = (
                {str(r["offering_id"]): str(r["vendor_id"]) for r in offerings.to_dict("records")}
                if not offerings.empty
                else {}
            )
            for offering_id in target_offering_ids:
                mapped_vendor = offering_vendor_map.get(str(offering_id))
                if not mapped_vendor:
                    raise ValueError(f"Offering {offering_id} was not found.")
                if target_vendor_ids is not None and mapped_vendor not in target_vendor_ids:
                    target_vendor_ids.append(mapped_vendor)
                elif target_vendor_ids is None:
                    # keep backward-compatible validation path for vendor-scoped edits
                    if vendor_id and not self.offering_belongs_to_vendor(vendor_id, offering_id):
                        raise ValueError(f"Offering {offering_id} does not belong to vendor.")

        if target_vendor_ids is not None:
            for mapped_vendor_id in target_vendor_ids:
                if self.get_vendor_profile(mapped_vendor_id).empty:
                    raise ValueError(f"Vendor {mapped_vendor_id} not found.")

        if not clean_updates and target_offering_ids is None and target_vendor_ids is None:
            raise ValueError("No updates were provided.")
        if "owner_principal" in clean_updates:
            owner_candidate = str(clean_updates.get("owner_principal") or "").strip()
            if owner_candidate:
                owner_ref = self.resolve_user_id(owner_candidate, allow_create=False)
                if not owner_ref:
                    raise ValueError("Project owner must exist in the app user directory.")
                clean_updates["owner_principal"] = owner_ref
            else:
                clean_updates["owner_principal"] = None

        before = dict(current)
        after = dict(current)
        after.update(clean_updates)
        if target_vendor_ids is not None:
            after["vendor_id"] = target_vendor_ids[0] if target_vendor_ids else None
            after["vendor_ids"] = target_vendor_ids
        if target_offering_ids is not None:
            after["linked_offering_ids"] = target_offering_ids

        request_id = str(uuid.uuid4())
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        if target_vendor_ids is not None:
            clean_updates["vendor_id"] = target_vendor_ids[0] if target_vendor_ids else None

        if clean_updates:
            set_clause = ", ".join([f"{key} = %s" for key in clean_updates.keys()])
            params = list(clean_updates.values()) + [now, actor_ref, project_id]
            self._execute_file(
                "updates/update_project.sql",
                params=tuple(params),
                app_project=self._table("app_project"),
                set_clause=set_clause,
            )
        if target_vendor_ids is not None:
            self._execute_file(
                "updates/update_project_vendor_map_soft.sql",
                params=(now, actor_ref, project_id),
                app_project_vendor_map=self._table("app_project_vendor_map"),
            )
            for mapped_vendor_id in target_vendor_ids:
                self._execute_file(
                    "inserts/create_project_vendor_map.sql",
                    params=(
                        self._new_id("pvm"),
                        project_id,
                        mapped_vendor_id,
                        True,
                        now,
                        actor_ref,
                        now,
                        actor_ref,
                    ),
                    app_project_vendor_map=self._table("app_project_vendor_map"),
                )
        if target_offering_ids is not None:
            self._execute_file(
                "updates/update_project_offering_map_soft.sql",
                params=(now, actor_ref, project_id),
                app_project_offering_map=self._table("app_project_offering_map"),
            )
            offerings = self._query_file(
                "ingestion/select_offering_vendor_pairs.sql",
                columns=["offering_id", "vendor_id"],
                core_vendor_offering=self._table("core_vendor_offering"),
            )
            offering_vendor_map = (
                {str(r["offering_id"]): str(r["vendor_id"]) for r in offerings.to_dict("records")}
                if not offerings.empty
                else {}
            )
            for offering_id in target_offering_ids:
                mapped_vendor_id = offering_vendor_map.get(offering_id) or str(current.get("vendor_id") or "")
                self._execute_file(
                    "inserts/create_project_offering_map.sql",
                    params=(
                        self._new_id("pom"),
                        project_id,
                        mapped_vendor_id,
                        offering_id,
                        True,
                        now,
                        actor_ref,
                        now,
                        actor_ref,
                    ),
                    app_project_offering_map=self._table("app_project_offering_map"),
                )
        change_event_id = self._write_audit_entity_change(
            entity_name="app_project",
            entity_id=project_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

