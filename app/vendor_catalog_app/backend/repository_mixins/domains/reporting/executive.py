from __future__ import annotations

import logging

import pandas as pd

from vendor_catalog_app.core.repository_constants import *

LOGGER = logging.getLogger(__name__)


class RepositoryReportingExecutiveMixin:
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

