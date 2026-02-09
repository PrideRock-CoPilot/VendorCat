from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from vendor_catalog_app.config import AppConfig
from vendor_catalog_app.db import DatabricksSQLClient
from vendor_catalog_app import mock_data


class VendorRepository:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.client = DatabricksSQLClient(config)
        self._mock_role_overrides: dict[str, set[str]] = {}
        self._mock_user_settings: dict[tuple[str, str], dict[str, Any]] = {}
        self._mock_usage_events: list[dict[str, Any]] = []
        self._mock_new_vendors: list[dict[str, Any]] = []
        self._mock_vendor_overrides: dict[str, dict[str, Any]] = {}
        self._mock_new_offerings: list[dict[str, Any]] = []
        self._mock_offering_overrides: dict[str, dict[str, Any]] = {}
        self._mock_contract_overrides: dict[str, dict[str, Any]] = {}
        self._mock_demo_overrides: dict[str, dict[str, Any]] = {}
        self._mock_new_offering_owners: list[dict[str, Any]] = []
        self._mock_removed_offering_owner_ids: set[str] = set()
        self._mock_new_offering_contacts: list[dict[str, Any]] = []
        self._mock_removed_offering_contact_ids: set[str] = set()
        self._mock_change_request_overrides: list[dict[str, Any]] = []
        self._mock_audit_change_overrides: list[dict[str, Any]] = []
        self._mock_new_projects: list[dict[str, Any]] = []
        self._mock_project_overrides: dict[str, dict[str, Any]] = {}
        self._mock_project_vendor_overrides: dict[str, list[str]] = {}
        self._mock_project_offering_overrides: dict[str, list[str]] = {}
        self._mock_new_project_demos: list[dict[str, Any]] = []
        self._mock_project_demo_overrides: dict[str, dict[str, Any]] = {}
        self._mock_removed_project_demo_ids: set[str] = set()
        self._mock_new_project_notes: list[dict[str, Any]] = []
        self._mock_removed_project_note_ids: set[str] = set()
        self._mock_new_doc_links: list[dict[str, Any]] = []
        self._mock_doc_link_overrides: dict[str, dict[str, Any]] = {}
        self._mock_removed_doc_link_ids: set[str] = set()

    def _table(self, name: str) -> str:
        if self.config.use_local_db:
            return name
        return f"{self.config.fq_schema}.{name}"

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _query_or_empty(
        self, statement: str, params: tuple | None = None, columns: list[str] | None = None
    ) -> pd.DataFrame:
        try:
            return self.client.query(statement, params)
        except Exception:
            return pd.DataFrame(columns=columns or [])

    @staticmethod
    def _apply_org_filter(df: pd.DataFrame, org_id: str | None, org_column: str = "org_id") -> pd.DataFrame:
        if org_id and org_id != "all" and org_column in df.columns:
            return df[df[org_column] == org_id].copy()
        return df.copy()

    @staticmethod
    def _months_window(df: pd.DataFrame, month_col: str, months: int) -> pd.DataFrame:
        if month_col not in df.columns:
            return df
        months = max(1, min(months, 36))
        frame = df.copy()
        frame[month_col] = pd.to_datetime(frame[month_col], errors="coerce")
        if frame[month_col].isna().all():
            return frame
        max_month = frame[month_col].max()
        cutoff = (max_month - pd.DateOffset(months=months - 1)).replace(day=1)
        return frame[frame[month_col] >= cutoff]

    @staticmethod
    def _matches_needle(value: Any, needle: str) -> bool:
        if value is None:
            return False
        return needle in str(value).strip().lower()

    @staticmethod
    def _filter_contains_any(df: pd.DataFrame, needle: str, columns: list[str]) -> pd.DataFrame:
        cleaned = (needle or "").strip().lower()
        if df.empty or not cleaned:
            return df
        mask = pd.Series(False, index=df.index)
        for column in columns:
            if column in df.columns:
                mask = mask | df[column].astype(str).str.lower().str.contains(cleaned, regex=False, na=False)
        return df[mask].copy()

    def _serialize_payload(self, payload: dict[str, Any] | None) -> str:
        if not payload:
            return "{}"
        return json.dumps(payload)

    @staticmethod
    def _apply_row_overrides(
        df: pd.DataFrame,
        overrides: dict[str, dict[str, Any]],
        key_column: str,
    ) -> pd.DataFrame:
        if df.empty or not overrides or key_column not in df.columns:
            return df
        out = df.copy()
        for row_id, row_overrides in overrides.items():
            mask = out[key_column].astype(str) == str(row_id)
            if not mask.any():
                continue
            for key, value in row_overrides.items():
                if key in out.columns:
                    out.loc[mask, key] = value
        return out

    def _mock_offerings_df(self) -> pd.DataFrame:
        base = mock_data.offerings().copy()
        if self._mock_new_offerings:
            base = pd.concat([base, pd.DataFrame(self._mock_new_offerings)], ignore_index=True)
        return self._apply_row_overrides(base, self._mock_offering_overrides, "offering_id")

    def _mock_contracts_df(self) -> pd.DataFrame:
        base = mock_data.contracts().copy()
        return self._apply_row_overrides(base, self._mock_contract_overrides, "contract_id")

    def _mock_demos_df(self) -> pd.DataFrame:
        base = mock_data.demo_outcomes().copy()
        return self._apply_row_overrides(base, self._mock_demo_overrides, "demo_id")

    def _mock_offering_owners_df(self) -> pd.DataFrame:
        base = mock_data.offering_business_owners().copy()
        if self._mock_new_offering_owners:
            base = pd.concat([base, pd.DataFrame(self._mock_new_offering_owners)], ignore_index=True)
        if "offering_owner_id" in base.columns and self._mock_removed_offering_owner_ids:
            base = base[~base["offering_owner_id"].astype(str).isin(self._mock_removed_offering_owner_ids)].copy()
        return base

    def _mock_offering_contacts_df(self) -> pd.DataFrame:
        base = mock_data.offering_contacts().copy()
        if self._mock_new_offering_contacts:
            base = pd.concat([base, pd.DataFrame(self._mock_new_offering_contacts)], ignore_index=True)
        if "offering_contact_id" in base.columns and self._mock_removed_offering_contact_ids:
            base = base[~base["offering_contact_id"].astype(str).isin(self._mock_removed_offering_contact_ids)].copy()
        return base

    def _mock_append_audit_event(
        self,
        *,
        entity_name: str,
        entity_id: str,
        action_type: str,
        actor_user_principal: str,
        request_id: str | None = None,
    ) -> str:
        change_event_id = str(uuid.uuid4())
        self._mock_audit_change_overrides.append(
            {
                "change_event_id": change_event_id,
                "entity_name": entity_name,
                "entity_id": entity_id,
                "action_type": action_type,
                "event_ts": self._now().isoformat(),
                "actor_user_principal": actor_user_principal,
                "request_id": request_id,
            }
        )
        return change_event_id

    def _write_audit_entity_change(
        self,
        *,
        entity_name: str,
        entity_id: str,
        action_type: str,
        actor_user_principal: str,
        before_json: dict[str, Any] | None = None,
        after_json: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> str:
        change_event_id = str(uuid.uuid4())
        if self.config.use_mock:
            return self._mock_append_audit_event(
                entity_name=entity_name,
                entity_id=entity_id,
                action_type=action_type,
                actor_user_principal=actor_user_principal,
                request_id=request_id,
            )
        try:
            self.client.execute(
                f"""
                INSERT INTO {self._table('audit_entity_change')}
                  (change_event_id, entity_name, entity_id, action_type, before_json, after_json, actor_user_principal, event_ts, request_id)
                VALUES
                  (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    change_event_id,
                    entity_name,
                    entity_id,
                    action_type,
                    json.dumps(before_json, default=str) if before_json is not None else None,
                    json.dumps(after_json, default=str) if after_json is not None else None,
                    actor_user_principal,
                    self._now(),
                    request_id,
                ),
            )
        except Exception:
            pass
        return change_event_id

    def _mock_vendors_df(self) -> pd.DataFrame:
        base = mock_data.vendors().copy()
        if self._mock_new_vendors:
            base = pd.concat([base, pd.DataFrame(self._mock_new_vendors)], ignore_index=True)
        return self._apply_row_overrides(base, self._mock_vendor_overrides, "vendor_id")

    def _mock_change_requests_df(self) -> pd.DataFrame:
        base = mock_data.change_requests().copy()
        if self._mock_change_request_overrides:
            base = pd.concat([base, pd.DataFrame(self._mock_change_request_overrides)], ignore_index=True)
        return base

    def _mock_audit_changes_df(self) -> pd.DataFrame:
        base = mock_data.audit_entity_changes().copy()
        if self._mock_audit_change_overrides:
            base = pd.concat([base, pd.DataFrame(self._mock_audit_change_overrides)], ignore_index=True)
        return base

    def _mock_projects_df(self) -> pd.DataFrame:
        base = mock_data.projects().copy()
        if self._mock_new_projects:
            base = pd.concat([base, pd.DataFrame(self._mock_new_projects)], ignore_index=True)
        base = self._apply_row_overrides(base, self._mock_project_overrides, "project_id")
        if "active_flag" in base.columns:
            base = base[base["active_flag"].fillna(True) == True].copy()
        return base

    def _mock_project_offering_map_df(self) -> pd.DataFrame:
        base = mock_data.project_offering_maps().copy()
        override_rows: list[dict[str, Any]] = []
        for project_id, offering_ids in self._mock_project_offering_overrides.items():
            for offering_id in offering_ids:
                override_rows.append(
                    {
                        "project_offering_map_id": self._new_id("pom"),
                        "project_id": project_id,
                        "offering_id": offering_id,
                        "active_flag": True,
                    }
                )
        if override_rows:
            base = base[~base["project_id"].astype(str).isin(self._mock_project_offering_overrides.keys())].copy()
            base = pd.concat([base, pd.DataFrame(override_rows)], ignore_index=True)
        if "active_flag" in base.columns:
            base = base[base["active_flag"].fillna(True) == True].copy()
        return base

    def _mock_project_vendor_map_df(self) -> pd.DataFrame:
        projects = self._mock_projects_df()
        rows: list[dict[str, Any]] = []
        for row in projects.to_dict("records"):
            project_id = str(row.get("project_id") or "")
            primary_vendor = str(row.get("vendor_id") or "").strip()
            mapped_vendor_ids = self._mock_project_vendor_overrides.get(project_id)
            if mapped_vendor_ids is None:
                mapped_vendor_ids = [primary_vendor] if primary_vendor else []
            for vendor_id in mapped_vendor_ids:
                clean_vendor = str(vendor_id).strip()
                if not clean_vendor:
                    continue
                rows.append(
                    {
                        "project_vendor_map_id": self._new_id("pvm"),
                        "project_id": project_id,
                        "vendor_id": clean_vendor,
                        "active_flag": True,
                    }
                )
        if not rows:
            return pd.DataFrame(columns=["project_vendor_map_id", "project_id", "vendor_id", "active_flag"])
        out = pd.DataFrame(rows)
        out = out.drop_duplicates(subset=["project_id", "vendor_id"], keep="last")
        return out

    def _mock_project_demos_df(self) -> pd.DataFrame:
        base = mock_data.project_demos().copy()
        if self._mock_new_project_demos:
            base = pd.concat([base, pd.DataFrame(self._mock_new_project_demos)], ignore_index=True)
        base = self._apply_row_overrides(base, self._mock_project_demo_overrides, "project_demo_id")
        if "project_demo_id" in base.columns and self._mock_removed_project_demo_ids:
            base = base[~base["project_demo_id"].astype(str).isin(self._mock_removed_project_demo_ids)].copy()
        if "active_flag" in base.columns:
            base = base[base["active_flag"].fillna(True) == True].copy()
        return base

    def _mock_project_notes_df(self) -> pd.DataFrame:
        base = mock_data.project_notes().copy()
        if self._mock_new_project_notes:
            base = pd.concat([base, pd.DataFrame(self._mock_new_project_notes)], ignore_index=True)
        if "project_note_id" in base.columns and self._mock_removed_project_note_ids:
            base = base[~base["project_note_id"].astype(str).isin(self._mock_removed_project_note_ids)].copy()
        if "active_flag" in base.columns:
            base = base[base["active_flag"].fillna(True) == True].copy()
        return base

    def _mock_doc_links_df(self) -> pd.DataFrame:
        base = mock_data.document_links().copy()
        if self._mock_new_doc_links:
            base = pd.concat([base, pd.DataFrame(self._mock_new_doc_links)], ignore_index=True)
        base = self._apply_row_overrides(base, self._mock_doc_link_overrides, "doc_id")
        if "doc_id" in base.columns and self._mock_removed_doc_link_ids:
            base = base[~base["doc_id"].astype(str).isin(self._mock_removed_doc_link_ids)].copy()
        if "active_flag" in base.columns:
            base = base[base["active_flag"].fillna(True) == True].copy()
        return base

    def ensure_runtime_tables(self) -> None:
        if self.config.use_mock or self.config.use_local_db:
            return
        statements = [
            f"""
            CREATE TABLE IF NOT EXISTS {self._table('app_user_settings')} (
              setting_id STRING NOT NULL,
              user_principal STRING NOT NULL,
              setting_key STRING NOT NULL,
              setting_value_json STRING NOT NULL,
              updated_at TIMESTAMP NOT NULL,
              updated_by STRING NOT NULL
            ) USING DELTA
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self._table('app_usage_log')} (
              usage_event_id STRING NOT NULL,
              user_principal STRING NOT NULL,
              page_name STRING NOT NULL,
              event_type STRING NOT NULL,
              event_ts TIMESTAMP NOT NULL,
              payload_json STRING NOT NULL
            ) USING DELTA
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self._table('app_project')} (
              project_id STRING NOT NULL,
              vendor_id STRING,
              project_name STRING NOT NULL,
              project_type STRING,
              status STRING NOT NULL,
              start_date DATE,
              target_date DATE,
              owner_principal STRING,
              description STRING,
              active_flag BOOLEAN NOT NULL,
              created_at TIMESTAMP NOT NULL,
              created_by STRING NOT NULL,
              updated_at TIMESTAMP NOT NULL,
              updated_by STRING NOT NULL
            ) USING DELTA
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self._table('app_project_vendor_map')} (
              project_vendor_map_id STRING NOT NULL,
              project_id STRING NOT NULL,
              vendor_id STRING NOT NULL,
              active_flag BOOLEAN NOT NULL,
              created_at TIMESTAMP NOT NULL,
              created_by STRING NOT NULL,
              updated_at TIMESTAMP NOT NULL,
              updated_by STRING NOT NULL
            ) USING DELTA
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self._table('app_project_offering_map')} (
              project_offering_map_id STRING NOT NULL,
              project_id STRING NOT NULL,
              vendor_id STRING NOT NULL,
              offering_id STRING NOT NULL,
              active_flag BOOLEAN NOT NULL,
              created_at TIMESTAMP NOT NULL,
              created_by STRING NOT NULL,
              updated_at TIMESTAMP NOT NULL,
              updated_by STRING NOT NULL
            ) USING DELTA
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self._table('app_project_demo')} (
              project_demo_id STRING NOT NULL,
              project_id STRING NOT NULL,
              vendor_id STRING NOT NULL,
              demo_name STRING NOT NULL,
              demo_datetime_start TIMESTAMP,
              demo_datetime_end TIMESTAMP,
              demo_type STRING,
              outcome STRING,
              score DOUBLE,
              attendees_internal STRING,
              attendees_vendor STRING,
              notes STRING,
              followups STRING,
              linked_offering_id STRING,
              linked_vendor_demo_id STRING,
              active_flag BOOLEAN NOT NULL,
              created_at TIMESTAMP NOT NULL,
              created_by STRING NOT NULL,
              updated_at TIMESTAMP NOT NULL,
              updated_by STRING NOT NULL
            ) USING DELTA
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self._table('app_project_note')} (
              project_note_id STRING NOT NULL,
              project_id STRING NOT NULL,
              vendor_id STRING NOT NULL,
              note_text STRING NOT NULL,
              active_flag BOOLEAN NOT NULL,
              created_at TIMESTAMP NOT NULL,
              created_by STRING NOT NULL,
              updated_at TIMESTAMP NOT NULL,
              updated_by STRING NOT NULL
            ) USING DELTA
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {self._table('app_document_link')} (
              doc_id STRING NOT NULL,
              entity_type STRING NOT NULL,
              entity_id STRING NOT NULL,
              doc_title STRING NOT NULL,
              doc_url STRING NOT NULL,
              doc_type STRING NOT NULL,
              tags STRING,
              owner STRING,
              active_flag BOOLEAN NOT NULL,
              created_at TIMESTAMP NOT NULL,
              created_by STRING NOT NULL,
              updated_at TIMESTAMP NOT NULL,
              updated_by STRING NOT NULL
            ) USING DELTA
            """,
        ]
        for statement in statements:
            try:
                self.client.execute(statement)
            except Exception:
                # Do not block app startup if runtime user cannot create tables.
                pass

    def bootstrap_user_access(self, user_principal: str) -> set[str]:
        roles = self.get_user_roles(user_principal)
        if roles:
            return roles
        self.ensure_user_record(user_principal)
        return self.get_user_roles(user_principal)

    def ensure_user_record(self, user_principal: str) -> None:
        if self.config.use_mock:
            current = self.get_user_roles(user_principal)
            if not current:
                self._mock_role_overrides[user_principal] = {"vendor_viewer"}
            return

        current = self._query_or_empty(
            f"""
            SELECT 1 AS has_role
            FROM {self._table('sec_user_role_map')}
            WHERE user_principal = %s
              AND active_flag = true
              AND revoked_at IS NULL
            LIMIT 1
            """,
            params=(user_principal,),
            columns=["has_role"],
        )
        if not current.empty:
            return

        now = self._now()
        try:
            self.client.execute(
                f"""
                INSERT INTO {self._table('sec_user_role_map')}
                  (user_principal, role_code, active_flag, granted_by, granted_at, revoked_at)
                VALUES
                  (%s, %s, %s, %s, %s, %s)
                """,
                (user_principal, "vendor_viewer", True, "system:auto-bootstrap", now, None),
            )
            self._audit_access(
                actor_user_principal="system:auto-bootstrap",
                action_type="auto_provision_viewer",
                target_user_principal=user_principal,
                target_role="vendor_viewer",
                notes="User auto-provisioned with basic view rights.",
            )
        except Exception:
            # If role table is unavailable or write is blocked, app still falls back to view-only in UI.
            pass

    def get_user_setting(self, user_principal: str, setting_key: str) -> dict[str, Any]:
        if self.config.use_mock:
            return self._mock_user_settings.get((user_principal, setting_key), {})

        df = self._query_or_empty(
            f"""
            SELECT setting_value_json
            FROM {self._table('app_user_settings')}
            WHERE user_principal = %s
              AND setting_key = %s
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            params=(user_principal, setting_key),
            columns=["setting_value_json"],
        )
        if df.empty:
            return {}
        try:
            return json.loads(str(df.iloc[0]["setting_value_json"]))
        except Exception:
            return {}

    def save_user_setting(self, user_principal: str, setting_key: str, setting_value: dict[str, Any]) -> None:
        if self.config.use_mock:
            self._mock_user_settings[(user_principal, setting_key)] = setting_value
            return

        now = self._now()
        payload = self._serialize_payload(setting_value)
        try:
            self.client.execute(
                f"""
                DELETE FROM {self._table('app_user_settings')}
                WHERE user_principal = %s
                  AND setting_key = %s
                """,
                (user_principal, setting_key),
            )
            self.client.execute(
                f"""
                INSERT INTO {self._table('app_user_settings')}
                  (setting_id, user_principal, setting_key, setting_value_json, updated_at, updated_by)
                VALUES
                  (%s, %s, %s, %s, %s, %s)
                """,
                (str(uuid.uuid4()), user_principal, setting_key, payload, now, user_principal),
            )
        except Exception:
            pass

    def log_usage_event(
        self, user_principal: str, page_name: str, event_type: str, payload: dict[str, Any] | None = None
    ) -> None:
        if self.config.use_mock:
            self._mock_usage_events.append(
                {
                    "usage_event_id": str(uuid.uuid4()),
                    "user_principal": user_principal,
                    "page_name": page_name,
                    "event_type": event_type,
                    "event_ts": self._now().isoformat(),
                    "payload_json": self._serialize_payload(payload),
                }
            )
            return

        try:
            self.client.execute(
                f"""
                INSERT INTO {self._table('app_usage_log')}
                  (usage_event_id, user_principal, page_name, event_type, event_ts, payload_json)
                VALUES
                  (%s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    user_principal,
                    page_name,
                    event_type,
                    self._now(),
                    self._serialize_payload(payload),
                ),
            )
        except Exception:
            pass

    def get_current_user(self) -> str:
        if self.config.use_mock:
            return "admin@example.com"
        if self.config.use_local_db:
            return os.getenv("TVENDOR_TEST_USER", "admin@example.com")
        query = "SELECT current_user() AS user_principal"
        df = self.client.query(query)
        if df.empty:
            return "unknown_user"
        return str(df.iloc[0]["user_principal"])

    def get_user_roles(self, user_principal: str) -> set[str]:
        if self.config.use_mock:
            df = mock_data.role_map()
            rows = df[(df["user_principal"] == user_principal) & (df["active_flag"] == True)]
            base_roles = set(rows["role_code"].tolist())
            return base_roles.union(self._mock_role_overrides.get(user_principal, set()))

        df = self._query_or_empty(
            f"""
            SELECT DISTINCT role_code
            FROM {self._table("sec_user_role_map")}
            WHERE user_principal = %s
              AND active_flag = true
              AND revoked_at IS NULL
            """,
            params=(user_principal,),
            columns=["role_code"],
        )
        return set(df["role_code"].tolist()) if not df.empty else set()

    def dashboard_kpis(self) -> dict[str, int]:
        if self.config.use_mock:
            return {
                "active_vendors": int((self._mock_vendors_df()["lifecycle_state"] == "active").sum()),
                "active_offerings": int((self._mock_offerings_df()["lifecycle_state"] == "active").sum()),
                "demos_logged": int(len(self._mock_demos_df())),
                "cancelled_contracts": int(len(mock_data.contract_cancellations())),
            }

        vendor_df = self.client.query(
            f"SELECT COUNT(*) AS c FROM {self._table('core_vendor')} WHERE lifecycle_state = 'active'"
        )
        offering_df = self.client.query(
            f"SELECT COUNT(*) AS c FROM {self._table('core_vendor_offering')} WHERE lifecycle_state = 'active'"
        )
        demo_df = self.client.query(f"SELECT COUNT(*) AS c FROM {self._table('core_vendor_demo')}")
        cancel_df = self.client.query(
            f"""
            SELECT COUNT(*) AS c
            FROM {self._table('core_contract_event')}
            WHERE event_type = 'contract_cancelled'
            """
        )
        return {
            "active_vendors": int(vendor_df.iloc[0]["c"]),
            "active_offerings": int(offering_df.iloc[0]["c"]),
            "demos_logged": int(demo_df.iloc[0]["c"]),
            "cancelled_contracts": int(cancel_df.iloc[0]["c"]),
        }

    def available_orgs(self) -> list[str]:
        if self.config.use_mock:
            orgs = sorted(self._mock_vendors_df()["owner_org_id"].dropna().unique().tolist())
            return ["all"] + orgs
        df = self._query_or_empty(
            f"""
            SELECT DISTINCT owner_org_id AS org_id
            FROM {self._table('core_vendor')}
            WHERE owner_org_id IS NOT NULL
            ORDER BY owner_org_id
            """,
            columns=["org_id"],
        )
        if df.empty:
            return ["all"]
        return ["all"] + df["org_id"].astype(str).tolist()

    def executive_spend_by_category(self, org_id: str = "all", months: int = 12) -> pd.DataFrame:
        if self.config.use_mock:
            df = self._apply_org_filter(mock_data.spend_facts(), org_id)
            df = self._months_window(df, "month", months)
            grouped = (
                df.groupby("category", as_index=False)
                .agg(total_spend=("amount", "sum"))
                .sort_values("total_spend", ascending=False)
            )
            return grouped

        months = max(1, min(months, 36))
        org_clause = "AND org_id = %s" if org_id and org_id != "all" else ""
        params: tuple = (org_id,) if org_clause else ()
        return self._query_or_empty(
            f"""
            SELECT category, SUM(amount) AS total_spend
            FROM {self._table('rpt_spend_fact')}
            WHERE month >= add_months(date_trunc('month', current_date()), -{months - 1})
              {org_clause}
            GROUP BY category
            ORDER BY total_spend DESC
            """,
            params=params,
            columns=["category", "total_spend"],
        )

    def executive_monthly_spend_trend(self, org_id: str = "all", months: int = 12) -> pd.DataFrame:
        if self.config.use_mock:
            df = self._apply_org_filter(mock_data.spend_facts(), org_id)
            df = self._months_window(df, "month", months)
            grouped = (
                df.groupby("month", as_index=False)
                .agg(total_spend=("amount", "sum"))
                .sort_values("month")
            )
            return grouped

        months = max(1, min(months, 36))
        org_clause = "AND org_id = %s" if org_id and org_id != "all" else ""
        params: tuple = (org_id,) if org_clause else ()
        return self._query_or_empty(
            f"""
            SELECT month, SUM(amount) AS total_spend
            FROM {self._table('rpt_spend_fact')}
            WHERE month >= add_months(date_trunc('month', current_date()), -{months - 1})
              {org_clause}
            GROUP BY month
            ORDER BY month
            """,
            params=params,
            columns=["month", "total_spend"],
        )

    def executive_top_vendors_by_spend(
        self, org_id: str = "all", months: int = 12, limit: int = 10
    ) -> pd.DataFrame:
        limit = max(3, min(limit, 25))
        if self.config.use_mock:
            spend = self._apply_org_filter(mock_data.spend_facts(), org_id)
            spend = self._months_window(spend, "month", months)
            vendors = self._mock_vendors_df()[["vendor_id", "display_name", "risk_tier"]].copy()
            merged = spend.merge(vendors, how="left", on="vendor_id")
            top = (
                merged.groupby(["vendor_id", "display_name", "risk_tier"], as_index=False)
                .agg(total_spend=("amount", "sum"))
                .sort_values("total_spend", ascending=False)
                .head(limit)
            )
            top = top.rename(columns={"display_name": "vendor_name"})
            return top

        months = max(1, min(months, 36))
        org_clause = "AND sf.org_id = %s" if org_id and org_id != "all" else ""
        params: tuple = (org_id,) if org_clause else ()
        return self._query_or_empty(
            f"""
            SELECT
              sf.vendor_id,
              coalesce(v.display_name, v.legal_name) AS vendor_name,
              v.risk_tier,
              SUM(sf.amount) AS total_spend
            FROM {self._table('rpt_spend_fact')} sf
            LEFT JOIN {self._table('core_vendor')} v
              ON sf.vendor_id = v.vendor_id
            WHERE sf.month >= add_months(date_trunc('month', current_date()), -{months - 1})
              {org_clause}
            GROUP BY sf.vendor_id, coalesce(v.display_name, v.legal_name), v.risk_tier
            ORDER BY total_spend DESC
            LIMIT {limit}
            """,
            params=params,
            columns=["vendor_id", "vendor_name", "risk_tier", "total_spend"],
        )

    def executive_risk_distribution(self, org_id: str = "all") -> pd.DataFrame:
        if self.config.use_mock:
            df = self._mock_vendors_df().copy()
            if org_id and org_id != "all":
                df = df[df["owner_org_id"] == org_id]
            grouped = (
                df.groupby("risk_tier", as_index=False)
                .agg(vendor_count=("vendor_id", "count"))
                .sort_values("vendor_count", ascending=False)
            )
            return grouped

        org_clause = "AND owner_org_id = %s" if org_id and org_id != "all" else ""
        params: tuple = (org_id,) if org_clause else ()
        return self._query_or_empty(
            f"""
            SELECT risk_tier, COUNT(*) AS vendor_count
            FROM {self._table('core_vendor')}
            WHERE lifecycle_state = 'active'
              {org_clause}
            GROUP BY risk_tier
            ORDER BY vendor_count DESC
            """,
            params=params,
            columns=["risk_tier", "vendor_count"],
        )

    def executive_renewal_pipeline(self, org_id: str = "all", horizon_days: int = 180) -> pd.DataFrame:
        horizon_days = max(30, min(horizon_days, 365))
        if self.config.use_mock:
            renewals = self._apply_org_filter(mock_data.renewal_pipeline(), org_id)
            renewals = renewals.copy()
            renewals["renewal_date"] = pd.to_datetime(renewals["renewal_date"], errors="coerce")
            today = pd.Timestamp.utcnow().tz_localize(None).normalize()
            cutoff = today + pd.Timedelta(days=horizon_days)
            renewals = renewals[
                (renewals["renewal_date"] >= today) & (renewals["renewal_date"] <= cutoff)
            ]
            renewals["days_to_renewal"] = (renewals["renewal_date"] - today).dt.days
            return renewals.sort_values("renewal_date")

        org_clause = "AND org_id = %s" if org_id and org_id != "all" else ""
        params: tuple = (org_id,) if org_clause else ()
        return self._query_or_empty(
            f"""
            SELECT
              contract_id,
              vendor_id,
              vendor_name,
              org_id,
              category,
              renewal_date,
              annual_value,
              risk_tier,
              renewal_status,
              datediff(renewal_date, current_date()) AS days_to_renewal
            FROM {self._table('rpt_contract_renewals')}
            WHERE renewal_date BETWEEN current_date() AND date_add(current_date(), {horizon_days})
              {org_clause}
            ORDER BY renewal_date
            """,
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
        )

    def executive_summary(self, org_id: str = "all", months: int = 12, horizon_days: int = 180) -> dict[str, float]:
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

        if self.config.use_mock:
            offerings = self._mock_offerings_df()[["vendor_id", "lifecycle_state"]].copy()
            contracts = self._mock_contracts_df()[["vendor_id", "contract_status", "annual_value"]].copy()
            project_map = self._mock_project_vendor_map_df()[["project_id", "vendor_id"]].copy()
            owners = mock_data.vendor_business_owners().copy()
        else:
            offerings = self._query_or_empty(
                f"SELECT vendor_id, lifecycle_state FROM {self._table('core_vendor_offering')}",
                columns=["vendor_id", "lifecycle_state"],
            )
            contracts = self._query_or_empty(
                f"""
                SELECT vendor_id, contract_status, annual_value
                FROM {self._table('core_contract')}
                """,
                columns=["vendor_id", "contract_status", "annual_value"],
            )
            project_map = self._query_or_empty(
                f"""
                SELECT project_id, vendor_id
                FROM {self._table('app_project_vendor_map')}
                WHERE coalesce(active_flag, true) = true
                UNION ALL
                SELECT project_id, vendor_id
                FROM {self._table('app_project')}
                WHERE vendor_id IS NOT NULL
                  AND coalesce(active_flag, true) = true
                """,
                columns=["project_id", "vendor_id"],
            )
            owners = self._query_or_empty(
                f"""
                SELECT vendor_id, owner_user_principal, owner_role, active_flag
                FROM {self._table('core_vendor_business_owner')}
                """,
                columns=["vendor_id", "owner_user_principal", "owner_role", "active_flag"],
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

        if self.config.use_mock:
            project_vendor_map = self._mock_project_vendor_map_df()[["project_id", "vendor_id"]].copy()
            project_offering_map = self._mock_project_offering_map_df()[["project_id", "offering_id"]].copy()
            project_notes = self._mock_project_notes_df()[["project_id", "project_note_id"]].copy()
            project_docs = self._mock_doc_links_df()
            project_docs = project_docs[project_docs["entity_type"].astype(str) == "project"][["entity_id", "doc_id"]].copy()
        else:
            project_vendor_map = self._query_or_empty(
                f"""
                SELECT project_id, vendor_id
                FROM {self._table('app_project_vendor_map')}
                WHERE coalesce(active_flag, true) = true
                UNION ALL
                SELECT project_id, vendor_id
                FROM {self._table('app_project')}
                WHERE vendor_id IS NOT NULL
                  AND coalesce(active_flag, true) = true
                """,
                columns=["project_id", "vendor_id"],
            )
            project_offering_map = self._query_or_empty(
                f"""
                SELECT project_id, offering_id
                FROM {self._table('app_project_offering_map')}
                WHERE coalesce(active_flag, true) = true
                """,
                columns=["project_id", "offering_id"],
            )
            project_notes = self._query_or_empty(
                f"""
                SELECT project_id, project_note_id
                FROM {self._table('app_project_note')}
                WHERE coalesce(active_flag, true) = true
                """,
                columns=["project_id", "project_note_id"],
            )
            project_docs = self._query_or_empty(
                f"""
                SELECT entity_id, doc_id
                FROM {self._table('app_document_link')}
                WHERE entity_type = 'project'
                  AND coalesce(active_flag, true) = true
                """,
                columns=["entity_id", "doc_id"],
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
        if self.config.use_mock:
            vendors = self._mock_vendors_df()[["vendor_id", "display_name", "legal_name"]].copy()
            vendors["vendor_display_name"] = vendors["display_name"].fillna(vendors["legal_name"]).fillna(vendors["vendor_id"])

            vendor_owners = mock_data.vendor_business_owners().copy()
            vendor_owners = vendor_owners[vendor_owners["active_flag"].fillna(True) == True].copy()
            vendor_owners["entity_type"] = "vendor"
            vendor_owners["entity_id"] = vendor_owners["vendor_id"]
            vendor_owners = vendor_owners.merge(vendors[["vendor_id", "vendor_display_name"]], on="vendor_id", how="left")
            vendor_owners["entity_name"] = vendor_owners["vendor_display_name"]
            vendor_owners = vendor_owners.rename(
                columns={"owner_user_principal": "owner_principal", "owner_role": "owner_role"}
            )[
                [
                    "owner_principal",
                    "owner_role",
                    "entity_type",
                    "entity_id",
                    "entity_name",
                    "vendor_id",
                    "vendor_display_name",
                ]
            ]

            offering_owners = self._mock_offering_owners_df()[["offering_id", "owner_user_principal", "owner_role"]].copy()
            offerings = self._mock_offerings_df()[["offering_id", "vendor_id", "offering_name"]].copy()
            offering_owners = offering_owners.merge(offerings, on="offering_id", how="left")
            offering_owners = offering_owners.merge(vendors[["vendor_id", "vendor_display_name"]], on="vendor_id", how="left")
            offering_owners["entity_type"] = "offering"
            offering_owners["entity_id"] = offering_owners["offering_id"]
            offering_owners["entity_name"] = offering_owners["offering_name"].fillna(offering_owners["offering_id"])
            offering_owners = offering_owners.rename(
                columns={"owner_user_principal": "owner_principal", "owner_role": "owner_role"}
            )[
                [
                    "owner_principal",
                    "owner_role",
                    "entity_type",
                    "entity_id",
                    "entity_name",
                    "vendor_id",
                    "vendor_display_name",
                ]
            ]

            projects = self.list_all_projects(search_text="", status="all", vendor_id="all", limit=5000).copy()
            projects = projects[projects["owner_principal"].astype(str).str.strip() != ""].copy()
            projects["entity_type"] = "project"
            projects["entity_id"] = projects["project_id"]
            projects["entity_name"] = projects["project_name"]
            projects["owner_principal"] = projects["owner_principal"].astype(str)
            projects["owner_role"] = "project_owner"
            projects["vendor_display_name"] = projects["vendor_display_name"].fillna("Unassigned")
            project_owners = projects[
                [
                    "owner_principal",
                    "owner_role",
                    "entity_type",
                    "entity_id",
                    "entity_name",
                    "vendor_id",
                    "vendor_display_name",
                ]
            ].copy()

            out = pd.concat([vendor_owners, offering_owners, project_owners], ignore_index=True)
        else:
            out = self._query_or_empty(
                f"""
                SELECT
                  bo.owner_user_principal AS owner_principal,
                  bo.owner_role AS owner_role,
                  'vendor' AS entity_type,
                  bo.vendor_id AS entity_id,
                  coalesce(v.display_name, v.legal_name, bo.vendor_id) AS entity_name,
                  bo.vendor_id AS vendor_id,
                  coalesce(v.display_name, v.legal_name, bo.vendor_id) AS vendor_display_name
                FROM {self._table('core_vendor_business_owner')} bo
                LEFT JOIN {self._table('core_vendor')} v
                  ON bo.vendor_id = v.vendor_id
                WHERE coalesce(bo.active_flag, true) = true
                UNION ALL
                SELECT
                  obo.owner_user_principal AS owner_principal,
                  obo.owner_role AS owner_role,
                  'offering' AS entity_type,
                  obo.offering_id AS entity_id,
                  coalesce(o.offering_name, obo.offering_id) AS entity_name,
                  o.vendor_id AS vendor_id,
                  coalesce(v2.display_name, v2.legal_name, o.vendor_id) AS vendor_display_name
                FROM {self._table('core_offering_business_owner')} obo
                INNER JOIN {self._table('core_vendor_offering')} o
                  ON obo.offering_id = o.offering_id
                LEFT JOIN {self._table('core_vendor')} v2
                  ON o.vendor_id = v2.vendor_id
                WHERE coalesce(obo.active_flag, true) = true
                UNION ALL
                SELECT
                  p.owner_principal AS owner_principal,
                  'project_owner' AS owner_role,
                  'project' AS entity_type,
                  p.project_id AS entity_id,
                  p.project_name AS entity_name,
                  p.vendor_id AS vendor_id,
                  coalesce(v3.display_name, v3.legal_name, p.vendor_id, 'Unassigned') AS vendor_display_name
                FROM {self._table('app_project')} p
                LEFT JOIN {self._table('core_vendor')} v3
                  ON p.vendor_id = v3.vendor_id
                WHERE coalesce(p.active_flag, true) = true
                  AND p.owner_principal IS NOT NULL
                  AND trim(p.owner_principal) <> ''
                """,
                columns=columns,
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

    def search_vendors(self, search_text: str = "", lifecycle_state: str = "all") -> pd.DataFrame:
        if self.config.use_mock:
            df = self._mock_vendors_df().copy()
            if lifecycle_state != "all":
                df = df[df["lifecycle_state"] == lifecycle_state]
            if search_text.strip():
                needle = search_text.strip().lower()
                matched_vendor_ids: set[str] = set()

                for row in df.to_dict("records"):
                    for field in [
                        "vendor_id",
                        "legal_name",
                        "display_name",
                        "lifecycle_state",
                        "owner_org_id",
                        "risk_tier",
                        "source_system",
                        "source_record_id",
                        "source_batch_id",
                    ]:
                        if self._matches_needle(row.get(field), needle):
                            matched_vendor_ids.add(str(row.get("vendor_id")))
                            break

                offerings = self._mock_offerings_df()
                for row in offerings.to_dict("records"):
                    if any(
                        self._matches_needle(row.get(field), needle)
                        for field in ["offering_id", "offering_name", "offering_type", "lifecycle_state"]
                    ):
                        matched_vendor_ids.add(str(row.get("vendor_id")))

                contracts = self._mock_contracts_df()
                for row in contracts.to_dict("records"):
                    if any(
                        self._matches_needle(row.get(field), needle)
                        for field in ["contract_id", "contract_number", "contract_status", "offering_id"]
                    ):
                        matched_vendor_ids.add(str(row.get("vendor_id")))

                vendor_contacts = mock_data.contacts()
                for row in vendor_contacts.to_dict("records"):
                    if any(
                        self._matches_needle(row.get(field), needle)
                        for field in ["full_name", "email", "contact_type", "phone"]
                    ):
                        matched_vendor_ids.add(str(row.get("vendor_id")))

                vendor_owners = mock_data.vendor_business_owners()
                for row in vendor_owners.to_dict("records"):
                    if any(
                        self._matches_needle(row.get(field), needle)
                        for field in ["owner_user_principal", "owner_role"]
                    ):
                        matched_vendor_ids.add(str(row.get("vendor_id")))

                offering_contacts = self._mock_offering_contacts_df()
                if not offering_contacts.empty:
                    joined = offering_contacts.merge(
                        offerings[["offering_id", "vendor_id"]], on="offering_id", how="inner"
                    )
                    for row in joined.to_dict("records"):
                        if any(
                            self._matches_needle(row.get(field), needle)
                            for field in ["full_name", "email", "contact_type", "phone"]
                        ):
                            matched_vendor_ids.add(str(row.get("vendor_id")))

                offering_owners = self._mock_offering_owners_df()
                if not offering_owners.empty:
                    joined = offering_owners.merge(
                        offerings[["offering_id", "vendor_id"]], on="offering_id", how="inner"
                    )
                    for row in joined.to_dict("records"):
                        if any(
                            self._matches_needle(row.get(field), needle)
                            for field in ["owner_user_principal", "owner_role"]
                        ):
                            matched_vendor_ids.add(str(row.get("vendor_id")))

                demos = self._mock_demos_df()
                for row in demos.to_dict("records"):
                    if any(
                        self._matches_needle(row.get(field), needle)
                        for field in ["demo_id", "offering_id", "selection_outcome", "non_selection_reason_code", "notes"]
                    ):
                        matched_vendor_ids.add(str(row.get("vendor_id")))

                projects = self._mock_projects_df()
                for row in projects.to_dict("records"):
                    if any(
                        self._matches_needle(row.get(field), needle)
                        for field in ["project_id", "project_name", "project_type", "status", "owner_principal", "description"]
                    ):
                        matched_vendor_ids.add(str(row.get("vendor_id")))

                df = df[df["vendor_id"].astype(str).isin(matched_vendor_ids)]
            return df.sort_values("display_name")

        state_clause = ""
        params: list[str] = []
        if lifecycle_state != "all":
            state_clause = "AND v.lifecycle_state = %s"
            params.append(lifecycle_state)

        if not search_text.strip():
            query = f"""
                SELECT vendor_id, legal_name, display_name, lifecycle_state, owner_org_id, risk_tier, updated_at
                FROM {self._table("core_vendor")} v
                WHERE 1 = 1
                {state_clause}
                ORDER BY display_name
                LIMIT 250
            """
            return self.client.query(query, tuple(params))

        like = f"%{search_text.strip()}%"
        broad_query = f"""
            SELECT DISTINCT
              v.vendor_id,
              v.legal_name,
              v.display_name,
              v.lifecycle_state,
              v.owner_org_id,
              v.risk_tier,
              v.updated_at
            FROM {self._table("core_vendor")} v
            WHERE (
              lower(v.vendor_id) LIKE lower(%s)
              OR lower(coalesce(v.legal_name, '')) LIKE lower(%s)
              OR lower(coalesce(v.display_name, '')) LIKE lower(%s)
              OR lower(coalesce(v.owner_org_id, '')) LIKE lower(%s)
              OR lower(coalesce(v.risk_tier, '')) LIKE lower(%s)
              OR lower(coalesce(v.source_system, '')) LIKE lower(%s)
              OR lower(coalesce(v.source_record_id, '')) LIKE lower(%s)
              OR lower(coalesce(v.source_batch_id, '')) LIKE lower(%s)
              OR EXISTS (
                SELECT 1
                FROM {self._table('core_vendor_offering')} o
                WHERE o.vendor_id = v.vendor_id
                  AND (
                    lower(o.offering_id) LIKE lower(%s)
                    OR lower(coalesce(o.offering_name, '')) LIKE lower(%s)
                    OR lower(coalesce(o.offering_type, '')) LIKE lower(%s)
                  )
              )
              OR EXISTS (
                SELECT 1
                FROM {self._table('core_contract')} c
                WHERE c.vendor_id = v.vendor_id
                  AND (
                    lower(c.contract_id) LIKE lower(%s)
                    OR lower(coalesce(c.contract_number, '')) LIKE lower(%s)
                    OR lower(coalesce(c.contract_status, '')) LIKE lower(%s)
                  )
              )
              OR EXISTS (
                SELECT 1
                FROM {self._table('core_vendor_business_owner')} bo
                WHERE bo.vendor_id = v.vendor_id
                  AND (
                    lower(coalesce(bo.owner_user_principal, '')) LIKE lower(%s)
                    OR lower(coalesce(bo.owner_role, '')) LIKE lower(%s)
                  )
              )
              OR EXISTS (
                SELECT 1
                FROM {self._table('core_offering_business_owner')} obo
                INNER JOIN {self._table('core_vendor_offering')} o2
                  ON obo.offering_id = o2.offering_id
                WHERE o2.vendor_id = v.vendor_id
                  AND (
                    lower(coalesce(obo.owner_user_principal, '')) LIKE lower(%s)
                    OR lower(coalesce(obo.owner_role, '')) LIKE lower(%s)
                  )
              )
              OR EXISTS (
                SELECT 1
                FROM {self._table('core_vendor_contact')} vc
                WHERE vc.vendor_id = v.vendor_id
                  AND (
                    lower(coalesce(vc.full_name, '')) LIKE lower(%s)
                    OR lower(coalesce(vc.email, '')) LIKE lower(%s)
                    OR lower(coalesce(vc.contact_type, '')) LIKE lower(%s)
                    OR lower(coalesce(vc.phone, '')) LIKE lower(%s)
                  )
              )
              OR EXISTS (
                SELECT 1
                FROM {self._table('core_offering_contact')} oc
                INNER JOIN {self._table('core_vendor_offering')} o3
                  ON oc.offering_id = o3.offering_id
                WHERE o3.vendor_id = v.vendor_id
                  AND (
                    lower(coalesce(oc.full_name, '')) LIKE lower(%s)
                    OR lower(coalesce(oc.email, '')) LIKE lower(%s)
                    OR lower(coalesce(oc.contact_type, '')) LIKE lower(%s)
                    OR lower(coalesce(oc.phone, '')) LIKE lower(%s)
                  )
              )
              OR EXISTS (
                SELECT 1
                FROM {self._table('core_vendor_demo')} d
                WHERE d.vendor_id = v.vendor_id
                  AND (
                    lower(d.demo_id) LIKE lower(%s)
                    OR lower(coalesce(d.offering_id, '')) LIKE lower(%s)
                    OR lower(coalesce(d.selection_outcome, '')) LIKE lower(%s)
                    OR lower(coalesce(d.non_selection_reason_code, '')) LIKE lower(%s)
                    OR lower(coalesce(d.notes, '')) LIKE lower(%s)
                  )
              )
              OR EXISTS (
                SELECT 1
                FROM {self._table('app_project')} p
                WHERE p.vendor_id = v.vendor_id
                  AND coalesce(p.active_flag, true) = true
                  AND (
                    lower(p.project_id) LIKE lower(%s)
                    OR lower(coalesce(p.project_name, '')) LIKE lower(%s)
                    OR lower(coalesce(p.project_type, '')) LIKE lower(%s)
                    OR lower(coalesce(p.status, '')) LIKE lower(%s)
                    OR lower(coalesce(p.owner_principal, '')) LIKE lower(%s)
                    OR lower(coalesce(p.description, '')) LIKE lower(%s)
                  )
              )
            )
            {state_clause}
            ORDER BY v.display_name
            LIMIT 250
        """
        broad_params = [like] * 37 + params

        try:
            return self.client.query(broad_query, tuple(broad_params))
        except Exception:
            fallback_query = f"""
                SELECT vendor_id, legal_name, display_name, lifecycle_state, owner_org_id, risk_tier, updated_at
                FROM {self._table("core_vendor")} v
                WHERE (
                  lower(v.legal_name) LIKE lower(%s)
                  OR lower(coalesce(v.display_name, '')) LIKE lower(%s)
                  OR lower(v.vendor_id) LIKE lower(%s)
                )
                {state_clause}
                ORDER BY v.display_name
                LIMIT 250
            """
            return self.client.query(fallback_query, tuple([like, like, like] + params))

    def get_vendor_profile(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            return self._mock_vendors_df().query("vendor_id == @vendor_id")
        return self.client.query(
            f"SELECT * FROM {self._table('core_vendor')} WHERE vendor_id = %s", (vendor_id,)
        )

    def get_vendor_offerings(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            return self._mock_offerings_df().query("vendor_id == @vendor_id")
        return self.client.query(
            f"""
            SELECT offering_id, vendor_id, offering_name, offering_type, lifecycle_state, criticality_tier
            FROM {self._table('core_vendor_offering')}
            WHERE vendor_id = %s
            ORDER BY offering_name
            """,
            (vendor_id,),
        )

    def get_vendor_contacts(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            return mock_data.contacts().query("vendor_id == @vendor_id")
        return self.client.query(
            f"""
            SELECT vendor_contact_id, vendor_id, contact_type, full_name, email, phone, active_flag
            FROM {self._table('core_vendor_contact')}
            WHERE vendor_id = %s
            ORDER BY full_name
            """,
            (vendor_id,),
        )

    def get_vendor_identifiers(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            return mock_data.vendor_identifiers().query("vendor_id == @vendor_id")
        return self._query_or_empty(
            f"""
            SELECT vendor_identifier_id, vendor_id, identifier_type, identifier_value, is_primary, country_code
            FROM {self._table('core_vendor_identifier')}
            WHERE vendor_id = %s
            ORDER BY is_primary DESC, identifier_type
            """,
            params=(vendor_id,),
            columns=[
                "vendor_identifier_id",
                "vendor_id",
                "identifier_type",
                "identifier_value",
                "is_primary",
                "country_code",
            ],
        )

    def get_vendor_business_owners(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            return mock_data.vendor_business_owners().query("vendor_id == @vendor_id")
        return self._query_or_empty(
            f"""
            SELECT vendor_owner_id, vendor_id, owner_user_principal, owner_role, active_flag
            FROM {self._table('core_vendor_business_owner')}
            WHERE vendor_id = %s
            ORDER BY active_flag DESC, owner_role
            """,
            params=(vendor_id,),
            columns=["vendor_owner_id", "vendor_id", "owner_user_principal", "owner_role", "active_flag"],
        )

    def get_vendor_org_assignments(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            return mock_data.vendor_org_assignments().query("vendor_id == @vendor_id")
        return self._query_or_empty(
            f"""
            SELECT vendor_org_assignment_id, vendor_id, org_id, assignment_type, active_flag
            FROM {self._table('core_vendor_org_assignment')}
            WHERE vendor_id = %s
            ORDER BY active_flag DESC, org_id
            """,
            params=(vendor_id,),
            columns=["vendor_org_assignment_id", "vendor_id", "org_id", "assignment_type", "active_flag"],
        )

    def get_vendor_offering_business_owners(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            offs = self._mock_offerings_df().query("vendor_id == @vendor_id")[["offering_id", "offering_name"]]
            owners = self._mock_offering_owners_df()
            merged = owners.merge(offs, on="offering_id", how="inner")
            return merged
        return self._query_or_empty(
            f"""
            SELECT
              o.offering_id,
              o.offering_name,
              obo.offering_owner_id,
              obo.owner_user_principal,
              obo.owner_role,
              obo.active_flag
            FROM {self._table('core_offering_business_owner')} obo
            INNER JOIN {self._table('core_vendor_offering')} o
              ON obo.offering_id = o.offering_id
            WHERE o.vendor_id = %s
            ORDER BY o.offering_name, obo.active_flag DESC
            """,
            params=(vendor_id,),
            columns=[
                "offering_id",
                "offering_name",
                "offering_owner_id",
                "owner_user_principal",
                "owner_role",
                "active_flag",
            ],
        )

    def get_vendor_offering_contacts(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            offs = self._mock_offerings_df().query("vendor_id == @vendor_id")[["offering_id", "offering_name"]]
            contacts = self._mock_offering_contacts_df()
            merged = contacts.merge(offs, on="offering_id", how="inner")
            return merged
        return self._query_or_empty(
            f"""
            SELECT
              o.offering_id,
              o.offering_name,
              c.offering_contact_id,
              c.contact_type,
              c.full_name,
              c.email,
              c.phone,
              c.active_flag
            FROM {self._table('core_offering_contact')} c
            INNER JOIN {self._table('core_vendor_offering')} o
              ON c.offering_id = o.offering_id
            WHERE o.vendor_id = %s
            ORDER BY o.offering_name, c.full_name
            """,
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
        )

    def get_vendor_contracts(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            return self._mock_contracts_df().query("vendor_id == @vendor_id")
        return self._query_or_empty(
            f"""
            SELECT contract_id, vendor_id, offering_id, contract_number, contract_status, start_date, end_date, cancelled_flag
            FROM {self._table('core_contract')}
            WHERE vendor_id = %s
            ORDER BY end_date DESC
            """,
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
        )

    def get_vendor_contract_events(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            contracts = self._mock_contracts_df().query("vendor_id == @vendor_id")[["contract_id"]]
            events = mock_data.contract_events()
            return events.merge(contracts, on="contract_id", how="inner").sort_values("event_ts", ascending=False)
        return self._query_or_empty(
            f"""
            SELECT e.contract_event_id, e.contract_id, e.event_type, e.event_ts, e.reason_code, e.notes, e.actor_user_principal
            FROM {self._table('core_contract_event')} e
            INNER JOIN {self._table('core_contract')} c
              ON e.contract_id = c.contract_id
            WHERE c.vendor_id = %s
            ORDER BY e.event_ts DESC
            """,
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
        )

    def get_vendor_demos(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            return self._mock_demos_df().query("vendor_id == @vendor_id").sort_values("demo_date", ascending=False)
        return self._query_or_empty(
            f"""
            SELECT demo_id, vendor_id, offering_id, demo_date, overall_score, selection_outcome, non_selection_reason_code, notes
            FROM {self._table('core_vendor_demo')}
            WHERE vendor_id = %s
            ORDER BY demo_date DESC
            """,
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
        )

    def get_vendor_demo_scores(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            demos = self._mock_demos_df().query("vendor_id == @vendor_id")[["demo_id"]]
            return mock_data.demo_scores().merge(demos, on="demo_id", how="inner")
        return self._query_or_empty(
            f"""
            SELECT s.demo_score_id, s.demo_id, s.score_category, s.score_value, s.weight, s.comments
            FROM {self._table('core_vendor_demo_score')} s
            INNER JOIN {self._table('core_vendor_demo')} d
              ON s.demo_id = d.demo_id
            WHERE d.vendor_id = %s
            ORDER BY d.demo_date DESC, s.score_category
            """,
            params=(vendor_id,),
            columns=["demo_score_id", "demo_id", "score_category", "score_value", "weight", "comments"],
        )

    def get_vendor_demo_notes(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            demos = self._mock_demos_df().query("vendor_id == @vendor_id")[["demo_id"]]
            return mock_data.demo_notes().merge(demos, on="demo_id", how="inner")
        return self._query_or_empty(
            f"""
            SELECT n.demo_note_id, n.demo_id, n.note_type, n.note_text, n.created_at, n.created_by
            FROM {self._table('core_vendor_demo_note')} n
            INNER JOIN {self._table('core_vendor_demo')} d
              ON n.demo_id = d.demo_id
            WHERE d.vendor_id = %s
            ORDER BY n.created_at DESC
            """,
            params=(vendor_id,),
            columns=["demo_note_id", "demo_id", "note_type", "note_text", "created_at", "created_by"],
        )

    def get_vendor_change_requests(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            return self._mock_change_requests_df().query("vendor_id == @vendor_id").sort_values("submitted_at", ascending=False)
        return self._query_or_empty(
            f"""
            SELECT change_request_id, vendor_id, requestor_user_principal, change_type, requested_payload_json, status, submitted_at, updated_at
            FROM {self._table('app_vendor_change_request')}
            WHERE vendor_id = %s
            ORDER BY submitted_at DESC
            """,
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
        )

    def get_vendor_audit_events(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            events = self._mock_audit_changes_df()
            requests = self._mock_change_requests_df().query("vendor_id == @vendor_id")["change_request_id"].tolist()
            vendor_events = events[(events["entity_id"] == vendor_id) | (events["request_id"].isin(requests))]
            return vendor_events.sort_values("event_ts", ascending=False)
        return self._query_or_empty(
            f"""
            SELECT change_event_id, entity_name, entity_id, action_type, event_ts, actor_user_principal, request_id
            FROM {self._table('audit_entity_change')}
            WHERE entity_id = %s
               OR request_id IN (
                    SELECT change_request_id
                    FROM {self._table('app_vendor_change_request')}
                    WHERE vendor_id = %s
               )
            ORDER BY event_ts DESC
            LIMIT 500
            """,
            params=(vendor_id, vendor_id),
            columns=[
                "change_event_id",
                "entity_name",
                "entity_id",
                "action_type",
                "event_ts",
                "actor_user_principal",
                "request_id",
            ],
        )

    def get_vendor_source_lineage(self, vendor_id: str) -> pd.DataFrame:
        profile = self.get_vendor_profile(vendor_id)
        if profile.empty:
            return pd.DataFrame(
                columns=["source_system", "source_record_id", "source_batch_id", "source_extract_ts", "entity_hint"]
            )

        if self.config.use_mock:
            source_record_id = str(profile.iloc[0].get("source_record_id", ""))
            line = mock_data.source_records()
            return line[line["source_record_id"] == source_record_id]

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
        if self.config.use_mock:
            spend = mock_data.spend_facts().query("vendor_id == @vendor_id")
            spend = self._months_window(spend, "month", months)
            return (
                spend.groupby("category", as_index=False)
                .agg(total_spend=("amount", "sum"))
                .sort_values("total_spend", ascending=False)
            )
        months = max(1, min(months, 36))
        return self._query_or_empty(
            f"""
            SELECT category, SUM(amount) AS total_spend
            FROM {self._table('rpt_spend_fact')}
            WHERE vendor_id = %s
              AND month >= add_months(date_trunc('month', current_date()), -{months - 1})
            GROUP BY category
            ORDER BY total_spend DESC
            """,
            params=(vendor_id,),
            columns=["category", "total_spend"],
        )

    def vendor_monthly_spend_trend(self, vendor_id: str, months: int = 12) -> pd.DataFrame:
        if self.config.use_mock:
            spend = mock_data.spend_facts().query("vendor_id == @vendor_id")
            spend = self._months_window(spend, "month", months)
            return (
                spend.groupby("month", as_index=False)
                .agg(total_spend=("amount", "sum"))
                .sort_values("month")
            )
        months = max(1, min(months, 36))
        return self._query_or_empty(
            f"""
            SELECT month, SUM(amount) AS total_spend
            FROM {self._table('rpt_spend_fact')}
            WHERE vendor_id = %s
              AND month >= add_months(date_trunc('month', current_date()), -{months - 1})
            GROUP BY month
            ORDER BY month
            """,
            params=(vendor_id,),
            columns=["month", "total_spend"],
        )

    def vendor_summary(self, vendor_id: str, months: int = 12) -> dict[str, float]:
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

        return {
            "lifecycle_state": str(profile.iloc[0]["lifecycle_state"]) if not profile.empty else "unknown",
            "risk_tier": str(profile.iloc[0]["risk_tier"]) if not profile.empty else "unknown",
            "offering_count": float(len(offerings)),
            "active_contract_count": float(active_contracts),
            "demos_selected": float(selected_demos),
            "demos_not_selected": float(not_selected_demos),
            "total_spend_window": float(spend["total_spend"].sum()) if "total_spend" in spend else 0.0,
        }

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _normalize_offering_id(offering_id: str | None) -> str | None:
        if offering_id is None:
            return None
        cleaned = str(offering_id).strip()
        return cleaned or None

    def get_offering_record(self, vendor_id: str, offering_id: str) -> dict[str, Any] | None:
        offerings = self.get_vendor_offerings(vendor_id)
        if offerings.empty:
            return None
        matched = offerings[offerings["offering_id"].astype(str) == str(offering_id)]
        if matched.empty:
            return None
        return matched.iloc[0].to_dict()

    def offering_belongs_to_vendor(self, vendor_id: str, offering_id: str) -> bool:
        if not offering_id:
            return False
        if self.config.use_mock:
            return self.get_offering_record(vendor_id, offering_id) is not None
        check = self._query_or_empty(
            f"""
            SELECT 1 AS present
            FROM {self._table('core_vendor_offering')}
            WHERE vendor_id = %s
              AND offering_id = %s
            LIMIT 1
            """,
            params=(vendor_id, offering_id),
            columns=["present"],
        )
        return not check.empty

    def get_unassigned_contracts(self, vendor_id: str) -> pd.DataFrame:
        contracts = self.get_vendor_contracts(vendor_id).copy()
        if contracts.empty or "offering_id" not in contracts.columns:
            return contracts
        return contracts[
            contracts["offering_id"].isna()
            | (contracts["offering_id"].astype(str).str.strip() == "")
        ].copy()

    def get_unassigned_demos(self, vendor_id: str) -> pd.DataFrame:
        demos = self.get_vendor_demos(vendor_id).copy()
        if demos.empty or "offering_id" not in demos.columns:
            return demos
        return demos[
            demos["offering_id"].isna()
            | (demos["offering_id"].astype(str).str.strip() == "")
        ].copy()

    def create_vendor_profile(
        self,
        *,
        actor_user_principal: str,
        legal_name: str,
        display_name: str | None = None,
        lifecycle_state: str = "draft",
        owner_org_id: str | None = None,
        risk_tier: str | None = None,
        source_system: str | None = "manual",
    ) -> str:
        legal_name = legal_name.strip()
        if not legal_name:
            raise ValueError("Legal name is required.")
        owner_org_id = (owner_org_id or "").strip()
        if not owner_org_id:
            raise ValueError("Owner Org ID is required.")
        vendor_id = self._new_id("vnd")
        now = self._now()
        row = {
            "vendor_id": vendor_id,
            "legal_name": legal_name,
            "display_name": (display_name or legal_name).strip(),
            "lifecycle_state": lifecycle_state,
            "owner_org_id": owner_org_id,
            "risk_tier": (risk_tier or "").strip() or None,
            "source_system": (source_system or "manual").strip() or "manual",
            "source_record_id": f"manual-{vendor_id}",
            "source_batch_id": f"manual-{now.strftime('%Y%m%d%H%M%S')}",
            "source_extract_ts": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        if self.config.use_mock:
            self._mock_new_vendors.append(row)
            self._write_audit_entity_change(
                entity_name="core_vendor",
                entity_id=vendor_id,
                action_type="insert",
                actor_user_principal=actor_user_principal,
                before_json=None,
                after_json=row,
                request_id=None,
            )
            return vendor_id

        self.client.execute(
            f"""
            INSERT INTO {self._table('core_vendor')}
              (vendor_id, legal_name, display_name, lifecycle_state, owner_org_id, risk_tier, source_system, updated_at, updated_by)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                vendor_id,
                row["legal_name"],
                row["display_name"],
                row["lifecycle_state"],
                row["owner_org_id"],
                row["risk_tier"],
                row["source_system"],
                now,
                actor_user_principal,
            ),
        )
        self._write_audit_entity_change(
            entity_name="core_vendor",
            entity_id=vendor_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return vendor_id

    def create_offering(
        self,
        *,
        vendor_id: str,
        actor_user_principal: str,
        offering_name: str,
        offering_type: str | None = None,
        lifecycle_state: str = "draft",
        criticality_tier: str | None = None,
    ) -> str:
        offering_name = offering_name.strip()
        if not offering_name:
            raise ValueError("Offering name is required.")
        profile = self.get_vendor_profile(vendor_id)
        if profile.empty:
            raise ValueError("Vendor not found.")

        offering_id = self._new_id("off")
        row = {
            "offering_id": offering_id,
            "vendor_id": vendor_id,
            "offering_name": offering_name,
            "offering_type": (offering_type or "").strip() or None,
            "lifecycle_state": lifecycle_state,
            "criticality_tier": (criticality_tier or "").strip() or None,
        }

        if self.config.use_mock:
            self._mock_new_offerings.append(row)
            self._write_audit_entity_change(
                entity_name="core_vendor_offering",
                entity_id=offering_id,
                action_type="insert",
                actor_user_principal=actor_user_principal,
                before_json=None,
                after_json=row,
                request_id=None,
            )
            return offering_id

        self.client.execute(
            f"""
            INSERT INTO {self._table('core_vendor_offering')}
              (offering_id, vendor_id, offering_name, offering_type, lifecycle_state, criticality_tier)
            VALUES
              (%s, %s, %s, %s, %s, %s)
            """,
            (
                offering_id,
                vendor_id,
                row["offering_name"],
                row["offering_type"],
                row["lifecycle_state"],
                row["criticality_tier"],
            ),
        )
        self._write_audit_entity_change(
            entity_name="core_vendor_offering",
            entity_id=offering_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return offering_id

    def update_offering_fields(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        actor_user_principal: str,
        updates: dict[str, Any],
        reason: str,
    ) -> dict[str, str]:
        allowed = {"offering_name", "offering_type", "lifecycle_state", "criticality_tier"}
        clean_updates = {k: v for k, v in updates.items() if k in allowed}
        if not clean_updates:
            raise ValueError("No editable fields were provided.")
        if not reason.strip():
            raise ValueError("Reason is required.")

        current = self.get_offering_record(vendor_id, offering_id)
        if current is None:
            raise ValueError("Offering not found for vendor.")
        before = dict(current)
        after = dict(current)
        after.update(clean_updates)

        request_id = str(uuid.uuid4())
        if self.config.use_mock:
            self._mock_offering_overrides[offering_id] = {
                **self._mock_offering_overrides.get(offering_id, {}),
                **clean_updates,
            }
            self._mock_change_request_overrides.append(
                {
                    "change_request_id": request_id,
                    "vendor_id": vendor_id,
                    "requestor_user_principal": actor_user_principal,
                    "change_type": "direct_update_offering",
                    "requested_payload_json": self._serialize_payload({"offering_id": offering_id, "updates": clean_updates, "reason": reason}),
                    "status": "approved",
                    "submitted_at": self._now().isoformat(),
                    "updated_at": self._now().isoformat(),
                }
            )
            change_event_id = self._write_audit_entity_change(
                entity_name="core_vendor_offering",
                entity_id=offering_id,
                action_type="update",
                actor_user_principal=actor_user_principal,
                before_json=before,
                after_json=after,
                request_id=request_id,
            )
            return {"request_id": request_id, "change_event_id": change_event_id}

        set_clause = ", ".join([f"{k} = %s" for k in clean_updates.keys()])
        params = list(clean_updates.values()) + [offering_id, vendor_id]
        self.client.execute(
            f"""
            UPDATE {self._table('core_vendor_offering')}
            SET {set_clause}
            WHERE offering_id = %s
              AND vendor_id = %s
            """,
            tuple(params),
        )
        change_event_id = self._write_audit_entity_change(
            entity_name="core_vendor_offering",
            entity_id=offering_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def map_contract_to_offering(
        self,
        *,
        contract_id: str,
        vendor_id: str,
        offering_id: str | None,
        actor_user_principal: str,
        reason: str,
    ) -> dict[str, str]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        offering_id = self._normalize_offering_id(offering_id)
        contracts = self.get_vendor_contracts(vendor_id)
        target = contracts[contracts["contract_id"].astype(str) == str(contract_id)]
        if target.empty:
            raise ValueError("Contract does not belong to this vendor.")
        if offering_id and not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Selected offering does not belong to this vendor.")

        before = target.iloc[0].to_dict()
        after = dict(before)
        after["offering_id"] = offering_id
        request_id = str(uuid.uuid4())

        if self.config.use_mock:
            self._mock_contract_overrides[contract_id] = {
                **self._mock_contract_overrides.get(contract_id, {}),
                "offering_id": offering_id,
            }
            self._mock_change_request_overrides.append(
                {
                    "change_request_id": request_id,
                    "vendor_id": vendor_id,
                    "requestor_user_principal": actor_user_principal,
                    "change_type": "direct_map_contract_offering",
                    "requested_payload_json": self._serialize_payload({"contract_id": contract_id, "offering_id": offering_id, "reason": reason}),
                    "status": "approved",
                    "submitted_at": self._now().isoformat(),
                    "updated_at": self._now().isoformat(),
                }
            )
            change_event_id = self._write_audit_entity_change(
                entity_name="core_contract",
                entity_id=contract_id,
                action_type="update",
                actor_user_principal=actor_user_principal,
                before_json=before,
                after_json=after,
                request_id=request_id,
            )
            return {"request_id": request_id, "change_event_id": change_event_id}

        self.client.execute(
            f"""
            UPDATE {self._table('core_contract')}
            SET offering_id = %s,
                updated_at = %s,
                updated_by = %s
            WHERE contract_id = %s
              AND vendor_id = %s
            """,
            (offering_id, self._now(), actor_user_principal, contract_id, vendor_id),
        )
        change_event_id = self._write_audit_entity_change(
            entity_name="core_contract",
            entity_id=contract_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def map_demo_to_offering(
        self,
        *,
        demo_id: str,
        vendor_id: str,
        offering_id: str | None,
        actor_user_principal: str,
        reason: str,
    ) -> dict[str, str]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        offering_id = self._normalize_offering_id(offering_id)
        demos = self.get_vendor_demos(vendor_id)
        target = demos[demos["demo_id"].astype(str) == str(demo_id)]
        if target.empty:
            raise ValueError("Demo does not belong to this vendor.")
        if offering_id and not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Selected offering does not belong to this vendor.")

        before = target.iloc[0].to_dict()
        after = dict(before)
        after["offering_id"] = offering_id
        request_id = str(uuid.uuid4())

        if self.config.use_mock:
            self._mock_demo_overrides[demo_id] = {
                **self._mock_demo_overrides.get(demo_id, {}),
                "offering_id": offering_id,
            }
            self._mock_change_request_overrides.append(
                {
                    "change_request_id": request_id,
                    "vendor_id": vendor_id,
                    "requestor_user_principal": actor_user_principal,
                    "change_type": "direct_map_demo_offering",
                    "requested_payload_json": self._serialize_payload({"demo_id": demo_id, "offering_id": offering_id, "reason": reason}),
                    "status": "approved",
                    "submitted_at": self._now().isoformat(),
                    "updated_at": self._now().isoformat(),
                }
            )
            change_event_id = self._write_audit_entity_change(
                entity_name="core_vendor_demo",
                entity_id=demo_id,
                action_type="update",
                actor_user_principal=actor_user_principal,
                before_json=before,
                after_json=after,
                request_id=request_id,
            )
            return {"request_id": request_id, "change_event_id": change_event_id}

        self.client.execute(
            f"""
            UPDATE {self._table('core_vendor_demo')}
            SET offering_id = %s,
                updated_at = %s,
                updated_by = %s
            WHERE demo_id = %s
              AND vendor_id = %s
            """,
            (offering_id, self._now(), actor_user_principal, demo_id, vendor_id),
        )
        change_event_id = self._write_audit_entity_change(
            entity_name="core_vendor_demo",
            entity_id=demo_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def add_offering_owner(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        owner_user_principal: str,
        owner_role: str,
        actor_user_principal: str,
    ) -> str:
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to vendor.")
        if not owner_user_principal.strip():
            raise ValueError("Owner principal is required.")
        owner_id = self._new_id("oown")
        row = {
            "offering_owner_id": owner_id,
            "offering_id": offering_id,
            "owner_user_principal": owner_user_principal.strip(),
            "owner_role": owner_role.strip() or "business_owner",
            "active_flag": True,
        }
        if self.config.use_mock:
            self._mock_new_offering_owners.append(row)
            self._write_audit_entity_change(
                entity_name="core_offering_business_owner",
                entity_id=owner_id,
                action_type="insert",
                actor_user_principal=actor_user_principal,
                before_json=None,
                after_json=row,
                request_id=None,
            )
            return owner_id

        self.client.execute(
            f"""
            INSERT INTO {self._table('core_offering_business_owner')}
              (offering_owner_id, offering_id, owner_user_principal, owner_role, active_flag)
            VALUES
              (%s, %s, %s, %s, %s)
            """,
            (owner_id, offering_id, row["owner_user_principal"], row["owner_role"], True),
        )
        self._write_audit_entity_change(
            entity_name="core_offering_business_owner",
            entity_id=owner_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return owner_id

    def remove_offering_owner(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        offering_owner_id: str,
        actor_user_principal: str,
    ) -> None:
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to vendor.")
        if self.config.use_mock:
            self._mock_removed_offering_owner_ids.add(str(offering_owner_id))
            self._write_audit_entity_change(
                entity_name="core_offering_business_owner",
                entity_id=str(offering_owner_id),
                action_type="delete",
                actor_user_principal=actor_user_principal,
                before_json=None,
                after_json=None,
                request_id=None,
            )
            return
        try:
            self.client.execute(
                f"""
                UPDATE {self._table('core_offering_business_owner')}
                SET active_flag = false
                WHERE offering_owner_id = %s
                  AND offering_id = %s
                """,
                (offering_owner_id, offering_id),
            )
        except Exception:
            self.client.execute(
                f"""
                DELETE FROM {self._table('core_offering_business_owner')}
                WHERE offering_owner_id = %s
                  AND offering_id = %s
                """,
                (offering_owner_id, offering_id),
            )
        self._write_audit_entity_change(
            entity_name="core_offering_business_owner",
            entity_id=str(offering_owner_id),
            action_type="delete",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=None,
            request_id=None,
        )

    def add_offering_contact(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        full_name: str,
        contact_type: str,
        email: str | None,
        phone: str | None,
        actor_user_principal: str,
    ) -> str:
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to vendor.")
        if not full_name.strip():
            raise ValueError("Contact name is required.")
        contact_id = self._new_id("ocon")
        row = {
            "offering_contact_id": contact_id,
            "offering_id": offering_id,
            "contact_type": contact_type.strip() or "business",
            "full_name": full_name.strip(),
            "email": (email or "").strip() or None,
            "phone": (phone or "").strip() or None,
            "active_flag": True,
        }
        if self.config.use_mock:
            self._mock_new_offering_contacts.append(row)
            self._write_audit_entity_change(
                entity_name="core_offering_contact",
                entity_id=contact_id,
                action_type="insert",
                actor_user_principal=actor_user_principal,
                before_json=None,
                after_json=row,
                request_id=None,
            )
            return contact_id

        self.client.execute(
            f"""
            INSERT INTO {self._table('core_offering_contact')}
              (offering_contact_id, offering_id, contact_type, full_name, email, phone, active_flag)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s)
            """,
            (contact_id, offering_id, row["contact_type"], row["full_name"], row["email"], row["phone"], True),
        )
        self._write_audit_entity_change(
            entity_name="core_offering_contact",
            entity_id=contact_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return contact_id

    def remove_offering_contact(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        offering_contact_id: str,
        actor_user_principal: str,
    ) -> None:
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to vendor.")
        if self.config.use_mock:
            self._mock_removed_offering_contact_ids.add(str(offering_contact_id))
            self._write_audit_entity_change(
                entity_name="core_offering_contact",
                entity_id=str(offering_contact_id),
                action_type="delete",
                actor_user_principal=actor_user_principal,
                before_json=None,
                after_json=None,
                request_id=None,
            )
            return
        try:
            self.client.execute(
                f"""
                UPDATE {self._table('core_offering_contact')}
                SET active_flag = false
                WHERE offering_contact_id = %s
                  AND offering_id = %s
                """,
                (offering_contact_id, offering_id),
            )
        except Exception:
            self.client.execute(
                f"""
                DELETE FROM {self._table('core_offering_contact')}
                WHERE offering_contact_id = %s
                  AND offering_id = %s
                """,
                (offering_contact_id, offering_id),
            )
        self._write_audit_entity_change(
            entity_name="core_offering_contact",
            entity_id=str(offering_contact_id),
            action_type="delete",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=None,
            request_id=None,
        )

    def _project_vendor_ids(self, project_id: str) -> list[str]:
        if not project_id:
            return []
        if self.config.use_mock:
            maps = self._mock_project_vendor_map_df()
            matched = maps[maps["project_id"].astype(str) == str(project_id)]
            if matched.empty:
                return []
            return sorted(matched["vendor_id"].astype(str).dropna().unique().tolist())

        map_rows = self._query_or_empty(
            f"""
            SELECT DISTINCT vendor_id
            FROM {self._table('app_project_vendor_map')}
            WHERE project_id = %s
              AND coalesce(active_flag, true) = true
            """,
            params=(project_id,),
            columns=["vendor_id"],
        )
        if not map_rows.empty and "vendor_id" in map_rows.columns:
            return sorted(map_rows["vendor_id"].astype(str).dropna().unique().tolist())

        # Backward compatibility: if mapping table has no rows, fall back to primary vendor_id on app_project.
        fallback = self._query_or_empty(
            f"""
            SELECT vendor_id
            FROM {self._table('app_project')}
            WHERE project_id = %s
              AND coalesce(active_flag, true) = true
            LIMIT 1
            """,
            params=(project_id,),
            columns=["vendor_id"],
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
        if self.config.use_mock:
            projects = self._mock_projects_df().copy()
            if projects.empty:
                return pd.DataFrame(
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
                    ]
                )
            map_df = self._mock_project_vendor_map_df()
            if map_df.empty:
                projects = projects[projects["vendor_id"].astype(str) == str(vendor_id)].copy()
            else:
                project_ids = (
                    map_df[map_df["vendor_id"].astype(str) == str(vendor_id)]["project_id"].astype(str).tolist()
                )
                projects = projects[projects["project_id"].astype(str).isin(project_ids)].copy()
            demos = self._mock_project_demos_df()
            for idx, row in projects.iterrows():
                pid = str(row.get("project_id"))
                project_demos = demos[demos["project_id"].astype(str) == pid]
                projects.loc[idx, "demo_count"] = int(len(project_demos))
                last_activity = str(row.get("updated_at") or row.get("created_at") or "")
                if not project_demos.empty:
                    demo_latest = (
                        project_demos["updated_at"]
                        if "updated_at" in project_demos.columns
                        else project_demos["created_at"]
                    )
                    if not demo_latest.empty:
                        demo_latest_text = str(demo_latest.astype(str).max())
                        if demo_latest_text and demo_latest_text > last_activity:
                            last_activity = demo_latest_text
                projects.loc[idx, "last_activity_at"] = last_activity
            projects["demo_count"] = projects["demo_count"].fillna(0).astype(int)
            return projects.sort_values(["status", "project_name"], ascending=[True, True])

        return self._query_or_empty(
            f"""
            SELECT
              p.project_id,
              p.vendor_id,
              p.project_name,
              p.project_type,
              p.status,
              p.start_date,
              p.target_date,
              p.owner_principal,
              p.description,
              p.updated_at,
              COALESCE(d.demo_count, 0) AS demo_count,
              CASE
                WHEN d.last_demo_at IS NOT NULL AND d.last_demo_at > p.updated_at THEN d.last_demo_at
                ELSE p.updated_at
              END AS last_activity_at
            FROM {self._table('app_project')} p
            LEFT JOIN (
              SELECT project_id, COUNT(*) AS demo_count, MAX(updated_at) AS last_demo_at
              FROM {self._table('app_project_demo')}
              WHERE coalesce(active_flag, true) = true
              GROUP BY project_id
            ) d
              ON p.project_id = d.project_id
            WHERE (
              p.project_id IN (
                SELECT project_id
                FROM {self._table('app_project_vendor_map')}
                WHERE vendor_id = %s
                  AND coalesce(active_flag, true) = true
              )
              OR p.vendor_id = %s
            )
              AND coalesce(p.active_flag, true) = true
            ORDER BY p.status, p.project_name
            """,
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
        if self.config.use_mock:
            projects = self._mock_projects_df().copy()
            vendors = self._mock_vendors_df()[["vendor_id", "display_name", "legal_name"]].copy()
            demos = self._mock_project_demos_df().copy()
            project_vendor_map = self._mock_project_vendor_map_df().copy()

            if vendor_id != "all":
                if not project_vendor_map.empty:
                    project_ids = (
                        project_vendor_map[project_vendor_map["vendor_id"].astype(str) == str(vendor_id)]["project_id"]
                        .astype(str)
                        .tolist()
                    )
                    projects = projects[projects["project_id"].astype(str).isin(project_ids)].copy()
                else:
                    projects = projects[projects["vendor_id"].astype(str) == str(vendor_id)].copy()
            if status != "all" and "status" in projects.columns:
                projects = projects[projects["status"].astype(str).str.lower() == str(status).lower()].copy()
            if search_text.strip():
                needle = search_text.strip().lower()
                projects = projects[
                    projects.apply(
                        lambda r: any(
                            self._matches_needle(r.get(field), needle)
                            for field in [
                                "project_id",
                                "project_name",
                                "project_type",
                                "status",
                                "owner_principal",
                                "description",
                                "vendor_id",
                            ]
                        ),
                        axis=1,
                    )
                ].copy()

            merged = projects.merge(vendors, on="vendor_id", how="left")
            if not demos.empty:
                summary = (
                    demos.groupby("project_id", as_index=False)
                    .agg(demo_count=("project_demo_id", "count"), last_activity_at=("updated_at", "max"))
                )
                merged = merged.merge(summary, on="project_id", how="left")
            else:
                merged["demo_count"] = 0
                merged["last_activity_at"] = merged.get("updated_at")

            merged["vendor_display_name"] = merged["display_name"].fillna(merged["legal_name"]).fillna(merged["vendor_id"])
            merged["demo_count"] = merged.get("demo_count", 0).fillna(0).astype(int)
            if "last_activity_at" not in merged.columns:
                merged["last_activity_at"] = merged.get("updated_at")
            return merged.sort_values(["status", "project_name"], ascending=[True, True]).head(limit)

        params: list[Any] = []
        where_parts = ["coalesce(p.active_flag, true) = true"]
        if vendor_id != "all":
            where_parts.append(
                "("
                "p.project_id IN ("
                f"SELECT project_id FROM {self._table('app_project_vendor_map')} "
                "WHERE vendor_id = %s AND coalesce(active_flag, true) = true)"
                " OR p.vendor_id = %s"
                ")"
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
                " OR lower(coalesce(p.description, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.display_name, '')) LIKE lower(%s)"
                ")"
            )
            like = f"%{search_text.strip()}%"
            params.extend([like, like, like, like, like, like])

        where_clause = " AND ".join(where_parts)
        return self._query_or_empty(
            f"""
            SELECT
              p.project_id,
              p.vendor_id,
              coalesce(v.display_name, v.legal_name, p.vendor_id) AS vendor_display_name,
              p.project_name,
              p.project_type,
              p.status,
              p.start_date,
              p.target_date,
              p.owner_principal,
              p.description,
              p.updated_at,
              COALESCE(d.demo_count, 0) AS demo_count,
              CASE
                WHEN d.last_demo_at IS NOT NULL AND d.last_demo_at > p.updated_at THEN d.last_demo_at
                ELSE p.updated_at
              END AS last_activity_at
            FROM {self._table('app_project')} p
            LEFT JOIN {self._table('core_vendor')} v
              ON p.vendor_id = v.vendor_id
            LEFT JOIN (
              SELECT project_id, COUNT(*) AS demo_count, MAX(updated_at) AS last_demo_at
              FROM {self._table('app_project_demo')}
              WHERE coalesce(active_flag, true) = true
              GROUP BY project_id
            ) d
              ON p.project_id = d.project_id
            WHERE {where_clause}
            ORDER BY p.status, p.project_name
            LIMIT {limit}
            """,
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
        if self.config.use_mock:
            rows = self.list_all_projects(search_text="", status="all", vendor_id="all")
            matched = rows[rows["project_id"].astype(str) == str(project_id)]
            if matched.empty:
                return None
            row = matched.iloc[0].to_dict()
            linked = self.list_project_offerings(None, str(project_id))
            row["linked_offering_ids"] = (
                linked["offering_id"].astype(str).tolist()
                if not linked.empty and "offering_id" in linked.columns
                else []
            )
            row["vendor_ids"] = self._project_vendor_ids(str(project_id))
            return row

        rows = self._query_or_empty(
            f"""
            SELECT
              p.project_id,
              p.vendor_id,
              coalesce(v.display_name, v.legal_name, p.vendor_id) AS vendor_display_name,
              p.project_name,
              p.project_type,
              p.status,
              p.start_date,
              p.target_date,
              p.owner_principal,
              p.description,
              p.updated_at,
              p.created_at,
              p.created_by,
              p.updated_by
            FROM {self._table('app_project')} p
            LEFT JOIN {self._table('core_vendor')} v
              ON p.vendor_id = v.vendor_id
            WHERE p.project_id = %s
              AND coalesce(p.active_flag, true) = true
            LIMIT 1
            """,
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
        if self.config.use_mock:
            offerings = self._mock_offerings_df().copy()
            if offerings.empty:
                return offerings
            maps = self._mock_project_offering_map_df()
            map_rows = maps[maps["project_id"].astype(str) == str(project_id)]
            ids = set(map_rows["offering_id"].astype(str).tolist()) if not map_rows.empty else set()
            if not ids:
                return pd.DataFrame(columns=offerings.columns)
            out = offerings[offerings["offering_id"].astype(str).isin(ids)].copy()
            if vendor_id:
                out = out[out["vendor_id"].astype(str) == str(vendor_id)].copy()
            return out

        vendor_clause = "AND m.vendor_id = %s" if vendor_id else ""
        params: tuple[Any, ...] = (project_id, vendor_id) if vendor_id else (project_id,)
        return self._query_or_empty(
            f"""
            SELECT
              o.offering_id,
              o.vendor_id,
              o.offering_name,
              o.offering_type,
              o.lifecycle_state,
              o.criticality_tier
            FROM {self._table('app_project_offering_map')} m
            INNER JOIN {self._table('core_vendor_offering')} o
              ON m.offering_id = o.offering_id
            WHERE m.project_id = %s
              {vendor_clause}
              AND coalesce(m.active_flag, true) = true
            ORDER BY o.offering_name
            """,
            params=params,
            columns=[
                "offering_id",
                "vendor_id",
                "offering_name",
                "offering_type",
                "lifecycle_state",
                "criticality_tier",
            ],
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
        if self.config.use_mock:
            offerings = self._mock_offerings_df()
        else:
            offerings = self._query_or_empty(
                f"SELECT offering_id, vendor_id FROM {self._table('core_vendor_offering')}",
                columns=["offering_id", "vendor_id"],
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
        primary_vendor_id = normalized_vendor_ids[0] if normalized_vendor_ids else None
        row = {
            "project_id": project_id,
            "vendor_id": primary_vendor_id,
            "project_name": clean_name,
            "project_type": (project_type or "").strip() or "other",
            "status": (status or "draft").strip() or "draft",
            "start_date": (start_date or "").strip() or None,
            "target_date": (target_date or "").strip() or None,
            "owner_principal": (owner_principal or "").strip() or None,
            "description": (description or "").strip() or None,
            "active_flag": True,
            "created_at": now.isoformat(),
            "created_by": actor_user_principal,
            "updated_at": now.isoformat(),
            "updated_by": actor_user_principal,
        }

        if self.config.use_mock:
            self._mock_new_projects.append(row)
            self._mock_project_vendor_overrides[project_id] = normalized_vendor_ids
            self._mock_project_offering_overrides[project_id] = linked_offering_ids
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

        self.client.execute(
            f"""
            INSERT INTO {self._table('app_project')}
              (project_id, vendor_id, project_name, project_type, status, start_date, target_date, owner_principal, description, active_flag, created_at, created_by, updated_at, updated_by)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
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
                actor_user_principal,
                now,
                actor_user_principal,
            ),
        )
        for mapped_vendor_id in normalized_vendor_ids:
            self.client.execute(
                f"""
                INSERT INTO {self._table('app_project_vendor_map')}
                  (project_vendor_map_id, project_id, vendor_id, active_flag, created_at, created_by, updated_at, updated_by)
                VALUES
                  (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    self._new_id("pvm"),
                    project_id,
                    mapped_vendor_id,
                    True,
                    now,
                    actor_user_principal,
                    now,
                    actor_user_principal,
                ),
            )
        for offering_id in linked_offering_ids:
            mapped_vendor_id = offering_vendor_map.get(offering_id) or row["vendor_id"]
            self.client.execute(
                f"""
                INSERT INTO {self._table('app_project_offering_map')}
                  (project_offering_map_id, project_id, vendor_id, offering_id, active_flag, created_at, created_by, updated_at, updated_by)
                VALUES
                  (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    self._new_id("pom"),
                    project_id,
                    mapped_vendor_id,
                    offering_id,
                    True,
                    now,
                    actor_user_principal,
                    now,
                    actor_user_principal,
                ),
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
            if self.config.use_mock:
                offerings = self._mock_offerings_df()
            else:
                offerings = self._query_or_empty(
                    f"SELECT offering_id, vendor_id FROM {self._table('core_vendor_offering')}",
                    columns=["offering_id", "vendor_id"],
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
        if self.config.use_mock:
            self._mock_project_overrides[project_id] = {
                **self._mock_project_overrides.get(project_id, {}),
                **clean_updates,
                "updated_at": now.isoformat(),
                "updated_by": actor_user_principal,
            }
            if target_vendor_ids is not None:
                self._mock_project_vendor_overrides[project_id] = target_vendor_ids
            if target_offering_ids is not None:
                self._mock_project_offering_overrides[project_id] = target_offering_ids
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

        if target_vendor_ids is not None:
            clean_updates["vendor_id"] = target_vendor_ids[0] if target_vendor_ids else None

        if clean_updates:
            set_clause = ", ".join([f"{key} = %s" for key in clean_updates.keys()])
            params = list(clean_updates.values()) + [now, actor_user_principal, project_id]
            self.client.execute(
                f"""
                UPDATE {self._table('app_project')}
                SET {set_clause},
                    updated_at = %s,
                    updated_by = %s
                WHERE project_id = %s
                """,
                tuple(params),
            )
        if target_vendor_ids is not None:
            try:
                self.client.execute(
                    f"""
                    UPDATE {self._table('app_project_vendor_map')}
                    SET active_flag = false,
                        updated_at = %s,
                        updated_by = %s
                    WHERE project_id = %s
                    """,
                    (now, actor_user_principal, project_id),
                )
            except Exception:
                self.client.execute(
                    f"""
                    DELETE FROM {self._table('app_project_vendor_map')}
                    WHERE project_id = %s
                    """,
                    (project_id,),
                )
            for mapped_vendor_id in target_vendor_ids:
                self.client.execute(
                    f"""
                    INSERT INTO {self._table('app_project_vendor_map')}
                      (project_vendor_map_id, project_id, vendor_id, active_flag, created_at, created_by, updated_at, updated_by)
                    VALUES
                      (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        self._new_id("pvm"),
                        project_id,
                        mapped_vendor_id,
                        True,
                        now,
                        actor_user_principal,
                        now,
                        actor_user_principal,
                    ),
                )
        if target_offering_ids is not None:
            try:
                self.client.execute(
                    f"""
                    UPDATE {self._table('app_project_offering_map')}
                    SET active_flag = false,
                        updated_at = %s,
                        updated_by = %s
                    WHERE project_id = %s
                    """,
                    (now, actor_user_principal, project_id),
                )
            except Exception:
                self.client.execute(
                    f"""
                    DELETE FROM {self._table('app_project_offering_map')}
                    WHERE project_id = %s
                    """,
                    (project_id,),
                )
            if self.config.use_mock:
                offerings = self._mock_offerings_df()
            else:
                offerings = self._query_or_empty(
                    f"SELECT offering_id, vendor_id FROM {self._table('core_vendor_offering')}",
                    columns=["offering_id", "vendor_id"],
                )
            offering_vendor_map = (
                {str(r["offering_id"]): str(r["vendor_id"]) for r in offerings.to_dict("records")}
                if not offerings.empty
                else {}
            )
            for offering_id in target_offering_ids:
                mapped_vendor_id = offering_vendor_map.get(offering_id) or str(current.get("vendor_id") or "")
                self.client.execute(
                    f"""
                    INSERT INTO {self._table('app_project_offering_map')}
                      (project_offering_map_id, project_id, vendor_id, offering_id, active_flag, created_at, created_by, updated_at, updated_by)
                    VALUES
                      (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        self._new_id("pom"),
                        project_id,
                        mapped_vendor_id,
                        offering_id,
                        True,
                        now,
                        actor_user_principal,
                        now,
                        actor_user_principal,
                    ),
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
        if self.config.use_mock:
            demos = self._mock_project_demos_df()
            if demos.empty:
                return demos
            demos = demos[demos["project_id"].astype(str) == str(project_id)].copy()
            if vendor_id:
                demos = demos[demos["vendor_id"].astype(str) == str(vendor_id)].copy()
            if "updated_at" in demos.columns:
                demos = demos.sort_values("updated_at", ascending=False)
            return demos
        vendor_clause = "AND vendor_id = %s" if vendor_id else ""
        params: tuple[Any, ...] = (project_id, vendor_id) if vendor_id else (project_id,)
        return self._query_or_empty(
            f"""
            SELECT
              project_demo_id,
              project_id,
              vendor_id,
              demo_name,
              demo_datetime_start,
              demo_datetime_end,
              demo_type,
              outcome,
              score,
              attendees_internal,
              attendees_vendor,
              notes,
              followups,
              linked_offering_id,
              linked_vendor_demo_id,
              created_at,
              created_by,
              updated_at,
              updated_by
            FROM {self._table('app_project_demo')}
            WHERE project_id = %s
              {vendor_clause}
              AND coalesce(active_flag, true) = true
            ORDER BY updated_at DESC
            """,
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
        )

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
            "created_by": actor_user_principal,
            "updated_at": now.isoformat(),
            "updated_by": actor_user_principal,
        }
        if self.config.use_mock:
            self._mock_new_project_demos.append(row)
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

        self.client.execute(
            f"""
            INSERT INTO {self._table('app_project_demo')}
              (project_demo_id, project_id, vendor_id, demo_name, demo_datetime_start, demo_datetime_end, demo_type, outcome, score, attendees_internal, attendees_vendor, notes, followups, linked_offering_id, linked_vendor_demo_id, active_flag, created_at, created_by, updated_at, updated_by)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
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
                actor_user_principal,
                now,
                actor_user_principal,
            ),
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
        if self.config.use_mock:
            self._mock_project_demo_overrides[project_demo_id] = {
                **self._mock_project_demo_overrides.get(project_demo_id, {}),
                **clean_updates,
                "updated_at": now.isoformat(),
                "updated_by": actor_user_principal,
            }
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

        set_clause = ", ".join([f"{k} = %s" for k in clean_updates.keys()])
        params = list(clean_updates.values()) + [now, actor_user_principal, project_demo_id, project_id, vendor_id]
        self.client.execute(
            f"""
            UPDATE {self._table('app_project_demo')}
            SET {set_clause},
                updated_at = %s,
                updated_by = %s
            WHERE project_demo_id = %s
              AND project_id = %s
              AND vendor_id = %s
            """,
            tuple(params),
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
        if self.config.use_mock:
            self._mock_removed_project_demo_ids.add(str(project_demo_id))
            self._write_audit_entity_change(
                entity_name="app_project_demo",
                entity_id=project_demo_id,
                action_type="delete",
                actor_user_principal=actor_user_principal,
                before_json=current,
                after_json=None,
                request_id=None,
            )
            return
        try:
            self.client.execute(
                f"""
                UPDATE {self._table('app_project_demo')}
                SET active_flag = false,
                    updated_at = %s,
                    updated_by = %s
                WHERE project_demo_id = %s
                  AND project_id = %s
                  AND vendor_id = %s
                """,
                (self._now(), actor_user_principal, project_demo_id, project_id, vendor_id),
            )
        except Exception:
            self.client.execute(
                f"""
                DELETE FROM {self._table('app_project_demo')}
                WHERE project_demo_id = %s
                  AND project_id = %s
                  AND vendor_id = %s
                """,
                (project_demo_id, project_id, vendor_id),
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
        if self.config.use_mock:
            notes = self._mock_project_notes_df()
            if notes.empty:
                return notes
            notes = notes[notes["project_id"].astype(str) == str(project_id)].copy()
            if vendor_id:
                notes = notes[notes["vendor_id"].astype(str) == str(vendor_id)].copy()
            if "created_at" in notes.columns:
                notes = notes.sort_values("created_at", ascending=False)
            return notes
        vendor_clause = "AND vendor_id = %s" if vendor_id else ""
        params: tuple[Any, ...] = (project_id, vendor_id) if vendor_id else (project_id,)
        return self._query_or_empty(
            f"""
            SELECT
              project_note_id,
              project_id,
              vendor_id,
              note_text,
              created_at,
              created_by,
              updated_at,
              updated_by
            FROM {self._table('app_project_note')}
            WHERE project_id = %s
              {vendor_clause}
              AND coalesce(active_flag, true) = true
            ORDER BY created_at DESC
            """,
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
        )

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
        row = {
            "project_note_id": note_id,
            "project_id": project_id,
            "vendor_id": effective_vendor_id,
            "note_text": clean_note,
            "active_flag": True,
            "created_at": now.isoformat(),
            "created_by": actor_user_principal,
            "updated_at": now.isoformat(),
            "updated_by": actor_user_principal,
        }
        if self.config.use_mock:
            self._mock_new_project_notes.append(row)
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

        self.client.execute(
            f"""
            INSERT INTO {self._table('app_project_note')}
              (project_note_id, project_id, vendor_id, note_text, active_flag, created_at, created_by, updated_at, updated_by)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                note_id,
                project_id,
                effective_vendor_id,
                clean_note,
                True,
                now,
                actor_user_principal,
                now,
                actor_user_principal,
            ),
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
        if self.config.use_mock:
            events = self._mock_audit_changes_df().copy()
            project_demos = self.list_project_demos(vendor_id, project_id)
            demo_ids = (
                project_demos["project_demo_id"].astype(str).tolist()
                if not project_demos.empty and "project_demo_id" in project_demos.columns
                else []
            )
            doc_rows = self.list_docs("project", project_id)
            doc_ids = doc_rows["doc_id"].astype(str).tolist() if not doc_rows.empty and "doc_id" in doc_rows else []
            note_rows = self.list_project_notes(vendor_id, project_id)
            note_ids = (
                note_rows["project_note_id"].astype(str).tolist()
                if not note_rows.empty and "project_note_id" in note_rows.columns
                else []
            )
            ids = {str(project_id), *demo_ids, *doc_ids, *note_ids}
            filtered = events[events["entity_id"].astype(str).isin(ids)].copy()
            if "event_ts" in filtered.columns:
                filtered = filtered.sort_values("event_ts", ascending=False)
            return filtered

        return self._query_or_empty(
            f"""
            SELECT change_event_id, entity_name, entity_id, action_type, event_ts, actor_user_principal, request_id
            FROM {self._table('audit_entity_change')}
            WHERE entity_id = %s
            OR entity_id IN (
                    SELECT project_demo_id
                    FROM {self._table('app_project_demo')}
                    WHERE project_id = %s
                      AND (%s IS NULL OR vendor_id = %s)
               )
               OR entity_id IN (
                    SELECT doc_id
                    FROM {self._table('app_document_link')}
                    WHERE entity_type = 'project'
                      AND entity_id = %s
               )
            OR entity_id IN (
                    SELECT project_note_id
                    FROM {self._table('app_project_note')}
                    WHERE project_id = %s
                      AND (%s IS NULL OR vendor_id = %s)
               )
            ORDER BY event_ts DESC
            LIMIT 500
            """,
            params=(project_id, project_id, vendor_id, vendor_id, project_id, project_id, vendor_id, vendor_id),
            columns=[
                "change_event_id",
                "entity_name",
                "entity_id",
                "action_type",
                "event_ts",
                "actor_user_principal",
                "request_id",
            ],
        )

    def get_doc_link(self, doc_id: str) -> dict[str, Any] | None:
        if self.config.use_mock:
            docs = self._mock_doc_links_df()
            matched = docs[docs["doc_id"].astype(str) == str(doc_id)]
            if matched.empty:
                return None
            return matched.iloc[0].to_dict()
        rows = self._query_or_empty(
            f"""
            SELECT doc_id, entity_type, entity_id, doc_title, doc_url, doc_type, tags, owner, active_flag, created_at, created_by, updated_at, updated_by
            FROM {self._table('app_document_link')}
            WHERE doc_id = %s
            LIMIT 1
            """,
            params=(doc_id,),
            columns=[
                "doc_id",
                "entity_type",
                "entity_id",
                "doc_title",
                "doc_url",
                "doc_type",
                "tags",
                "owner",
                "active_flag",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ],
        )
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def list_docs(self, entity_type: str, entity_id: str) -> pd.DataFrame:
        allowed = {"vendor", "project", "offering", "demo"}
        if entity_type not in allowed:
            return pd.DataFrame(
                columns=[
                    "doc_id",
                    "entity_type",
                    "entity_id",
                    "doc_title",
                    "doc_url",
                    "doc_type",
                    "tags",
                    "owner",
                    "created_at",
                    "created_by",
                    "updated_at",
                    "updated_by",
                ]
            )
        if self.config.use_mock:
            docs = self._mock_doc_links_df()
            docs = docs[
                (docs["entity_type"].astype(str) == str(entity_type))
                & (docs["entity_id"].astype(str) == str(entity_id))
            ].copy()
            if "updated_at" in docs.columns:
                docs = docs.sort_values("updated_at", ascending=False)
            return docs
        return self._query_or_empty(
            f"""
            SELECT doc_id, entity_type, entity_id, doc_title, doc_url, doc_type, tags, owner, created_at, created_by, updated_at, updated_by
            FROM {self._table('app_document_link')}
            WHERE entity_type = %s
              AND entity_id = %s
              AND coalesce(active_flag, true) = true
            ORDER BY updated_at DESC
            """,
            params=(entity_type, entity_id),
            columns=[
                "doc_id",
                "entity_type",
                "entity_id",
                "doc_title",
                "doc_url",
                "doc_type",
                "tags",
                "owner",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ],
        )

    def create_doc_link(
        self,
        *,
        entity_type: str,
        entity_id: str,
        doc_title: str,
        doc_url: str,
        doc_type: str,
        tags: str | None,
        owner: str | None,
        actor_user_principal: str,
    ) -> str:
        allowed = {"vendor", "project", "offering", "demo"}
        if entity_type not in allowed:
            raise ValueError("Unsupported document entity type.")
        clean_title = (doc_title or "").strip()
        clean_url = (doc_url or "").strip()
        clean_type = (doc_type or "").strip()
        if not clean_title:
            raise ValueError("Document title is required.")
        if not clean_url:
            raise ValueError("Document URL is required.")
        if not clean_type:
            raise ValueError("Document type is required.")

        doc_id = self._new_id("doc")
        now = self._now()
        row = {
            "doc_id": doc_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "doc_title": clean_title,
            "doc_url": clean_url,
            "doc_type": clean_type,
            "tags": (tags or "").strip() or None,
            "owner": (owner or "").strip() or None,
            "active_flag": True,
            "created_at": now.isoformat(),
            "created_by": actor_user_principal,
            "updated_at": now.isoformat(),
            "updated_by": actor_user_principal,
        }
        if self.config.use_mock:
            self._mock_new_doc_links.append(row)
            self._write_audit_entity_change(
                entity_name="app_document_link",
                entity_id=doc_id,
                action_type="insert",
                actor_user_principal=actor_user_principal,
                before_json=None,
                after_json=row,
                request_id=None,
            )
            return doc_id

        self.client.execute(
            f"""
            INSERT INTO {self._table('app_document_link')}
              (doc_id, entity_type, entity_id, doc_title, doc_url, doc_type, tags, owner, active_flag, created_at, created_by, updated_at, updated_by)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                doc_id,
                entity_type,
                entity_id,
                clean_title,
                clean_url,
                clean_type,
                row["tags"],
                row["owner"],
                True,
                now,
                actor_user_principal,
                now,
                actor_user_principal,
            ),
        )
        self._write_audit_entity_change(
            entity_name="app_document_link",
            entity_id=doc_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return doc_id

    def update_doc_link(self, *, doc_id: str, actor_user_principal: str, updates: dict[str, Any], reason: str) -> dict[str, str]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        current = self.get_doc_link(doc_id)
        if current is None:
            raise ValueError("Document link not found.")
        allowed = {"doc_title", "doc_url", "doc_type", "tags", "owner"}
        clean_updates = {k: v for k, v in updates.items() if k in allowed}
        if not clean_updates:
            raise ValueError("No updates were provided.")
        before = dict(current)
        after = dict(current)
        after.update(clean_updates)
        request_id = str(uuid.uuid4())
        now = self._now()
        if self.config.use_mock:
            self._mock_doc_link_overrides[doc_id] = {
                **self._mock_doc_link_overrides.get(doc_id, {}),
                **clean_updates,
                "updated_at": now.isoformat(),
                "updated_by": actor_user_principal,
            }
            change_event_id = self._write_audit_entity_change(
                entity_name="app_document_link",
                entity_id=doc_id,
                action_type="update",
                actor_user_principal=actor_user_principal,
                before_json=before,
                after_json=after,
                request_id=request_id,
            )
            return {"request_id": request_id, "change_event_id": change_event_id}

        set_clause = ", ".join([f"{k} = %s" for k in clean_updates.keys()])
        params = list(clean_updates.values()) + [now, actor_user_principal, doc_id]
        self.client.execute(
            f"""
            UPDATE {self._table('app_document_link')}
            SET {set_clause},
                updated_at = %s,
                updated_by = %s
            WHERE doc_id = %s
            """,
            tuple(params),
        )
        change_event_id = self._write_audit_entity_change(
            entity_name="app_document_link",
            entity_id=doc_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def remove_doc_link(self, *, doc_id: str, actor_user_principal: str) -> None:
        current = self.get_doc_link(doc_id)
        if current is None:
            raise ValueError("Document link not found.")
        if self.config.use_mock:
            self._mock_removed_doc_link_ids.add(str(doc_id))
            self._write_audit_entity_change(
                entity_name="app_document_link",
                entity_id=doc_id,
                action_type="delete",
                actor_user_principal=actor_user_principal,
                before_json=current,
                after_json=None,
                request_id=None,
            )
            return
        try:
            self.client.execute(
                f"""
                UPDATE {self._table('app_document_link')}
                SET active_flag = false,
                    updated_at = %s,
                    updated_by = %s
                WHERE doc_id = %s
                """,
                (self._now(), actor_user_principal, doc_id),
            )
        except Exception:
            self.client.execute(
                f"""
                DELETE FROM {self._table('app_document_link')}
                WHERE doc_id = %s
                """,
                (doc_id,),
            )
        self._write_audit_entity_change(
            entity_name="app_document_link",
            entity_id=doc_id,
            action_type="delete",
            actor_user_principal=actor_user_principal,
            before_json=current,
            after_json=None,
            request_id=None,
        )

    def create_vendor_change_request(
        self, vendor_id: str, requestor_user_principal: str, change_type: str, payload: dict
    ) -> str:
        request_id = str(uuid.uuid4())
        now = self._now()

        if self.config.use_mock:
            self._mock_change_request_overrides.append(
                {
                    "change_request_id": request_id,
                    "vendor_id": vendor_id,
                    "requestor_user_principal": requestor_user_principal,
                    "change_type": change_type,
                    "requested_payload_json": self._serialize_payload(payload),
                    "status": "submitted",
                    "submitted_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            )
            self._mock_audit_change_overrides.append(
                {
                    "change_event_id": str(uuid.uuid4()),
                    "entity_name": "app_vendor_change_request",
                    "entity_id": request_id,
                    "action_type": "insert",
                    "event_ts": now.isoformat(),
                    "actor_user_principal": requestor_user_principal,
                    "request_id": request_id,
                }
            )
            return request_id

        try:
            self.client.execute(
                f"""
                INSERT INTO {self._table('app_vendor_change_request')}
                  (change_request_id, vendor_id, requestor_user_principal, change_type, requested_payload_json, status, submitted_at, updated_at)
                VALUES
                  (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    request_id,
                    vendor_id,
                    requestor_user_principal,
                    change_type,
                    json.dumps(payload),
                    "submitted",
                    now,
                    now,
                ),
            )
        except Exception:
            return request_id

        try:
            self.client.execute(
                f"""
                INSERT INTO {self._table('audit_workflow_event')}
                  (workflow_event_id, workflow_type, workflow_id, old_status, new_status, actor_user_principal, event_ts, notes)
                VALUES
                  (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    "vendor_change_request",
                    request_id,
                    None,
                    "submitted",
                    requestor_user_principal,
                    now,
                    f"{change_type} request created",
                ),
            )
        except Exception:
            pass

        return request_id

    def apply_vendor_profile_update(
        self,
        vendor_id: str,
        actor_user_principal: str,
        updates: dict[str, Any],
        reason: str,
    ) -> dict[str, str]:
        allowed_fields = {"legal_name", "display_name", "lifecycle_state", "owner_org_id", "risk_tier"}
        clean_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        if not clean_updates:
            raise ValueError("No editable fields were provided.")
        if not reason.strip():
            raise ValueError("A reason is required for audited updates.")

        now = self._now()
        request_id = str(uuid.uuid4())
        change_event_id = str(uuid.uuid4())

        if self.config.use_mock:
            profile = self.get_vendor_profile(vendor_id)
            if profile.empty:
                raise ValueError("Vendor not found.")
            old_row = profile.iloc[0].to_dict()
            new_row = dict(old_row)
            new_row.update(clean_updates)
            new_row["updated_at"] = now.isoformat()
            self._mock_vendor_overrides[vendor_id] = {
                key: value for key, value in new_row.items() if key in old_row.keys()
            }
            self._mock_change_request_overrides.append(
                {
                    "change_request_id": request_id,
                    "vendor_id": vendor_id,
                    "requestor_user_principal": actor_user_principal,
                    "change_type": "direct_update_vendor_profile",
                    "requested_payload_json": self._serialize_payload({"updates": clean_updates, "reason": reason}),
                    "status": "approved",
                    "submitted_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            )
            self._mock_audit_change_overrides.append(
                {
                    "change_event_id": change_event_id,
                    "entity_name": "core_vendor",
                    "entity_id": vendor_id,
                    "action_type": "update",
                    "event_ts": now.isoformat(),
                    "actor_user_principal": actor_user_principal,
                    "request_id": request_id,
                }
            )
            self.log_usage_event(
                user_principal=actor_user_principal,
                page_name="vendor_360",
                event_type="vendor_profile_update_applied",
                payload={"vendor_id": vendor_id, "request_id": request_id, "reason": reason},
            )
            return {"request_id": request_id, "change_event_id": change_event_id}

        existing = self._query_or_empty(
            f"SELECT * FROM {self._table('core_vendor')} WHERE vendor_id = %s LIMIT 1",
            params=(vendor_id,),
            columns=[],
        )
        if existing.empty:
            raise ValueError("Vendor not found.")
        old_row = existing.iloc[0].to_dict()

        # Create and immediately approve a change request so all direct edits remain traceable.
        try:
            self.client.execute(
                f"""
                INSERT INTO {self._table('app_vendor_change_request')}
                  (change_request_id, vendor_id, requestor_user_principal, change_type, requested_payload_json, status, submitted_at, updated_at)
                VALUES
                  (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    request_id,
                    vendor_id,
                    actor_user_principal,
                    "direct_update_vendor_profile",
                    self._serialize_payload({"updates": clean_updates, "reason": reason}),
                    "approved",
                    now,
                    now,
                ),
            )
            self.client.execute(
                f"""
                INSERT INTO {self._table('audit_workflow_event')}
                  (workflow_event_id, workflow_type, workflow_id, old_status, new_status, actor_user_principal, event_ts, notes)
                VALUES
                  (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    "vendor_change_request",
                    request_id,
                    "submitted",
                    "approved",
                    actor_user_principal,
                    now,
                    "Direct vendor profile update approved and applied.",
                ),
            )
        except Exception:
            # Continue to apply update even if app workflow tables are unavailable.
            pass

        set_clause = ", ".join([f"{field} = %s" for field in clean_updates.keys()])
        params = list(clean_updates.values()) + [now, actor_user_principal, vendor_id]
        self.client.execute(
            f"""
            UPDATE {self._table('core_vendor')}
            SET {set_clause},
                updated_at = %s,
                updated_by = %s
            WHERE vendor_id = %s
            """,
            tuple(params),
        )

        updated = self._query_or_empty(
            f"SELECT * FROM {self._table('core_vendor')} WHERE vendor_id = %s LIMIT 1",
            params=(vendor_id,),
            columns=[],
        )
        new_row = updated.iloc[0].to_dict() if not updated.empty else {**old_row, **clean_updates}

        # Maintain SCD-style vendor history.
        try:
            version_df = self._query_or_empty(
                f"""
                SELECT COALESCE(MAX(version_no), 0) + 1 AS next_version
                FROM {self._table('hist_vendor')}
                WHERE vendor_id = %s
                """,
                params=(vendor_id,),
                columns=["next_version"],
            )
            next_version = int(version_df.iloc[0]["next_version"]) if not version_df.empty else 1

            self.client.execute(
                f"""
                UPDATE {self._table('hist_vendor')}
                SET is_current = false,
                    valid_to_ts = %s
                WHERE vendor_id = %s
                  AND is_current = true
                """,
                (now, vendor_id),
            )
            self.client.execute(
                f"""
                INSERT INTO {self._table('hist_vendor')}
                  (vendor_hist_id, vendor_id, version_no, valid_from_ts, valid_to_ts, is_current, snapshot_json, changed_by, change_reason)
                VALUES
                  (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    vendor_id,
                    next_version,
                    now,
                    None,
                    True,
                    json.dumps(new_row, default=str),
                    actor_user_principal,
                    reason,
                ),
            )
        except Exception:
            pass

        try:
            self.client.execute(
                f"""
                INSERT INTO {self._table('audit_entity_change')}
                  (change_event_id, entity_name, entity_id, action_type, before_json, after_json, actor_user_principal, event_ts, request_id)
                VALUES
                  (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    change_event_id,
                    "core_vendor",
                    vendor_id,
                    "update",
                    json.dumps(old_row, default=str),
                    json.dumps(new_row, default=str),
                    actor_user_principal,
                    now,
                    request_id,
                ),
            )
        except Exception:
            pass

        return {"request_id": request_id, "change_event_id": change_event_id}

    def demo_outcomes(self) -> pd.DataFrame:
        if self.config.use_mock:
            return self._mock_demos_df()
        return self.client.query(
            f"""
            SELECT demo_id, vendor_id, offering_id, demo_date, overall_score, selection_outcome, non_selection_reason_code, notes
            FROM {self._table('core_vendor_demo')}
            ORDER BY demo_date DESC
            LIMIT 500
            """
        )

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
        if self.config.use_mock:
            return demo_id

        self.client.execute(
            f"""
            INSERT INTO {self._table('core_vendor_demo')}
              (demo_id, vendor_id, offering_id, demo_date, overall_score, selection_outcome, non_selection_reason_code, notes, updated_at, updated_by)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                demo_id,
                vendor_id,
                offering_id,
                demo_date,
                overall_score,
                selection_outcome,
                non_selection_reason_code,
                notes,
                now,
                actor_user_principal,
            ),
        )

        self.client.execute(
            f"""
            INSERT INTO {self._table('audit_entity_change')}
              (change_event_id, entity_name, entity_id, action_type, before_json, after_json, actor_user_principal, event_ts, request_id)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                "core_vendor_demo",
                demo_id,
                "insert",
                None,
                json.dumps(
                    {
                        "vendor_id": vendor_id,
                        "offering_id": offering_id,
                        "demo_date": demo_date,
                        "overall_score": overall_score,
                        "selection_outcome": selection_outcome,
                        "non_selection_reason_code": non_selection_reason_code,
                        "notes": notes,
                    }
                ),
                actor_user_principal,
                now,
                None,
            ),
        )
        return demo_id

    def contract_cancellations(self) -> pd.DataFrame:
        if self.config.use_mock:
            return mock_data.contract_cancellations()
        return self.client.query(
            f"""
            SELECT contract_id, vendor_id, offering_id, cancelled_at, reason_code, notes
            FROM {self._table('rpt_contract_cancellations')}
            ORDER BY cancelled_at DESC
            LIMIT 500
            """
        )

    def record_contract_cancellation(
        self, contract_id: str, reason_code: str, notes: str, actor_user_principal: str
    ) -> str:
        event_id = str(uuid.uuid4())
        now = self._now()
        if self.config.use_mock:
            return event_id

        self.client.execute(
            f"""
            INSERT INTO {self._table('core_contract_event')}
              (contract_event_id, contract_id, event_type, event_ts, reason_code, notes, actor_user_principal)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s)
            """,
            (event_id, contract_id, "contract_cancelled", now, reason_code, notes, actor_user_principal),
        )

        self.client.execute(
            f"""
            UPDATE {self._table('core_contract')}
            SET contract_status = %s,
                cancelled_flag = %s,
                updated_at = %s,
                updated_by = %s
            WHERE contract_id = %s
            """,
            ("cancelled", True, now, actor_user_principal, contract_id),
        )

        self.client.execute(
            f"""
            INSERT INTO {self._table('audit_entity_change')}
              (change_event_id, entity_name, entity_id, action_type, before_json, after_json, actor_user_principal, event_ts, request_id)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                "core_contract",
                contract_id,
                "update",
                None,
                json.dumps(
                    {
                        "contract_status": "cancelled",
                        "cancelled_flag": True,
                        "reason_code": reason_code,
                        "notes": notes,
                    }
                ),
                actor_user_principal,
                now,
                None,
            ),
        )
        return event_id

    def list_role_grants(self) -> pd.DataFrame:
        if self.config.use_mock:
            return mock_data.role_map()
        return self.client.query(
            f"""
            SELECT user_principal, role_code, active_flag, granted_by, granted_at, revoked_at
            FROM {self._table('sec_user_role_map')}
            ORDER BY granted_at DESC
            LIMIT 1000
            """
        )

    def list_scope_grants(self) -> pd.DataFrame:
        if self.config.use_mock:
            return mock_data.org_scope()
        return self.client.query(
            f"""
            SELECT user_principal, org_id, scope_level, active_flag, granted_at
            FROM {self._table('sec_user_org_scope')}
            ORDER BY granted_at DESC
            LIMIT 1000
            """
        )

    def grant_role(self, target_user_principal: str, role_code: str, granted_by: str) -> None:
        if self.config.use_mock:
            return
        now = self._now()
        self.client.execute(
            f"""
            INSERT INTO {self._table('sec_user_role_map')}
              (user_principal, role_code, active_flag, granted_by, granted_at, revoked_at)
            VALUES
              (%s, %s, %s, %s, %s, %s)
            """,
            (target_user_principal, role_code, True, granted_by, now, None),
        )
        self._audit_access(
            actor_user_principal=granted_by,
            action_type="grant_role",
            target_user_principal=target_user_principal,
            target_role=role_code,
            notes="Role granted through admin UI.",
        )

    def grant_org_scope(
        self, target_user_principal: str, org_id: str, scope_level: str, granted_by: str
    ) -> None:
        if self.config.use_mock:
            return
        now = self._now()
        self.client.execute(
            f"""
            INSERT INTO {self._table('sec_user_org_scope')}
              (user_principal, org_id, scope_level, active_flag, granted_at)
            VALUES
              (%s, %s, %s, %s, %s)
            """,
            (target_user_principal, org_id, scope_level, True, now),
        )
        self._audit_access(
            actor_user_principal=granted_by,
            action_type="grant_scope",
            target_user_principal=target_user_principal,
            target_role=None,
            notes=f"Org scope granted: {org_id} ({scope_level}).",
        )

    def _audit_access(
        self,
        actor_user_principal: str,
        action_type: str,
        target_user_principal: str | None,
        target_role: str | None,
        notes: str,
    ) -> None:
        if self.config.use_mock:
            return
        self.client.execute(
            f"""
            INSERT INTO {self._table('audit_access_event')}
              (access_event_id, actor_user_principal, action_type, target_user_principal, target_role, event_ts, notes)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                actor_user_principal,
                action_type,
                target_user_principal,
                target_role,
                self._now(),
                notes,
            ),
        )
