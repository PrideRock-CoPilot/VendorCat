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

class RepositoryReportingMixin:
    def dashboard_kpis(self) -> dict[str, int]:
        def _load() -> dict[str, int]:
            frame = self._query_file(
                "reporting/dashboard_kpis.sql",
                columns=["active_vendors", "active_offerings", "demos_logged", "cancelled_contracts"],
                core_vendor=self._table("core_vendor"),
                core_vendor_offering=self._table("core_vendor_offering"),
                core_vendor_demo=self._table("core_vendor_demo"),
                core_contract_event=self._table("core_contract_event"),
            )
            if frame.empty:
                return {
                    "active_vendors": 0,
                    "active_offerings": 0,
                    "demos_logged": 0,
                    "cancelled_contracts": 0,
                }
            row = frame.iloc[0]
            return {
                "active_vendors": int(row.get("active_vendors") or 0),
                "active_offerings": int(row.get("active_offerings") or 0),
                "demos_logged": int(row.get("demos_logged") or 0),
                "cancelled_contracts": int(row.get("cancelled_contracts") or 0),
            }

        return self._cached(("dashboard_kpis",), _load, ttl_seconds=60)

    def available_orgs(self) -> list[str]:
        def _load() -> list[str]:
            df = self._query_file(
                "reporting/available_orgs.sql",
                columns=["org_id"],
                core_vendor=self._table("core_vendor"),
            )
            if df.empty:
                return ["all"]
            return ["all"] + df["org_id"].astype(str).tolist()

        return self._cached(("available_orgs",), _load, ttl_seconds=300)

    def executive_spend_by_category(self, org_id: str = "all", months: int = 12) -> pd.DataFrame:
        months = max(1, min(months, 36))
        org_clause = "AND org_id = %s" if org_id and org_id != "all" else ""
        params: tuple = (org_id,) if org_clause else ()
        return self._cached(
            ("executive_spend_by_category", str(org_id), int(months)),
            lambda: self._query_file(
                "reporting/executive_spend_by_category.sql",
                params=params,
                columns=["category", "total_spend"],
                rpt_spend_fact=self._table("rpt_spend_fact"),
                months_back=(months - 1),
                org_clause=org_clause,
            ),
            ttl_seconds=60,
        )

    def executive_monthly_spend_trend(self, org_id: str = "all", months: int = 12) -> pd.DataFrame:
        months = max(1, min(months, 36))
        org_clause = "AND org_id = %s" if org_id and org_id != "all" else ""
        params: tuple = (org_id,) if org_clause else ()
        return self._cached(
            ("executive_monthly_spend_trend", str(org_id), int(months)),
            lambda: self._query_file(
                "reporting/executive_monthly_spend_trend.sql",
                params=params,
                columns=["month", "total_spend"],
                rpt_spend_fact=self._table("rpt_spend_fact"),
                months_back=(months - 1),
                org_clause=org_clause,
            ),
            ttl_seconds=60,
        )

    def executive_top_vendors_by_spend(
        self, org_id: str = "all", months: int = 12, limit: int = 10
    ) -> pd.DataFrame:
        limit = max(3, min(limit, 25))
        months = max(1, min(months, 36))
        org_clause = "AND sf.org_id = %s" if org_id and org_id != "all" else ""
        params: tuple = (org_id,) if org_clause else ()
        return self._cached(
            ("executive_top_vendors_by_spend", str(org_id), int(months), int(limit)),
            lambda: self._query_file(
                "reporting/executive_top_vendors_by_spend.sql",
                params=params,
                columns=["vendor_id", "vendor_name", "risk_tier", "total_spend"],
                rpt_spend_fact=self._table("rpt_spend_fact"),
                core_vendor=self._table("core_vendor"),
                months_back=(months - 1),
                org_clause=org_clause,
                limit_rows=limit,
            ),
            ttl_seconds=60,
        )

    def executive_risk_distribution(self, org_id: str = "all") -> pd.DataFrame:
        org_clause = "AND owner_org_id = %s" if org_id and org_id != "all" else ""
        params: tuple = (org_id,) if org_clause else ()
        return self._cached(
            ("executive_risk_distribution", str(org_id)),
            lambda: self._query_file(
                "reporting/executive_risk_distribution.sql",
                params=params,
                columns=["risk_tier", "vendor_count"],
                core_vendor=self._table("core_vendor"),
                org_clause=org_clause,
            ),
            ttl_seconds=60,
        )

    def executive_renewal_pipeline(self, org_id: str = "all", horizon_days: int = 180) -> pd.DataFrame:
        horizon_days = max(30, min(horizon_days, 365))
        org_clause = "AND org_id = %s" if org_id and org_id != "all" else ""
        params: tuple = (org_id,) if org_clause else ()
        return self._cached(
            ("executive_renewal_pipeline", str(org_id), int(horizon_days)),
            lambda: self._query_file(
                "reporting/executive_renewal_pipeline.sql",
                params=params,
                columns=[
                    "contract_id",
                    "vendor_id",
                    "vendor_name",
                    "org_id",
                    "category",
                    "renewal_date",
                    "annual_value",
                    "risk_tier",
                    "renewal_status",
                    "days_to_renewal",
                ],
                rpt_contract_renewals=self._table("rpt_contract_renewals"),
                horizon_days=horizon_days,
                org_clause=org_clause,
            ),
            ttl_seconds=60,
        )

    def executive_summary(self, org_id: str = "all", months: int = 12, horizon_days: int = 180) -> dict[str, float]:
        def _load() -> dict[str, float]:
            spend_trend = self.executive_monthly_spend_trend(org_id=org_id, months=months)
            risk = self.executive_risk_distribution(org_id=org_id)
            renewals = self.executive_renewal_pipeline(org_id=org_id, horizon_days=horizon_days)
            demos = self.demo_outcomes()

            total_spend = float(spend_trend["total_spend"].sum()) if "total_spend" in spend_trend else 0.0
            high_risk_count = 0
            if not risk.empty and {"risk_tier", "vendor_count"}.issubset(risk.columns):
                high_risk_count = int(
                    risk[risk["risk_tier"].astype(str).str.lower().isin(["high", "critical"])]["vendor_count"].sum()
                )

            renewal_value = (
                float(renewals["annual_value"].sum()) if not renewals.empty and "annual_value" in renewals else 0.0
            )
            not_selected_rate = 0.0
            if not demos.empty and "selection_outcome" in demos.columns:
                total_demos = len(demos)
                not_selected = int((demos["selection_outcome"] == "not_selected").sum())
                not_selected_rate = (not_selected / total_demos) if total_demos else 0.0

            return {
                "total_spend_window": total_spend,
                "high_risk_vendors": float(high_risk_count),
                "renewals_due_count": float(len(renewals)),
                "renewals_due_value": renewal_value,
                "not_selected_demo_rate": not_selected_rate,
            }

        return self._cached(
            ("executive_summary", str(org_id), int(months), int(horizon_days)),
            _load,
            ttl_seconds=60,
        )

    def report_vendor_inventory(
        self,
        *,
        search_text: str = "",
        lifecycle_state: str = "all",
        owner_principal: str = "",
        limit: int = 500,
    ) -> pd.DataFrame:
        columns = [
            "vendor_id",
            "display_name",
            "legal_name",
            "lifecycle_state",
            "owner_org_id",
            "risk_tier",
            "offering_count",
            "active_offering_count",
            "contract_count",
            "active_contract_count",
            "project_count",
            "total_contract_value",
            "owner_principals",
            "owner_roles",
            "updated_at",
        ]
        limit = max(50, min(limit, 5000))
        vendors = self.search_vendors(search_text=search_text, lifecycle_state=lifecycle_state).copy()
        if vendors.empty:
            return pd.DataFrame(columns=columns)

        offerings = self._query_file(
            "reporting/report_vendor_inventory_offerings.sql",
            columns=["vendor_id", "lifecycle_state"],
            core_vendor_offering=self._table("core_vendor_offering"),
        )
        contracts = self._query_file(
            "reporting/report_vendor_inventory_contracts.sql",
            columns=["vendor_id", "contract_status", "annual_value"],
            core_contract=self._table("core_contract"),
        )
        project_map = self._query_file(
            "reporting/report_vendor_inventory_project_map.sql",
            columns=["project_id", "vendor_id"],
            app_project_vendor_map=self._table("app_project_vendor_map"),
            app_project=self._table("app_project"),
        )
        owners = self._query_file(
            "reporting/report_vendor_inventory_owners.sql",
            columns=["vendor_id", "owner_user_principal", "owner_role", "active_flag"],
            core_vendor_business_owner=self._table("core_vendor_business_owner"),
        )

        offerings["vendor_id"] = offerings["vendor_id"].astype(str)
        contracts["vendor_id"] = contracts["vendor_id"].astype(str)
        project_map["vendor_id"] = project_map["vendor_id"].astype(str)
        project_map["project_id"] = project_map["project_id"].astype(str)
        owners["vendor_id"] = owners["vendor_id"].astype(str)
        if "active_flag" in owners.columns:
            owners = owners[owners["active_flag"].fillna(True) == True].copy()

        offering_counts = (
            offerings.groupby("vendor_id", as_index=False).size().rename(columns={"size": "offering_count"})
            if not offerings.empty
            else pd.DataFrame(columns=["vendor_id", "offering_count"])
        )
        active_offering_counts = (
            offerings[offerings["lifecycle_state"].astype(str).str.lower() == "active"]
            .groupby("vendor_id", as_index=False)
            .size()
            .rename(columns={"size": "active_offering_count"})
            if not offerings.empty
            else pd.DataFrame(columns=["vendor_id", "active_offering_count"])
        )
        contract_counts = (
            contracts.groupby("vendor_id", as_index=False).size().rename(columns={"size": "contract_count"})
            if not contracts.empty
            else pd.DataFrame(columns=["vendor_id", "contract_count"])
        )
        active_contract_counts = (
            contracts[contracts["contract_status"].astype(str).str.lower() == "active"]
            .groupby("vendor_id", as_index=False)
            .size()
            .rename(columns={"size": "active_contract_count"})
            if not contracts.empty
            else pd.DataFrame(columns=["vendor_id", "active_contract_count"])
        )
        contract_value = (
            contracts.assign(annual_value=pd.to_numeric(contracts["annual_value"], errors="coerce").fillna(0.0))
            .groupby("vendor_id", as_index=False)["annual_value"]
            .sum()
            .rename(columns={"annual_value": "total_contract_value"})
            if not contracts.empty
            else pd.DataFrame(columns=["vendor_id", "total_contract_value"])
        )
        project_counts = (
            project_map.drop_duplicates(subset=["project_id", "vendor_id"])
            .groupby("vendor_id", as_index=False)
            .size()
            .rename(columns={"size": "project_count"})
            if not project_map.empty
            else pd.DataFrame(columns=["vendor_id", "project_count"])
        )
        owner_principals = (
            owners.groupby("vendor_id", as_index=False)["owner_user_principal"]
            .agg(lambda s: ", ".join(sorted({str(x).strip() for x in s if str(x).strip()})))
            .rename(columns={"owner_user_principal": "owner_principals"})
            if not owners.empty
            else pd.DataFrame(columns=["vendor_id", "owner_principals"])
        )
        owner_roles = (
            owners.groupby("vendor_id", as_index=False)["owner_role"]
            .agg(lambda s: ", ".join(sorted({str(x).strip() for x in s if str(x).strip()})))
            .rename(columns={"owner_role": "owner_roles"})
            if not owners.empty
            else pd.DataFrame(columns=["vendor_id", "owner_roles"])
        )

        out = vendors.merge(offering_counts, on="vendor_id", how="left")
        out = out.merge(active_offering_counts, on="vendor_id", how="left")
        out = out.merge(contract_counts, on="vendor_id", how="left")
        out = out.merge(active_contract_counts, on="vendor_id", how="left")
        out = out.merge(project_counts, on="vendor_id", how="left")
        out = out.merge(contract_value, on="vendor_id", how="left")
        out = out.merge(owner_principals, on="vendor_id", how="left")
        out = out.merge(owner_roles, on="vendor_id", how="left")

        if owner_principal.strip():
            out = self._filter_contains_any(out, owner_principal, ["owner_principals"])

        for count_col in [
            "offering_count",
            "active_offering_count",
            "contract_count",
            "active_contract_count",
            "project_count",
        ]:
            out[count_col] = pd.to_numeric(out.get(count_col), errors="coerce").fillna(0).astype(int)
        out["total_contract_value"] = pd.to_numeric(out.get("total_contract_value"), errors="coerce").fillna(0.0)
        out["owner_principals"] = out.get("owner_principals", "").fillna("")
        out["owner_roles"] = out.get("owner_roles", "").fillna("")
        return out[columns].sort_values(["display_name", "vendor_id"]).head(limit)

    def report_project_portfolio(
        self,
        *,
        search_text: str = "",
        status: str = "all",
        vendor_id: str = "all",
        owner_principal: str = "",
        limit: int = 500,
    ) -> pd.DataFrame:
        columns = [
            "project_id",
            "project_name",
            "status",
            "project_type",
            "vendor_display_name",
            "vendor_id",
            "vendor_count",
            "linked_offering_count",
            "demo_count",
            "note_count",
            "doc_count",
            "owner_principal",
            "target_date",
            "last_activity_at",
            "updated_at",
        ]
        limit = max(50, min(limit, 5000))
        projects = self.list_all_projects(search_text=search_text, status=status, vendor_id=vendor_id, limit=limit * 2).copy()
        if projects.empty:
            return pd.DataFrame(columns=columns)

        if owner_principal.strip():
            projects = self._filter_contains_any(projects, owner_principal, ["owner_principal"])

        project_vendor_map = self._query_file(
            "reporting/report_project_portfolio_vendor_map.sql",
            columns=["project_id", "vendor_id"],
            app_project_vendor_map=self._table("app_project_vendor_map"),
            app_project=self._table("app_project"),
        )
        project_offering_map = self._query_file(
            "reporting/report_project_portfolio_offering_map.sql",
            columns=["project_id", "offering_id"],
            app_project_offering_map=self._table("app_project_offering_map"),
        )
        project_notes = self._query_file(
            "reporting/report_project_portfolio_notes.sql",
            columns=["project_id", "project_note_id"],
            app_project_note=self._table("app_project_note"),
        )
        project_docs = self._query_file(
            "reporting/report_project_portfolio_docs.sql",
            columns=["entity_id", "doc_id"],
            app_document_link=self._table("app_document_link"),
        )

        project_vendor_counts = (
            project_vendor_map.drop_duplicates(subset=["project_id", "vendor_id"])
            .groupby("project_id", as_index=False)
            .size()
            .rename(columns={"size": "vendor_count"})
            if not project_vendor_map.empty
            else pd.DataFrame(columns=["project_id", "vendor_count"])
        )
        offering_counts = (
            project_offering_map.drop_duplicates(subset=["project_id", "offering_id"])
            .groupby("project_id", as_index=False)
            .size()
            .rename(columns={"size": "linked_offering_count"})
            if not project_offering_map.empty
            else pd.DataFrame(columns=["project_id", "linked_offering_count"])
        )
        note_counts = (
            project_notes.groupby("project_id", as_index=False)
            .size()
            .rename(columns={"size": "note_count"})
            if not project_notes.empty
            else pd.DataFrame(columns=["project_id", "note_count"])
        )
        doc_counts = (
            project_docs.groupby("entity_id", as_index=False)
            .size()
            .rename(columns={"entity_id": "project_id", "size": "doc_count"})
            if not project_docs.empty
            else pd.DataFrame(columns=["project_id", "doc_count"])
        )

        out = projects.merge(project_vendor_counts, on="project_id", how="left")
        out = out.merge(offering_counts, on="project_id", how="left")
        out = out.merge(note_counts, on="project_id", how="left")
        out = out.merge(doc_counts, on="project_id", how="left")
        out["vendor_display_name"] = out.get("vendor_display_name", "").fillna("Unassigned")
        for count_col in ["vendor_count", "linked_offering_count", "demo_count", "note_count", "doc_count"]:
            out[count_col] = pd.to_numeric(out.get(count_col), errors="coerce").fillna(0).astype(int)
        return out[columns].sort_values(["status", "project_name"]).head(limit)

    def report_contract_renewals(
        self,
        *,
        search_text: str = "",
        vendor_id: str = "all",
        org_id: str = "all",
        horizon_days: int = 180,
        limit: int = 500,
    ) -> pd.DataFrame:
        columns = [
            "contract_id",
            "vendor_id",
            "vendor_name",
            "org_id",
            "category",
            "renewal_date",
            "annual_value",
            "risk_tier",
            "renewal_status",
            "days_to_renewal",
        ]
        limit = max(50, min(limit, 5000))
        horizon_days = max(30, min(horizon_days, 730))
        out = self.executive_renewal_pipeline(org_id=org_id, horizon_days=horizon_days).copy()
        if out.empty:
            return pd.DataFrame(columns=columns)
        if vendor_id != "all":
            out = out[out["vendor_id"].astype(str) == str(vendor_id)].copy()
        if search_text.strip():
            out = self._filter_contains_any(
                out,
                search_text,
                ["contract_id", "vendor_id", "vendor_name", "category", "renewal_status", "risk_tier"],
            )
        out["annual_value"] = pd.to_numeric(out.get("annual_value"), errors="coerce").fillna(0.0)
        return out[columns].sort_values(["renewal_date", "vendor_name", "contract_id"]).head(limit)

    def report_demo_outcomes(
        self,
        *,
        search_text: str = "",
        vendor_id: str = "all",
        outcome: str = "all",
        limit: int = 500,
    ) -> pd.DataFrame:
        columns = [
            "demo_id",
            "demo_date",
            "vendor_id",
            "vendor_display_name",
            "offering_id",
            "overall_score",
            "selection_outcome",
            "non_selection_reason_code",
            "notes",
        ]
        limit = max(50, min(limit, 5000))
        out = self.demo_outcomes().copy()
        if out.empty:
            return pd.DataFrame(columns=columns)
        if vendor_id != "all":
            out = out[out["vendor_id"].astype(str) == str(vendor_id)].copy()
        if outcome != "all":
            out = out[out["selection_outcome"].astype(str).str.lower() == str(outcome).lower()].copy()
        if search_text.strip():
            out = self._filter_contains_any(
                out,
                search_text,
                ["demo_id", "vendor_id", "offering_id", "selection_outcome", "non_selection_reason_code", "notes"],
            )

        vendors = self.search_vendors(search_text="", lifecycle_state="all")[["vendor_id", "display_name", "legal_name"]].copy()
        vendors["vendor_display_name"] = vendors["display_name"].fillna(vendors["legal_name"]).fillna(vendors["vendor_id"])
        out = out.merge(vendors[["vendor_id", "vendor_display_name"]], on="vendor_id", how="left")
        out["vendor_display_name"] = out["vendor_display_name"].fillna(out["vendor_id"])
        out["overall_score"] = pd.to_numeric(out.get("overall_score"), errors="coerce")
        return out[columns].sort_values("demo_date", ascending=False).head(limit)

    def report_owner_coverage(
        self,
        *,
        search_text: str = "",
        owner_principal: str = "",
        vendor_id: str = "all",
        limit: int = 1000,
    ) -> pd.DataFrame:
        columns = [
            "owner_principal",
            "owner_role",
            "entity_type",
            "entity_id",
            "entity_name",
            "vendor_id",
            "vendor_display_name",
        ]
        limit = max(50, min(limit, 5000))
        out = self._query_file(
            "reporting/report_owner_coverage.sql",
            columns=columns,
            core_vendor_business_owner=self._table("core_vendor_business_owner"),
            core_vendor=self._table("core_vendor"),
            core_offering_business_owner=self._table("core_offering_business_owner"),
            core_vendor_offering=self._table("core_vendor_offering"),
            app_project=self._table("app_project"),
        )

        if out.empty:
            return pd.DataFrame(columns=columns)
        if vendor_id != "all":
            out = out[out["vendor_id"].astype(str) == str(vendor_id)].copy()
        if owner_principal.strip():
            out = self._filter_contains_any(out, owner_principal, ["owner_principal"])
        if search_text.strip():
            out = self._filter_contains_any(
                out,
                search_text,
                ["owner_principal", "owner_role", "entity_type", "entity_id", "entity_name", "vendor_id", "vendor_display_name"],
            )
        return out[columns].sort_values(["owner_principal", "entity_type", "entity_name"]).head(limit)

    def list_vendor_offerings_for_vendors(self, vendor_ids: list[str]) -> pd.DataFrame:
        columns = [
            "offering_id",
            "vendor_id",
            "offering_name",
            "offering_type",
            "lob",
            "service_type",
            "lifecycle_state",
        ]
        cleaned_ids = [str(v).strip() for v in vendor_ids if str(v).strip()]
        if not cleaned_ids:
            return pd.DataFrame(columns=columns)

        self._ensure_local_offering_columns()
        placeholders = ", ".join(["%s"] * len(cleaned_ids))
        return self._query_file(
            "ingestion/select_vendor_offerings_for_vendor_ids.sql",
            params=tuple(cleaned_ids),
            columns=columns,
            vendor_ids_placeholders=placeholders,
            core_vendor_offering=self._table("core_vendor_offering"),
        )

    def get_vendors_by_ids(self, vendor_ids: list[str]) -> pd.DataFrame:
        columns = ["vendor_id", "display_name", "legal_name", "lifecycle_state", "owner_org_id", "risk_tier"]
        cleaned_ids = [str(v).strip() for v in vendor_ids if str(v).strip()]
        if not cleaned_ids:
            return pd.DataFrame(columns=columns)
        placeholders = ", ".join(["%s"] * len(cleaned_ids))
        return self._query_file(
            "ingestion/select_vendors_by_ids.sql",
            params=tuple(cleaned_ids),
            columns=columns,
            vendor_ids_placeholders=placeholders,
            core_vendor=self._table("core_vendor"),
        )

    def get_offerings_by_ids(self, offering_ids: list[str]) -> pd.DataFrame:
        columns = [
            "offering_id",
            "vendor_id",
            "offering_name",
            "offering_type",
            "lob",
            "service_type",
            "lifecycle_state",
            "criticality_tier",
            "vendor_display_name",
        ]
        cleaned_ids = [str(v).strip() for v in offering_ids if str(v).strip()]
        if not cleaned_ids:
            return pd.DataFrame(columns=columns)
        self._ensure_local_offering_columns()
        placeholders = ", ".join(["%s"] * len(cleaned_ids))
        return self._query_file(
            "ingestion/select_offerings_by_ids.sql",
            params=tuple(cleaned_ids),
            columns=columns,
            offering_ids_placeholders=placeholders,
            core_vendor_offering=self._table("core_vendor_offering"),
            core_vendor=self._table("core_vendor"),
        )

    def search_vendors_typeahead(self, *, q: str = "", limit: int = 20) -> pd.DataFrame:
        limit = max(1, min(int(limit or 20), 100))
        columns = ["vendor_id", "label", "display_name", "legal_name", "lifecycle_state"]
        params: list[Any] = []
        where = "1 = 1"
        if q.strip():
            like = f"%{q.strip()}%"
            where = (
                "("
                "lower(v.vendor_id) LIKE lower(%s)"
                " OR lower(coalesce(v.display_name, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.legal_name, '')) LIKE lower(%s)"
                ")"
            )
            params.extend([like, like, like])
        return self._query_file(
            "reporting/search_vendors_typeahead.sql",
            params=tuple(params) if params else None,
            columns=columns,
            where_clause=where,
            limit=limit,
            core_vendor=self._table("core_vendor"),
        )

    def search_offerings_typeahead(self, *, vendor_id: str | None = None, q: str = "", limit: int = 20) -> pd.DataFrame:
        limit = max(1, min(int(limit or 20), 100))
        columns = [
            "offering_id",
            "vendor_id",
            "offering_name",
            "offering_type",
            "lob",
            "service_type",
            "lifecycle_state",
            "vendor_display_name",
            "label",
        ]
        filter_vendor = str(vendor_id or "").strip()
        where_parts = []
        params: list[Any] = []
        if filter_vendor:
            where_parts.append("o.vendor_id = %s")
            params.append(filter_vendor)
        if q.strip():
            like = f"%{q.strip()}%"
            where_parts.append(
                "("
                "lower(o.offering_id) LIKE lower(%s)"
                " OR lower(coalesce(o.offering_name, '')) LIKE lower(%s)"
                " OR lower(coalesce(o.offering_type, '')) LIKE lower(%s)"
                " OR lower(coalesce(o.lob, '')) LIKE lower(%s)"
                " OR lower(coalesce(o.service_type, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.display_name, v.legal_name, o.vendor_id)) LIKE lower(%s)"
                ")"
            )
            params.extend([like, like, like, like, like, like])
        where = " AND ".join(where_parts) if where_parts else "1 = 1"
        self._ensure_local_offering_columns()
        return self._query_file(
            "reporting/search_offerings_typeahead.sql",
            params=tuple(params) if params else None,
            columns=columns,
            where_clause=where,
            limit=limit,
            core_vendor_offering=self._table("core_vendor_offering"),
            core_vendor=self._table("core_vendor"),
        )

    def search_projects_typeahead(self, *, q: str = "", limit: int = 20) -> pd.DataFrame:
        limit = max(1, min(int(limit or 20), 100))
        columns = ["project_id", "project_name", "status", "vendor_id", "vendor_display_name", "label"]
        params: list[Any] = []
        where_parts = ["coalesce(p.active_flag, true) = true"]
        if q.strip():
            like = f"%{q.strip()}%"
            where_parts.append(
                "("
                "lower(p.project_id) LIKE lower(%s)"
                " OR lower(coalesce(p.project_name, '')) LIKE lower(%s)"
                " OR lower(coalesce(p.status, '')) LIKE lower(%s)"
                " OR lower(coalesce(p.owner_principal, '')) LIKE lower(%s)"
                " OR lower(coalesce(p.description, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.display_name, v.legal_name, p.vendor_id, '')) LIKE lower(%s)"
                ")"
            )
            params.extend([like, like, like, like, like, like])
        where = " AND ".join(where_parts)
        return self._query_file(
            "reporting/search_projects_typeahead.sql",
            params=tuple(params) if params else None,
            columns=columns,
            where_clause=where,
            limit=limit,
            app_project=self._table("app_project"),
            core_vendor=self._table("core_vendor"),
        )

    def list_vendors_page(
        self,
        *,
        search_text: str = "",
        lifecycle_state: str = "all",
        owner_org_id: str = "all",
        risk_tier: str = "all",
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "vendor_name",
        sort_dir: str = "asc",
    ) -> tuple[pd.DataFrame, int]:
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 25), 200))
        sort_dir = "desc" if str(sort_dir).strip().lower() == "desc" else "asc"
        sort_col = self._vendor_sort_column(sort_by)
        sort_expr = self._vendor_sort_expr(sort_by)
        offset = (page - 1) * page_size
        columns = [
            "vendor_id",
            "legal_name",
            "display_name",
            "lifecycle_state",
            "owner_org_id",
            "risk_tier",
            "source_system",
            "updated_at",
        ]

        self._ensure_local_offering_columns()
        where_parts = ["1 = 1"]
        params: list[Any] = []
        if lifecycle_state != "all":
            where_parts.append("v.lifecycle_state = %s")
            params.append(lifecycle_state)
        if owner_org_id != "all":
            where_parts.append("v.owner_org_id = %s")
            params.append(owner_org_id)
        if risk_tier != "all":
            where_parts.append("v.risk_tier = %s")
            params.append(risk_tier)
        if search_text.strip():
            like = f"%{search_text.strip()}%"
            where_parts.append(
                self._sql(
                    "reporting/filter_vendors_page_search_clause.sql",
                    core_vendor_offering=self._table("core_vendor_offering"),
                    core_contract=self._table("core_contract"),
                    core_vendor_business_owner=self._table("core_vendor_business_owner"),
                    core_offering_business_owner=self._table("core_offering_business_owner"),
                    core_vendor_contact=self._table("core_vendor_contact"),
                    core_offering_contact=self._table("core_offering_contact"),
                    core_vendor_demo=self._table("core_vendor_demo"),
                    app_project=self._table("app_project"),
                )
            )
            params.extend([like] * 39)

        where_clause = " AND ".join(where_parts)

        try:
            total_df = self._query_file(
                "reporting/list_vendors_page_count.sql",
                params=tuple(params),
                columns=["total_rows"],
                where_clause=where_clause,
                core_vendor=self._table("core_vendor"),
            )
            total = int(total_df.iloc[0]["total_rows"]) if not total_df.empty else 0
            rows = self._query_file(
                "reporting/list_vendors_page_data.sql",
                params=tuple(params + [page_size, offset]),
                where_clause=where_clause,
                sort_expr=sort_expr,
                sort_dir=sort_dir,
                core_vendor=self._table("core_vendor"),
            )
            if rows.empty:
                return pd.DataFrame(columns=columns), total
            for col in columns:
                if col not in rows.columns:
                    rows[col] = None
            return rows[columns], total
        except (DataQueryError, DataConnectionError):
            LOGGER.warning("Primary vendor paging query failed; using fallback search.", exc_info=True)
            fallback = self.search_vendors(search_text=search_text, lifecycle_state=lifecycle_state).copy()
            if owner_org_id != "all" and "owner_org_id" in fallback.columns:
                fallback = fallback[fallback["owner_org_id"].astype(str) == str(owner_org_id)].copy()
            if risk_tier != "all" and "risk_tier" in fallback.columns:
                fallback = fallback[fallback["risk_tier"].astype(str) == str(risk_tier)].copy()
            if sort_col in fallback.columns:
                fallback = fallback.sort_values(sort_col, ascending=(sort_dir == "asc"), kind="mergesort", na_position="last")
            total = int(len(fallback))
            out = fallback.iloc[offset : offset + page_size].copy()
            for col in columns:
                if col not in out.columns:
                    out[col] = None
            return out[columns], total

    def search_vendors(self, search_text: str = "", lifecycle_state: str = "all") -> pd.DataFrame:
        self._ensure_local_offering_columns()
        state_clause = ""
        params: list[str] = []
        if lifecycle_state != "all":
            state_clause = "AND v.lifecycle_state = %s"
            params.append(lifecycle_state)

        if not search_text.strip():
            return self._query_file(
                "reporting/search_vendors_base.sql",
                params=tuple(params),
                state_clause=state_clause,
                core_vendor=self._table("core_vendor"),
            )

        like = f"%{search_text.strip()}%"
        broad_params = [like] * 39 + params

        try:
            return self._query_file(
                "reporting/search_vendors_broad.sql",
                params=tuple(broad_params),
                state_clause=state_clause,
                core_vendor=self._table("core_vendor"),
                core_vendor_offering=self._table("core_vendor_offering"),
                core_contract=self._table("core_contract"),
                core_vendor_business_owner=self._table("core_vendor_business_owner"),
                core_offering_business_owner=self._table("core_offering_business_owner"),
                core_vendor_contact=self._table("core_vendor_contact"),
                core_offering_contact=self._table("core_offering_contact"),
                core_vendor_demo=self._table("core_vendor_demo"),
                app_project=self._table("app_project"),
            )
        except (DataQueryError, DataConnectionError):
            LOGGER.warning("Broad vendor search query failed; using fallback query.", exc_info=True)
            return self._query_file(
                "reporting/search_vendors_fallback.sql",
                params=tuple([like, like, like] + params),
                state_clause=state_clause,
                core_vendor=self._table("core_vendor"),
            )

    def get_vendor_profile(self, vendor_id: str) -> pd.DataFrame:
        return self._query_file(
            "ingestion/select_vendor_profile_by_id.sql",
            params=(vendor_id,),
            core_vendor=self._table("core_vendor"),
        )

    def get_vendor_offerings(self, vendor_id: str) -> pd.DataFrame:
        self._ensure_local_offering_columns()
        return self._query_file(
            "ingestion/select_vendor_offerings.sql",
            params=(vendor_id,),
            core_vendor_offering=self._table("core_vendor_offering"),
        )

    def get_vendor_contacts(self, vendor_id: str) -> pd.DataFrame:
        return self._query_file(
            "ingestion/select_vendor_contacts.sql",
            params=(vendor_id,),
            core_vendor_contact=self._table("core_vendor_contact"),
        )

    def get_vendor_identifiers(self, vendor_id: str) -> pd.DataFrame:
        return self._query_file(
            "ingestion/select_vendor_identifiers.sql",
            params=(vendor_id,),
            columns=[
                "vendor_identifier_id",
                "vendor_id",
                "identifier_type",
                "identifier_value",
                "is_primary",
                "country_code",
            ],
            core_vendor_identifier=self._table("core_vendor_identifier"),
        )

    def get_vendor_business_owners(self, vendor_id: str) -> pd.DataFrame:
        return self._query_file(
            "ingestion/select_vendor_business_owners.sql",
            params=(vendor_id,),
            columns=["vendor_owner_id", "vendor_id", "owner_user_principal", "owner_role", "active_flag"],
            core_vendor_business_owner=self._table("core_vendor_business_owner"),
            app_user_directory=self._table("app_user_directory"),
        )

    def get_vendor_org_assignments(self, vendor_id: str) -> pd.DataFrame:
        return self._query_file(
            "ingestion/select_vendor_org_assignments.sql",
            params=(vendor_id,),
            columns=["vendor_org_assignment_id", "vendor_id", "org_id", "assignment_type", "active_flag"],
            core_vendor_org_assignment=self._table("core_vendor_org_assignment"),
        )

    def get_vendor_offering_business_owners(self, vendor_id: str) -> pd.DataFrame:
        return self._query_file(
            "ingestion/select_vendor_offering_business_owners.sql",
            params=(vendor_id,),
            columns=[
                "offering_id",
                "offering_name",
                "offering_owner_id",
                "owner_user_principal",
                "owner_role",
                "active_flag",
            ],
            core_offering_business_owner=self._table("core_offering_business_owner"),
            core_vendor_offering=self._table("core_vendor_offering"),
            app_user_directory=self._table("app_user_directory"),
        )

    def get_vendor_offering_contacts(self, vendor_id: str) -> pd.DataFrame:
        return self._query_file(
            "ingestion/select_vendor_offering_contacts.sql",
            params=(vendor_id,),
            columns=[
                "offering_id",
                "offering_name",
                "offering_contact_id",
                "contact_type",
                "full_name",
                "email",
                "phone",
                "active_flag",
            ],
            core_offering_contact=self._table("core_offering_contact"),
            core_vendor_offering=self._table("core_vendor_offering"),
        )

    def get_vendor_contracts(self, vendor_id: str) -> pd.DataFrame:
        return self._query_file(
            "ingestion/select_vendor_contracts.sql",
            params=(vendor_id,),
            columns=[
                "contract_id",
                "vendor_id",
                "offering_id",
                "contract_number",
                "contract_status",
                "start_date",
                "end_date",
                "cancelled_flag",
            ],
            core_contract=self._table("core_contract"),
        )

    def get_vendor_contract_events(self, vendor_id: str) -> pd.DataFrame:
        out = self._query_file(
            "ingestion/select_vendor_contract_events.sql",
            params=(vendor_id,),
            columns=[
                "contract_event_id",
                "contract_id",
                "event_type",
                "event_ts",
                "reason_code",
                "notes",
                "actor_user_principal",
            ],
            core_contract_event=self._table("core_contract_event"),
            core_contract=self._table("core_contract"),
        )
        return self._decorate_user_columns(out, ["actor_user_principal"])

    def get_vendor_demos(self, vendor_id: str) -> pd.DataFrame:
        return self._query_file(
            "ingestion/select_vendor_demos.sql",
            params=(vendor_id,),
            columns=[
                "demo_id",
                "vendor_id",
                "offering_id",
                "demo_date",
                "overall_score",
                "selection_outcome",
                "non_selection_reason_code",
                "notes",
            ],
            core_vendor_demo=self._table("core_vendor_demo"),
        )

    def get_vendor_demo_scores(self, vendor_id: str) -> pd.DataFrame:
        return self._query_file(
            "ingestion/select_vendor_demo_scores.sql",
            params=(vendor_id,),
            columns=["demo_score_id", "demo_id", "score_category", "score_value", "weight", "comments"],
            core_vendor_demo_score=self._table("core_vendor_demo_score"),
            core_vendor_demo=self._table("core_vendor_demo"),
        )

    def get_vendor_demo_notes(self, vendor_id: str) -> pd.DataFrame:
        return self._query_file(
            "ingestion/select_vendor_demo_notes.sql",
            params=(vendor_id,),
            columns=["demo_note_id", "demo_id", "note_type", "note_text", "created_at", "created_by"],
            core_vendor_demo_note=self._table("core_vendor_demo_note"),
            core_vendor_demo=self._table("core_vendor_demo"),
        )

    def get_vendor_change_requests(self, vendor_id: str) -> pd.DataFrame:
        out = self._query_file(
            "ingestion/select_vendor_change_requests.sql",
            params=(vendor_id,),
            columns=[
                "change_request_id",
                "vendor_id",
                "requestor_user_principal",
                "change_type",
                "requested_payload_json",
                "status",
                "submitted_at",
                "updated_at",
            ],
            app_vendor_change_request=self._table("app_vendor_change_request"),
        )
        if "requestor_user_principal" in out.columns and "requestor_user_principal_raw" not in out.columns:
            out["requestor_user_principal_raw"] = out["requestor_user_principal"]
        return self._decorate_user_columns(out, ["requestor_user_principal"])

    def list_change_requests(self, *, status: str = "all") -> pd.DataFrame:
        normalized_status = str(status or "all").strip().lower()
        where_clause = ""
        params: tuple[Any, ...] = ()
        if normalized_status != "all":
            where_clause = "WHERE lower(status) = lower(%s)"
            params = (normalized_status,)
        out = self._query_file(
            "ingestion/select_all_vendor_change_requests.sql",
            params=params,
            columns=[
                "change_request_id",
                "vendor_id",
                "requestor_user_principal",
                "change_type",
                "requested_payload_json",
                "status",
                "submitted_at",
                "updated_at",
            ],
            where_clause=where_clause,
            app_vendor_change_request=self._table("app_vendor_change_request"),
        )
        if "requestor_user_principal" in out.columns and "requestor_user_principal_raw" not in out.columns:
            out["requestor_user_principal_raw"] = out["requestor_user_principal"]
        return self._decorate_user_columns(out, ["requestor_user_principal"])

    def get_change_request_by_id(self, change_request_id: str) -> dict[str, Any] | None:
        request_id = str(change_request_id or "").strip()
        if not request_id:
            return None
        df = self._query_file(
            "ingestion/select_vendor_change_request_by_id.sql",
            params=(request_id,),
            columns=[
                "change_request_id",
                "vendor_id",
                "requestor_user_principal",
                "change_type",
                "requested_payload_json",
                "status",
                "submitted_at",
                "updated_at",
            ],
            app_vendor_change_request=self._table("app_vendor_change_request"),
        )
        if df.empty:
            return None
        if "requestor_user_principal" in df.columns and "requestor_user_principal_raw" not in df.columns:
            df["requestor_user_principal_raw"] = df["requestor_user_principal"]
        out = self._decorate_user_columns(df, ["requestor_user_principal"])
        return out.iloc[0].to_dict()

    def update_change_request_status(
        self,
        *,
        change_request_id: str,
        new_status: str,
        actor_user_principal: str,
        notes: str | None = None,
    ) -> dict[str, Any]:
        request_id = str(change_request_id or "").strip()
        target_status = str(new_status or "").strip().lower()
        if not request_id:
            raise ValueError("Change request ID is required.")
        allowed_statuses = {str(item).strip().lower() for item in self.list_workflow_status_options() if str(item).strip()}
        if target_status not in allowed_statuses:
            raise ValueError(f"Unsupported change request status: {target_status}.")

        current = self.get_change_request_by_id(request_id)
        if not current:
            raise ValueError("Change request not found.")

        old_status = str(current.get("status") or "").strip().lower() or "submitted"
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        self._execute_file(
            "updates/update_vendor_change_request_status.sql",
            params=(target_status, now, request_id),
            app_vendor_change_request=self._table("app_vendor_change_request"),
        )

        try:
            self._execute_file(
                "inserts/create_workflow_event.sql",
                params=(
                    str(uuid.uuid4()),
                    "vendor_change_request",
                    request_id,
                    old_status,
                    target_status,
                    actor_ref,
                    now,
                    (notes or "").strip() or f"status changed to {target_status}",
                ),
                audit_workflow_event=self._table("audit_workflow_event"),
            )
        except (DataExecutionError, DataConnectionError):
            LOGGER.debug("Failed to write create_workflow_event for '%s'.", request_id, exc_info=True)

        updated_row = self.get_change_request_by_id(request_id)
        return updated_row or {"change_request_id": request_id, "status": target_status}

    def get_vendor_audit_events(self, vendor_id: str) -> pd.DataFrame:
        out = self._query_file(
            "ingestion/select_vendor_audit_events.sql",
            params=(vendor_id, vendor_id),
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
            app_vendor_change_request=self._table("app_vendor_change_request"),
        )
        out = self._with_audit_change_summaries(out)
        return self._decorate_user_columns(out, ["actor_user_principal"])

    def get_vendor_source_lineage(self, vendor_id: str) -> pd.DataFrame:
        profile = self.get_vendor_profile(vendor_id)
        if profile.empty:
            return pd.DataFrame(
                columns=["source_system", "source_record_id", "source_batch_id", "source_extract_ts", "entity_hint"]
            )

        source_system = profile.iloc[0].get("source_system")
        source_record_id = profile.iloc[0].get("source_record_id")
        source_batch_id = profile.iloc[0].get("source_batch_id")
        source_extract_ts = profile.iloc[0].get("source_extract_ts")
        return pd.DataFrame(
            [
                {
                    "source_system": source_system,
                    "source_record_id": source_record_id,
                    "source_batch_id": source_batch_id,
                    "source_extract_ts": source_extract_ts,
                    "entity_hint": "Vendor",
                }
            ]
        )

    def vendor_spend_by_category(self, vendor_id: str, months: int = 12) -> pd.DataFrame:
        months = max(1, min(months, 36))
        return self._query_file(
            "reporting/vendor_spend_by_category.sql",
            params=(vendor_id,),
            columns=["category", "total_spend"],
            rpt_spend_fact=self._table("rpt_spend_fact"),
            months_back=(months - 1),
        )

    def vendor_monthly_spend_trend(self, vendor_id: str, months: int = 12) -> pd.DataFrame:
        months = max(1, min(months, 36))
        return self._query_file(
            "reporting/vendor_monthly_spend_trend.sql",
            params=(vendor_id,),
            columns=["month", "total_spend"],
            rpt_spend_fact=self._table("rpt_spend_fact"),
            months_back=(months - 1),
        )

    def vendor_summary(self, vendor_id: str, months: int = 12) -> dict[str, Any]:
        profile = self.get_vendor_profile(vendor_id)
        offerings = self.get_vendor_offerings(vendor_id)
        contracts = self.get_vendor_contracts(vendor_id)
        demos = self.get_vendor_demos(vendor_id)
        spend = self.vendor_monthly_spend_trend(vendor_id, months=months)

        active_contracts = 0
        if not contracts.empty and "contract_status" in contracts.columns:
            active_contracts = int((contracts["contract_status"].astype(str).str.lower() == "active").sum())

        selected_demos = 0
        not_selected_demos = 0
        if not demos.empty and "selection_outcome" in demos.columns:
            selected_demos = int((demos["selection_outcome"] == "selected").sum())
            not_selected_demos = int((demos["selection_outcome"] == "not_selected").sum())

        active_offerings = offerings.copy()
        if "lifecycle_state" in active_offerings.columns:
            active_offerings = active_offerings[
                active_offerings["lifecycle_state"].astype(str).str.lower() == "active"
            ].copy()
        active_lob_values: list[str] = []
        active_service_type_values: list[str] = []
        if not active_offerings.empty:
            if "lob" in active_offerings.columns:
                active_lob_values = sorted(
                    {
                        str(value).strip()
                        for value in active_offerings["lob"].tolist()
                        if str(value).strip()
                    }
                )
            if "service_type" in active_offerings.columns:
                active_service_type_values = sorted(
                    {
                        str(value).strip()
                        for value in active_offerings["service_type"].tolist()
                        if str(value).strip()
                    }
                )

        return {
            "lifecycle_state": str(profile.iloc[0]["lifecycle_state"]) if not profile.empty else "unknown",
            "risk_tier": str(profile.iloc[0]["risk_tier"]) if not profile.empty else "unknown",
            "offering_count": float(len(offerings)),
            "active_contract_count": float(active_contracts),
            "demos_selected": float(selected_demos),
            "demos_not_selected": float(not_selected_demos),
            "active_lob_values": active_lob_values,
            "active_service_type_values": active_service_type_values,
            "total_spend_window": float(spend["total_spend"].sum()) if "total_spend" in spend else 0.0,
        }

