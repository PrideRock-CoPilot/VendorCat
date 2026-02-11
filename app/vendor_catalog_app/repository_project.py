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

class RepositoryProjectMixin:
    def _project_vendor_ids(self, project_id: str) -> list[str]:
        if not project_id:
            return []
        map_rows = self._query_file(
            "ingestion/select_project_vendor_ids.sql",
            params=(project_id,),
            columns=["vendor_id"],
            app_project_vendor_map=self._table("app_project_vendor_map"),
        )
        if not map_rows.empty and "vendor_id" in map_rows.columns:
            return sorted(map_rows["vendor_id"].astype(str).dropna().unique().tolist())

        # Backward compatibility: if mapping table has no rows, fall back to primary vendor_id on app_project.
        fallback = self._query_file(
            "ingestion/select_project_primary_vendor_fallback.sql",
            params=(project_id,),
            columns=["vendor_id"],
            app_project=self._table("app_project"),
        )
        if fallback.empty:
            return []
        vendor_id = str(fallback.iloc[0].get("vendor_id") or "").strip()
        return [vendor_id] if vendor_id else []

    def list_project_vendors(self, project_id: str) -> pd.DataFrame:
        vendor_ids = self._project_vendor_ids(project_id)
        if not vendor_ids:
            return pd.DataFrame(columns=["vendor_id", "vendor_display_name", "lifecycle_state", "owner_org_id", "risk_tier"])
        vendors = self.search_vendors(search_text="", lifecycle_state="all")
        if vendors.empty or "vendor_id" not in vendors.columns:
            return pd.DataFrame(columns=["vendor_id", "vendor_display_name", "lifecycle_state", "owner_org_id", "risk_tier"])
        subset = vendors[vendors["vendor_id"].astype(str).isin(vendor_ids)].copy()
        subset["vendor_display_name"] = subset["display_name"].fillna(subset["legal_name"]).fillna(subset["vendor_id"])
        return subset[["vendor_id", "vendor_display_name", "lifecycle_state", "owner_org_id", "risk_tier"]].sort_values("vendor_display_name")

    def project_belongs_to_vendor(self, vendor_id: str, project_id: str) -> bool:
        if not vendor_id or not project_id:
            return False
        return str(vendor_id) in set(self._project_vendor_ids(project_id))

    def list_projects(self, vendor_id: str) -> pd.DataFrame:
        return self._query_file(
            "reporting/list_projects_for_vendor.sql",
            params=(vendor_id, vendor_id),
            columns=[
                "project_id",
                "vendor_id",
                "project_name",
                "project_type",
                "status",
                "start_date",
                "target_date",
                "owner_principal",
                "description",
                "updated_at",
                "demo_count",
                "last_activity_at",
            ],
            app_project=self._table("app_project"),
            app_project_demo=self._table("app_project_demo"),
            app_project_vendor_map=self._table("app_project_vendor_map"),
            app_user_directory=self._table("app_user_directory"),
        )

    def list_all_projects(
        self,
        *,
        search_text: str = "",
        status: str = "all",
        vendor_id: str = "all",
        limit: int = 500,
    ) -> pd.DataFrame:
        limit = max(50, min(limit, 1000))
        params: list[Any] = []
        where_parts = ["coalesce(p.active_flag, true) = true"]
        if vendor_id != "all":
            where_parts.append(
                self._sql(
                    "reporting/filter_all_projects_vendor_clause.sql",
                    app_project_vendor_map=self._table("app_project_vendor_map"),
                )
            )
            params.append(vendor_id)
            params.append(vendor_id)
        if status != "all":
            where_parts.append("lower(p.status) = lower(%s)")
            params.append(status)
        if search_text.strip():
            where_parts.append(
                "("
                "lower(p.project_id) LIKE lower(%s)"
                " OR lower(coalesce(p.project_name, '')) LIKE lower(%s)"
                " OR lower(coalesce(p.project_type, '')) LIKE lower(%s)"
                " OR lower(coalesce(p.owner_principal, '')) LIKE lower(%s)"
                " OR lower(coalesce(ou.login_identifier, '')) LIKE lower(%s)"
                " OR lower(coalesce(ou.display_name, '')) LIKE lower(%s)"
                " OR lower(coalesce(p.description, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.display_name, '')) LIKE lower(%s)"
                ")"
            )
            like = f"%{search_text.strip()}%"
            params.extend([like, like, like, like, like, like, like, like])

        where_clause = " AND ".join(where_parts)
        return self._query_file(
            "reporting/list_all_projects.sql",
            params=tuple(params),
            columns=[
                "project_id",
                "vendor_id",
                "vendor_display_name",
                "project_name",
                "project_type",
                "status",
                "start_date",
                "target_date",
                "owner_principal",
                "description",
                "updated_at",
                "demo_count",
                "last_activity_at",
            ],
            where_clause=where_clause,
            limit=limit,
            app_project=self._table("app_project"),
            core_vendor=self._table("core_vendor"),
            app_project_demo=self._table("app_project_demo"),
            app_user_directory=self._table("app_user_directory"),
        )

    def get_project(self, vendor_id: str, project_id: str) -> dict[str, Any] | None:
        row = self.get_project_by_id(project_id)
        if row is None:
            return None
        if vendor_id and not self.project_belongs_to_vendor(vendor_id, project_id):
            return None
        return row

    def get_project_by_id(self, project_id: str) -> dict[str, Any] | None:
        if not project_id:
            return None
        rows = self._query_file(
            "ingestion/select_project_by_id.sql",
            params=(project_id,),
            columns=[
                "project_id",
                "vendor_id",
                "vendor_display_name",
                "project_name",
                "project_type",
                "status",
                "start_date",
                "target_date",
                "owner_principal",
                "description",
                "updated_at",
                "created_at",
                "created_by",
                "updated_by",
            ],
            app_project=self._table("app_project"),
            core_vendor=self._table("core_vendor"),
            app_user_directory=self._table("app_user_directory"),
        )
        if rows.empty:
            return None
        row = rows.iloc[0].to_dict()
        linked = self.list_project_offerings(None, str(project_id))
        row["linked_offering_ids"] = (
            linked["offering_id"].astype(str).tolist() if not linked.empty and "offering_id" in linked.columns else []
        )
        row["vendor_ids"] = self._project_vendor_ids(str(project_id))
        return row

    def list_project_offerings(self, vendor_id: str | None, project_id: str) -> pd.DataFrame:
        vendor_clause = "AND m.vendor_id = %s" if vendor_id else ""
        params: tuple[Any, ...] = (project_id, vendor_id) if vendor_id else (project_id,)
        self._ensure_local_offering_columns()
        return self._query_file(
            "ingestion/select_project_offerings.sql",
            params=params,
            columns=[
                "offering_id",
                "vendor_id",
                "offering_name",
                "offering_type",
                "lob",
                "service_type",
                "lifecycle_state",
                "criticality_tier",
            ],
            vendor_clause=vendor_clause,
            app_project_offering_map=self._table("app_project_offering_map"),
            core_vendor_offering=self._table("core_vendor_offering"),
        )

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

