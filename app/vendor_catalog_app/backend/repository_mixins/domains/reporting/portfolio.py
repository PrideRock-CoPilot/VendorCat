from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from vendor_catalog_app.core.repository_constants import *

LOGGER = logging.getLogger(__name__)


class RepositoryReportingPortfolioMixin:
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

    def report_vendor_warnings(
        self,
        *,
        search_text: str = "",
        vendor_id: str = "all",
        lifecycle_state: str = "all",
        limit: int = 500,
    ) -> pd.DataFrame:
        columns = [
            "warning_id",
            "vendor_id",
            "vendor_display_name",
            "lifecycle_state",
            "owner_org_id",
            "risk_tier",
            "warning_category",
            "severity",
            "warning_status",
            "warning_title",
            "warning_detail",
            "source_table",
            "source_version",
            "file_name",
            "detected_at",
            "resolved_at",
            "updated_at",
            "updated_by",
        ]
        limit = max(50, min(limit, 5000))
        where_parts = ["1 = 1"]
        params: list[Any] = []

        if vendor_id != "all":
            where_parts.append("w.vendor_id = %s")
            params.append(str(vendor_id))

        if lifecycle_state != "all":
            where_parts.append("lower(coalesce(v.lifecycle_state, '')) = lower(%s)")
            params.append(str(lifecycle_state))

        if search_text.strip():
            like = f"%{search_text.strip()}%"
            where_parts.append(
                "("
                "lower(coalesce(v.vendor_id, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.display_name, v.legal_name, '')) LIKE lower(%s)"
                " OR lower(coalesce(w.warning_category, '')) LIKE lower(%s)"
                " OR lower(coalesce(w.severity, '')) LIKE lower(%s)"
                " OR lower(coalesce(w.warning_status, '')) LIKE lower(%s)"
                " OR lower(coalesce(w.warning_title, '')) LIKE lower(%s)"
                " OR lower(coalesce(w.warning_detail, '')) LIKE lower(%s)"
                " OR lower(coalesce(w.source_table, '')) LIKE lower(%s)"
                " OR lower(coalesce(w.source_version, '')) LIKE lower(%s)"
                " OR lower(coalesce(w.file_name, '')) LIKE lower(%s)"
                ")"
            )
            params.extend([like] * 10)

        out = self._query_file(
            "reporting/report_vendor_warnings.sql",
            params=tuple(params) if params else None,
            where_clause=" AND ".join(where_parts),
            limit=limit,
            columns=columns,
            app_vendor_warning=self._table("app_vendor_warning"),
            core_vendor=self._table("core_vendor"),
        )
        if out.empty:
            return pd.DataFrame(columns=columns)
        return out[columns]

    def report_vendor_data_quality_overview(
        self,
        *,
        search_text: str = "",
        vendor_id: str = "all",
        lifecycle_state: str = "all",
        limit: int = 500,
    ) -> pd.DataFrame:
        columns = [
            "vendor_id",
            "vendor_display_name",
            "lifecycle_state",
            "owner_org_id",
            "risk_tier",
            "warning_count",
            "open_warning_count",
            "latest_warning_at",
            "offering_count",
            "latest_offering_updated_at",
            "contract_count",
            "latest_contract_updated_at",
            "demo_count",
            "latest_demo_updated_at",
            "invoice_count",
            "latest_invoice_date",
            "ticket_count",
            "latest_ticket_updated_at",
            "data_flow_count",
            "latest_data_flow_updated_at",
        ]
        limit = max(50, min(limit, 5000))
        where_parts = ["1 = 1"]
        params: list[Any] = []

        if vendor_id != "all":
            where_parts.append("v.vendor_id = %s")
            params.append(str(vendor_id))

        if lifecycle_state != "all":
            where_parts.append("lower(coalesce(v.lifecycle_state, '')) = lower(%s)")
            params.append(str(lifecycle_state))

        if search_text.strip():
            like = f"%{search_text.strip()}%"
            where_parts.append(
                "("
                "lower(coalesce(v.vendor_id, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.display_name, v.legal_name, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.owner_org_id, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.risk_tier, '')) LIKE lower(%s)"
                ")"
            )
            params.extend([like] * 4)

        out = self._query_file(
            "reporting/report_vendor_data_quality_overview.sql",
            params=tuple(params) if params else None,
            where_clause=" AND ".join(where_parts),
            limit=limit,
            columns=columns,
            core_vendor=self._table("core_vendor"),
            app_vendor_warning=self._table("app_vendor_warning"),
            core_vendor_offering=self._table("core_vendor_offering"),
            core_contract=self._table("core_contract"),
            core_vendor_demo=self._table("core_vendor_demo"),
            app_offering_invoice=self._table("app_offering_invoice"),
            app_offering_ticket=self._table("app_offering_ticket"),
            app_offering_data_flow=self._table("app_offering_data_flow"),
        )
        if out.empty:
            return pd.DataFrame(columns=columns)

        for count_col in [
            "warning_count",
            "open_warning_count",
            "offering_count",
            "contract_count",
            "demo_count",
            "invoice_count",
            "ticket_count",
            "data_flow_count",
        ]:
            out[count_col] = pd.to_numeric(out.get(count_col), errors="coerce").fillna(0).astype(int)
        return out[columns]

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

    def report_offering_budget_variance(
        self,
        *,
        search_text: str = "",
        vendor_id: str = "all",
        lifecycle_state: str = "all",
        horizon_days: int = 180,
        limit: int = 500,
    ) -> pd.DataFrame:
        columns = [
            "vendor_display_name",
            "vendor_id",
            "offering_name",
            "offering_id",
            "lifecycle_state",
            "estimated_monthly_cost",
            "avg_actual_monthly",
            "total_invoiced_window",
            "invoice_count_window",
            "active_month_count",
            "variance_amount",
            "variance_pct",
            "alert_status",
            "last_invoice_date",
        ]
        limit = max(50, min(limit, 5000))
        horizon_days = max(30, min(horizon_days, 730))
        where_parts = ["1 = 1"]
        params: list[Any] = []
        if vendor_id != "all":
            where_parts.append("o.vendor_id = %s")
            params.append(str(vendor_id))
        if lifecycle_state != "all":
            where_parts.append("lower(coalesce(o.lifecycle_state, '')) = lower(%s)")
            params.append(str(lifecycle_state))
        if search_text.strip():
            like = f"%{search_text.strip()}%"
            where_parts.append(
                "("
                "lower(o.offering_id) LIKE lower(%s)"
                " OR lower(coalesce(o.offering_name, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.display_name, v.legal_name, o.vendor_id)) LIKE lower(%s)"
                " OR lower(coalesce(o.vendor_id, '')) LIKE lower(%s)"
                ")"
            )
            params.extend([like, like, like, like])

        offerings = self._query_file(
            "reporting/report_offering_budget_variance_offerings.sql",
            params=tuple(params) if params else None,
            columns=[
                "offering_id",
                "vendor_id",
                "vendor_display_name",
                "offering_name",
                "lifecycle_state",
                "estimated_monthly_cost",
            ],
            where_clause=" AND ".join(where_parts),
            limit=max(limit * 3, 150),
            core_vendor_offering=self._table("core_vendor_offering"),
            core_vendor=self._table("core_vendor"),
            app_offering_profile=self._table("app_offering_profile"),
        )
        if offerings.empty:
            return pd.DataFrame(columns=columns)

        offering_ids = [str(value).strip() for value in offerings["offering_id"].tolist() if str(value).strip()]
        invoice_rows = pd.DataFrame(
            columns=["offering_id", "invoice_id", "invoice_date", "amount", "invoice_status"]
        )
        if offering_ids:
            placeholders = ", ".join(["%s"] * len(offering_ids))
            invoice_rows = self._query_file(
                "reporting/report_offering_budget_variance_invoices.sql",
                params=tuple(offering_ids),
                columns=["invoice_id", "offering_id", "vendor_id", "invoice_date", "amount", "invoice_status"],
                offering_ids_placeholders=placeholders,
                app_offering_invoice=self._table("app_offering_invoice"),
            )

        window_start = (self._now() - pd.Timedelta(days=(horizon_days - 1))).date()
        months_in_window = max(1, int((horizon_days + 29) // 30))
        amount_by_offering = pd.DataFrame(columns=["offering_id", "total_invoiced_window", "active_month_count"])
        invoice_meta = pd.DataFrame(columns=["offering_id", "invoice_count_window", "last_invoice_date"])
        if not invoice_rows.empty:
            invoice_rows["invoice_date"] = pd.to_datetime(invoice_rows.get("invoice_date"), errors="coerce")
            invoice_rows["amount"] = pd.to_numeric(invoice_rows.get("amount"), errors="coerce").fillna(0.0)
            invoice_rows = invoice_rows[invoice_rows["invoice_date"].notna()].copy()
            if not invoice_rows.empty:
                invoice_rows = invoice_rows[invoice_rows["invoice_date"].dt.date >= window_start].copy()
            if not invoice_rows.empty:
                invoice_rows["month"] = invoice_rows["invoice_date"].dt.to_period("M").dt.to_timestamp()
                monthly = (
                    invoice_rows.groupby(["offering_id", "month"], as_index=False)["amount"].sum()
                )
                amount_by_offering = (
                    monthly.groupby("offering_id", as_index=False)
                    .agg(
                        total_invoiced_window=("amount", "sum"),
                        active_month_count=("month", "nunique"),
                    )
                )
                invoice_meta = (
                    invoice_rows.groupby("offering_id", as_index=False)
                    .agg(
                        invoice_count_window=("invoice_id", "nunique"),
                        last_invoice_date=("invoice_date", "max"),
                    )
                )

        out = offerings.merge(amount_by_offering, on="offering_id", how="left")
        out = out.merge(invoice_meta, on="offering_id", how="left")
        out["estimated_monthly_cost"] = pd.to_numeric(out.get("estimated_monthly_cost"), errors="coerce")
        out["total_invoiced_window"] = pd.to_numeric(out.get("total_invoiced_window"), errors="coerce").fillna(0.0)
        out["avg_actual_monthly"] = out["total_invoiced_window"] / float(months_in_window)
        out["invoice_count_window"] = pd.to_numeric(out.get("invoice_count_window"), errors="coerce").fillna(0).astype(int)
        out["active_month_count"] = pd.to_numeric(out.get("active_month_count"), errors="coerce").fillna(0).astype(int)
        out["variance_amount"] = out["avg_actual_monthly"] - out["estimated_monthly_cost"].fillna(0.0)
        out["variance_pct"] = pd.Series([None] * len(out), dtype="float64")
        has_estimate = out["estimated_monthly_cost"].notna() & (out["estimated_monthly_cost"] > 0)
        out.loc[~has_estimate, "variance_amount"] = pd.NA
        out.loc[has_estimate, "variance_pct"] = (
            (out.loc[has_estimate, "variance_amount"] / out.loc[has_estimate, "estimated_monthly_cost"]) * 100.0
        )

        out["alert_status"] = "no_estimate"
        out.loc[has_estimate & (out["invoice_count_window"] == 0), "alert_status"] = "no_actuals"
        out.loc[has_estimate & (out["invoice_count_window"] > 0), "alert_status"] = "on_track"
        out.loc[has_estimate & (out["variance_pct"] >= 10.0), "alert_status"] = "over_budget"
        out.loc[has_estimate & (out["variance_pct"] <= -10.0), "alert_status"] = "under_budget"
        out["last_invoice_date"] = pd.to_datetime(out.get("last_invoice_date"), errors="coerce").dt.date.astype(str)
        out.loc[out["last_invoice_date"] == "NaT", "last_invoice_date"] = ""
        status_rank = {
            "over_budget": 0,
            "on_track": 1,
            "under_budget": 2,
            "no_actuals": 3,
            "no_estimate": 4,
        }
        out["_status_rank"] = out["alert_status"].map(lambda value: status_rank.get(str(value or "").strip(), 99))
        out = out.sort_values(
            ["_status_rank", "variance_pct", "vendor_display_name", "offering_name"],
            ascending=[True, False, True, True],
        )
        return out[columns].head(limit)

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

