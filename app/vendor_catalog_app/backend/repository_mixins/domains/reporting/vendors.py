from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import pandas as pd
from vendor_catalog_app.core.security import ACCESS_REQUEST_ALLOWED_ROLES
from vendor_catalog_app.core.repository_constants import *
from vendor_catalog_app.infrastructure.db import (
    DataConnectionError,
    DataExecutionError,
    DataQueryError,
)

LOGGER = logging.getLogger(__name__)


class RepositoryReportingVendorsMixin:
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

    def list_vendor_contacts_index(self, *, limit: int = 200000) -> pd.DataFrame:
        safe_limit = max(1, min(int(limit or 200000), 1000000))
        return self._cached(
            ("list_vendor_contacts_index", safe_limit),
            lambda: self._query_file(
                "reporting/list_vendor_contacts_index.sql",
                columns=[
                    "vendor_id",
                    "contact_type",
                    "full_name",
                    "email",
                    "phone",
                    "active_flag",
                    "vendor_display_name",
                    "legal_name",
                ],
                limit=safe_limit,
                core_vendor_contact=self._table("core_vendor_contact"),
                core_vendor=self._table("core_vendor"),
            ),
            ttl_seconds=300,
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
                "annual_value",
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

        if target_status == "approved" and str(current.get("change_type") or "").strip().lower() == "request_access":
            requested_payload = str(current.get("requested_payload_json") or "").strip()
            try:
                payload = json.loads(requested_payload) if requested_payload else {}
            except Exception:
                payload = {}
            requested_role = str((payload or {}).get("requested_role") or "").strip().lower()
            requestor_ref = str(
                current.get("requestor_user_principal_raw")
                or current.get("requestor_user_principal")
                or ""
            ).strip()
            if requestor_ref and requested_role in set(ACCESS_REQUEST_ALLOWED_ROLES):
                try:
                    self.grant_role(
                        target_user_principal=requestor_ref,
                        role_code=requested_role,
                        granted_by=actor_user_principal,
                    )
                except Exception:
                    LOGGER.warning(
                        "Approved access request could not be auto-granted for '%s' role '%s'.",
                        requestor_ref,
                        requested_role,
                        exc_info=True,
                    )
            elif requestor_ref and requested_role:
                LOGGER.warning(
                    "Approved access request requested disallowed role '%s' for '%s'.",
                    requested_role,
                    requestor_ref,
                )

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
            # Fresh environments often start with draft offerings only.
            # Fall back to all offerings so summary cards still show useful LOB/service values.
            if active_offerings.empty:
                active_offerings = offerings.copy()
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
