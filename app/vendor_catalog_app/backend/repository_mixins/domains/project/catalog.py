from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from vendor_catalog_app.core.repository_constants import *

LOGGER = logging.getLogger(__name__)


class RepositoryProjectCatalogMixin:
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

