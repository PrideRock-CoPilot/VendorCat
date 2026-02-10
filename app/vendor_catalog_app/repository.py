from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from vendor_catalog_app.config import AppConfig
from vendor_catalog_app.db import DatabricksSQLClient
from vendor_catalog_app import mock_data
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

UNKNOWN_USER_PRINCIPAL = "unknown_user"
GLOBAL_CHANGE_VENDOR_ID = "__global__"
LOOKUP_TYPE_DOC_SOURCE = "doc_source"
LOOKUP_TYPE_DOC_TAG = "doc_tag"
LOOKUP_TYPE_OWNER_ROLE = "owner_role"
LOOKUP_TYPE_ASSIGNMENT_TYPE = "assignment_type"
LOOKUP_TYPE_CONTACT_TYPE = "contact_type"
LOOKUP_TYPE_PROJECT_TYPE = "project_type"
LOOKUP_TYPE_OFFERING_TYPE = "offering_type"
LOOKUP_TYPE_OFFERING_LOB = "offering_lob"
LOOKUP_TYPE_OFFERING_SERVICE_TYPE = "offering_service_type"
LOOKUP_TYPE_WORKFLOW_STATUS = "workflow_status"
SUPPORTED_LOOKUP_TYPES = {
    LOOKUP_TYPE_DOC_SOURCE,
    LOOKUP_TYPE_DOC_TAG,
    LOOKUP_TYPE_OWNER_ROLE,
    LOOKUP_TYPE_ASSIGNMENT_TYPE,
    LOOKUP_TYPE_CONTACT_TYPE,
    LOOKUP_TYPE_PROJECT_TYPE,
    LOOKUP_TYPE_OFFERING_TYPE,
    LOOKUP_TYPE_OFFERING_LOB,
    LOOKUP_TYPE_OFFERING_SERVICE_TYPE,
    LOOKUP_TYPE_WORKFLOW_STATUS,
}
DEFAULT_DOC_SOURCE_OPTIONS = [
    "sharepoint",
    "onedrive",
    "confluence",
    "google_drive",
    "box",
    "dropbox",
    "github",
    "other",
]
DEFAULT_DOC_TAG_OPTIONS = [
    "contract",
    "msa",
    "nda",
    "sow",
    "invoice",
    "renewal",
    "security",
    "architecture",
    "runbook",
    "compliance",
    "rfp",
    "poc",
    "notes",
    "operations",
    "folder",
]
DEFAULT_OWNER_ROLE_OPTIONS = [
    "business_owner",
    "executive_owner",
    "service_owner",
    "technical_owner",
    "security_owner",
    "application_owner",
    "platform_owner",
    "legacy_owner",
]
DEFAULT_ASSIGNMENT_TYPE_OPTIONS = ["consumer", "primary", "secondary"]
DEFAULT_CONTACT_TYPE_OPTIONS = [
    "business",
    "account_manager",
    "support",
    "escalation",
    "security_specialist",
    "customer_success",
    "product_manager",
]
DEFAULT_PROJECT_TYPE_OPTIONS = ["rfp", "poc", "renewal", "implementation", "other"]
DEFAULT_WORKFLOW_STATUS_OPTIONS = ["submitted", "in_review", "approved", "rejected"]
DEFAULT_OFFERING_TYPE_CHOICES = [
    ("saas", "SaaS"),
    ("cloud", "Cloud"),
    ("paas", "PaaS"),
    ("security", "Security"),
    ("data", "Data"),
    ("integration", "Integration"),
    ("other", "Other"),
]
DEFAULT_OFFERING_LOB_CHOICES = [
    ("enterprise", "Enterprise"),
    ("finance", "Finance"),
    ("hr", "HR"),
    ("it", "IT"),
    ("operations", "Operations"),
    ("sales", "Sales"),
    ("security", "Security"),
]
DEFAULT_OFFERING_SERVICE_TYPE_CHOICES = [
    ("application", "Application"),
    ("infrastructure", "Infrastructure"),
    ("integration", "Integration"),
    ("managed_service", "Managed Service"),
    ("platform", "Platform"),
    ("security", "Security"),
    ("support", "Support"),
    ("other", "Other"),
]


class SchemaBootstrapRequiredError(RuntimeError):
    """Raised when required runtime schema objects are missing or inaccessible."""


class VendorRepository:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.client = DatabricksSQLClient(config)
        self._runtime_tables_ensured = False
        self._local_lookup_table_ensured = False
        self._local_offering_columns_ensured = False
        self._local_offering_extension_tables_ensured = False
        self._mock_role_overrides: dict[str, set[str]] = {}
        self._mock_scope_overrides: list[dict[str, Any]] = []
        self._mock_role_definitions: dict[str, dict[str, Any]] = self._default_role_definition_rows()
        self._mock_role_permissions: dict[str, set[str]] = self._default_role_permissions_by_role()
        self._mock_lookup_options: list[dict[str, Any]] = self._default_lookup_option_rows()
        self._mock_user_directory: dict[str, dict[str, str]] = {}
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
        self._mock_new_vendor_owners: list[dict[str, Any]] = []
        self._mock_removed_vendor_owner_ids: set[str] = set()
        self._mock_new_vendor_contacts: list[dict[str, Any]] = []
        self._mock_removed_vendor_contact_ids: set[str] = set()
        self._mock_new_vendor_org_assignments: list[dict[str, Any]] = []
        self._mock_removed_vendor_org_assignment_ids: set[str] = set()
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
        self._mock_offering_profile_overrides: dict[str, dict[str, Any]] = {}
        self._mock_new_offering_data_flows: list[dict[str, Any]] = []
        self._mock_offering_data_flow_overrides: dict[str, dict[str, Any]] = {}
        self._mock_removed_offering_data_flow_ids: set[str] = set()
        self._mock_new_offering_tickets: list[dict[str, Any]] = []
        self._mock_offering_ticket_overrides: dict[str, dict[str, Any]] = {}
        self._mock_new_offering_notes: list[dict[str, Any]] = []
        self._mock_new_doc_links: list[dict[str, Any]] = []
        self._mock_doc_link_overrides: dict[str, dict[str, Any]] = {}
        self._mock_removed_doc_link_ids: set[str] = set()

    def _table(self, name: str) -> str:
        if self.config.use_local_db:
            return name
        return f"{self.config.fq_schema}.{name}"

    @staticmethod
    @lru_cache(maxsize=512)
    def _read_sql_file(path_str: str) -> str:
        path = Path(path_str)
        if not path.exists():
            raise FileNotFoundError(f"SQL file not found: {path}")
        return path.read_text(encoding="utf-8")

    def _sql(self, relative_path: str, **format_args: Any) -> str:
        sql_root = Path(__file__).resolve().parent / "sql"
        sql_path = (sql_root / relative_path).resolve()
        template = self._read_sql_file(str(sql_path))
        return template.format(**format_args) if format_args else template

    def _query_file(
        self,
        relative_path: str,
        *,
        params: tuple | None = None,
        columns: list[str] | None = None,
        **format_args: Any,
    ) -> pd.DataFrame:
        statement = self._sql(relative_path, **format_args)
        return self._query_or_empty(statement, params=params, columns=columns)

    def _execute_file(
        self,
        relative_path: str,
        *,
        params: tuple | None = None,
        **format_args: Any,
    ) -> None:
        statement = self._sql(relative_path, **format_args)
        self.client.execute(statement, params)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_choice(
        value: str | None,
        *,
        field_name: str,
        allowed: set[str],
        default: str,
    ) -> str:
        normalized = (value or "").strip().lower()
        if not normalized:
            return default
        if normalized not in allowed:
            allowed_text = ", ".join(sorted(allowed))
            raise ValueError(f"{field_name} must be one of: {allowed_text}.")
        return normalized

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

    @staticmethod
    def _vendor_sort_column(sort_by: str) -> str:
        mapping = {
            "vendor_name": "display_name",
            "display_name": "display_name",
            "vendor_id": "vendor_id",
            "legal_name": "legal_name",
            "lifecycle_state": "lifecycle_state",
            "owner_org_id": "owner_org_id",
            "risk_tier": "risk_tier",
            "updated_at": "updated_at",
        }
        return mapping.get((sort_by or "").strip().lower(), "display_name")

    @staticmethod
    def _vendor_sort_expr(sort_by: str) -> str:
        mapping = {
            "vendor_name": "lower(coalesce(v.display_name, v.legal_name, v.vendor_id))",
            "display_name": "lower(coalesce(v.display_name, v.legal_name, v.vendor_id))",
            "vendor_id": "lower(v.vendor_id)",
            "legal_name": "lower(coalesce(v.legal_name, ''))",
            "lifecycle_state": "lower(coalesce(v.lifecycle_state, ''))",
            "owner_org_id": "lower(coalesce(v.owner_org_id, ''))",
            "risk_tier": "lower(coalesce(v.risk_tier, ''))",
            "updated_at": "v.updated_at",
        }
        return mapping.get((sort_by or "").strip().lower(), mapping["vendor_name"])

    def _serialize_payload(self, payload: dict[str, Any] | None) -> str:
        if not payload:
            return "{}"
        return json.dumps(payload)

    @staticmethod
    def _safe_payload_json(payload_json: Any) -> dict[str, Any]:
        if isinstance(payload_json, dict):
            return payload_json
        if not isinstance(payload_json, str):
            return {}
        try:
            parsed = json.loads(payload_json)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _audit_field_label(field_name: str) -> str:
        cleaned = re.sub(r"[_\s]+", " ", str(field_name or "").strip())
        cleaned = cleaned.strip()
        return cleaned.title() if cleaned else "Field"

    @staticmethod
    def _audit_value_for_compare(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, float) and pd.isna(value):
            return None
        if isinstance(value, (dict, list, tuple, set)):
            return json.dumps(value, default=str, sort_keys=True)
        if isinstance(value, str):
            return value.strip()
        return str(value)

    @classmethod
    def _audit_values_equal(cls, left: Any, right: Any) -> bool:
        return cls._audit_value_for_compare(left) == cls._audit_value_for_compare(right)

    @staticmethod
    def _audit_value_text(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, float) and pd.isna(value):
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (dict, list, tuple, set)):
            text = json.dumps(value, default=str, sort_keys=True)
        else:
            text = str(value)
        text = re.sub(r"\s+", " ", text).strip()
        return text if len(text) <= 72 else f"{text[:69]}..."

    def _build_audit_change_summary(
        self,
        *,
        action_type: str,
        before_payload: dict[str, Any],
        after_payload: dict[str, Any],
    ) -> str:
        action = str(action_type or "").strip().lower()
        ignored_fields = {
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "event_ts",
            "last_seen_at",
        }

        changes: list[str] = []
        if action == "insert":
            for key in sorted(after_payload.keys()):
                if key in ignored_fields:
                    continue
                changes.append(f"{self._audit_field_label(key)} = {self._audit_value_text(after_payload.get(key))}")
        elif action == "delete":
            for key in sorted(before_payload.keys()):
                if key in ignored_fields:
                    continue
                changes.append(f"{self._audit_field_label(key)} was {self._audit_value_text(before_payload.get(key))}")
        else:
            for key in sorted(set(before_payload.keys()) | set(after_payload.keys())):
                if key in ignored_fields:
                    continue
                before_value = before_payload.get(key)
                after_value = after_payload.get(key)
                if self._audit_values_equal(before_value, after_value):
                    continue
                changes.append(
                    f"{self._audit_field_label(key)}: {self._audit_value_text(before_value)} -> {self._audit_value_text(after_value)}"
                )

        if not changes:
            if action == "insert":
                return "Created record."
            if action == "delete":
                return "Removed record."
            return "Updated record (field-level details unavailable)."

        visible = changes[:4]
        summary = "; ".join(visible)
        if len(changes) > 4:
            summary = f"{summary}; +{len(changes) - 4} more"
        return summary

    def _with_audit_change_summaries(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            out = df.copy()
            if "change_summary" not in out.columns:
                out["change_summary"] = pd.Series(dtype="object")
            return out

        out = df.copy()
        if "before_json" not in out.columns:
            out["before_json"] = None
        if "after_json" not in out.columns:
            out["after_json"] = None

        summaries: list[str] = []
        for row in out.to_dict("records"):
            before_payload = self._safe_payload_json(row.get("before_json"))
            after_payload = self._safe_payload_json(row.get("after_json"))
            summaries.append(
                self._build_audit_change_summary(
                    action_type=str(row.get("action_type") or ""),
                    before_payload=before_payload,
                    after_payload=after_payload,
                )
            )
        out["change_summary"] = summaries
        return out

    def _prepare_change_request_payload(self, change_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        out = dict(payload or {})
        meta = out.get("_meta") if isinstance(out.get("_meta"), dict) else {}
        required_level = required_approval_level(change_type)
        try:
            required_level = int(meta.get("approval_level_required", required_level))
        except Exception:
            required_level = required_approval_level(change_type)
        required_level = max(1, min(required_level, 3))
        meta["approval_level_required"] = required_level
        meta["workflow_action"] = (change_type or "").strip().lower()
        out["_meta"] = meta
        return out

    @staticmethod
    def _default_role_definition_rows() -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for role_code, payload in default_role_definitions().items():
            out[str(role_code)] = {
                "role_code": str(role_code),
                "role_name": str(payload.get("role_name") or role_code),
                "description": str(payload.get("description") or "").strip() or None,
                "approval_level": int(payload.get("approval_level", 0) or 0),
                "can_edit": bool(payload.get("can_edit")),
                "can_report": bool(payload.get("can_report")),
                "can_direct_apply": bool(payload.get("can_direct_apply")),
                "active_flag": True,
            }
        return out

    @staticmethod
    def _default_role_permissions_by_role() -> dict[str, set[str]]:
        return {role_code: default_change_permissions_for_role(role_code) for role_code in ROLE_CHOICES}

    @staticmethod
    def _lookup_label_from_code(option_code: str) -> str:
        return re.sub(r"\s+", " ", str(option_code or "").replace("_", " ")).strip().title()

    @staticmethod
    def _default_lookup_option_rows() -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        now = datetime(1900, 1, 1, tzinfo=timezone.utc).isoformat()
        open_end = datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc).isoformat()
        groups: dict[str, list[str | tuple[str, str]]] = {
            LOOKUP_TYPE_DOC_SOURCE: DEFAULT_DOC_SOURCE_OPTIONS,
            LOOKUP_TYPE_DOC_TAG: DEFAULT_DOC_TAG_OPTIONS,
            LOOKUP_TYPE_OWNER_ROLE: DEFAULT_OWNER_ROLE_OPTIONS,
            LOOKUP_TYPE_ASSIGNMENT_TYPE: DEFAULT_ASSIGNMENT_TYPE_OPTIONS,
            LOOKUP_TYPE_CONTACT_TYPE: DEFAULT_CONTACT_TYPE_OPTIONS,
            LOOKUP_TYPE_PROJECT_TYPE: DEFAULT_PROJECT_TYPE_OPTIONS,
            LOOKUP_TYPE_WORKFLOW_STATUS: DEFAULT_WORKFLOW_STATUS_OPTIONS,
            LOOKUP_TYPE_OFFERING_TYPE: list(DEFAULT_OFFERING_TYPE_CHOICES),
            LOOKUP_TYPE_OFFERING_LOB: list(DEFAULT_OFFERING_LOB_CHOICES),
            LOOKUP_TYPE_OFFERING_SERVICE_TYPE: list(DEFAULT_OFFERING_SERVICE_TYPE_CHOICES),
        }
        for lookup_type, options in groups.items():
            for sort_order, entry in enumerate(options, start=1):
                if isinstance(entry, tuple):
                    raw_code, raw_label = entry
                else:
                    raw_code, raw_label = entry, None
                normalized_code = str(raw_code).strip().lower()
                if not normalized_code:
                    continue
                label_value = str(raw_label or VendorRepository._lookup_label_from_code(normalized_code)).strip()
                if not label_value:
                    label_value = VendorRepository._lookup_label_from_code(normalized_code)
                rows.append(
                    {
                    "option_id": f"lkp-{lookup_type}-{normalized_code}",
                    "lookup_type": lookup_type,
                    "option_code": normalized_code,
                    "option_label": label_value,
                    "sort_order": sort_order,
                    "active_flag": True,
                    "valid_from_ts": now,
                    "valid_to_ts": open_end,
                    "is_current": True,
                    "deleted_flag": False,
                    "updated_at": None,
                    "updated_by": "bootstrap",
                    }
                )
        return rows

    @staticmethod
    def _normalize_lookup_type(value: str) -> str:
        lookup_type = str(value or "").strip().lower()
        if lookup_type not in SUPPORTED_LOOKUP_TYPES:
            raise ValueError(f"Lookup type must be one of: {', '.join(sorted(SUPPORTED_LOOKUP_TYPES))}")
        return lookup_type

    @staticmethod
    def _normalize_lookup_code(value: str) -> str:
        option_code = re.sub(r"\s+", "_", str(value or "").strip().lower())
        option_code = re.sub(r"[^a-z0-9_-]", "_", option_code)
        option_code = re.sub(r"_+", "_", option_code).strip("_")
        if not option_code:
            raise ValueError("Lookup code is required.")
        return option_code

    def _ensure_local_lookup_option_table(self) -> None:
        if not self.config.use_local_db or self.config.use_mock:
            return
        if self._local_lookup_table_ensured:
            return
        self.client.execute(
            """
            CREATE TABLE IF NOT EXISTS app_lookup_option (
              option_id TEXT PRIMARY KEY,
              lookup_type TEXT NOT NULL,
              option_code TEXT NOT NULL,
              option_label TEXT NOT NULL,
              sort_order INTEGER NOT NULL DEFAULT 100,
              active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
              valid_from_ts TEXT NOT NULL,
              valid_to_ts TEXT,
              is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
              deleted_flag INTEGER NOT NULL DEFAULT 0 CHECK (deleted_flag IN (0, 1)),
              updated_at TEXT NOT NULL,
              updated_by TEXT NOT NULL
            )
            """
        )
        table_info = self.client.query("PRAGMA table_info(app_lookup_option)")
        present = {str(v).strip().lower() for v in table_info.get("name", pd.Series(dtype="object")).tolist()}
        if "valid_from_ts" not in present:
            self.client.execute("ALTER TABLE app_lookup_option ADD COLUMN valid_from_ts TEXT")
        if "valid_to_ts" not in present:
            self.client.execute("ALTER TABLE app_lookup_option ADD COLUMN valid_to_ts TEXT")
        if "is_current" not in present:
            self.client.execute("ALTER TABLE app_lookup_option ADD COLUMN is_current INTEGER DEFAULT 1")
        if "deleted_flag" not in present:
            self.client.execute("ALTER TABLE app_lookup_option ADD COLUMN deleted_flag INTEGER DEFAULT 0")

        now = self._now().isoformat()
        open_end = datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc).isoformat()
        self.client.execute(
            """
            UPDATE app_lookup_option
            SET
              valid_from_ts = COALESCE(valid_from_ts, updated_at, ?),
              valid_to_ts = CASE
                WHEN COALESCE(valid_to_ts, '') = '' AND COALESCE(is_current, 1) IN (1, '1', 'true', 'TRUE') THEN ?
                WHEN COALESCE(valid_to_ts, '') = '' THEN COALESCE(updated_at, ?)
                ELSE valid_to_ts
              END,
              is_current = CASE
                WHEN COALESCE(is_current, 1) IN (1, '1', 'true', 'TRUE') THEN 1
                ELSE 0
              END,
              deleted_flag = CASE
                WHEN COALESCE(deleted_flag, 0) IN (1, '1', 'true', 'TRUE') THEN 1
                WHEN COALESCE(active_flag, 1) IN (0, '0', 'false', 'FALSE') THEN 1
                ELSE 0
              END
            """
            ,
            (now, open_end, now),
        )
        self.client.execute(
            "CREATE INDEX IF NOT EXISTS idx_app_lookup_type_code ON app_lookup_option(lookup_type, option_code)"
        )
        self.client.execute(
            "CREATE INDEX IF NOT EXISTS idx_app_lookup_type_sort ON app_lookup_option(lookup_type, active_flag, sort_order)"
        )
        self.client.execute(
            "CREATE INDEX IF NOT EXISTS idx_app_lookup_type_current ON app_lookup_option(lookup_type, is_current, sort_order)"
        )
        self.client.execute(
            "CREATE INDEX IF NOT EXISTS idx_app_lookup_type_deleted ON app_lookup_option(lookup_type, deleted_flag, sort_order)"
        )
        self._local_lookup_table_ensured = True

    def _ensure_local_offering_columns(self) -> None:
        if not self.config.use_local_db or self.config.use_mock:
            return
        if self._local_offering_columns_ensured:
            return
        try:
            table_info = self.client.query("PRAGMA table_info(core_vendor_offering)")
        except Exception:
            return
        if table_info.empty or "name" not in table_info.columns:
            return
        present = {str(v).strip().lower() for v in table_info["name"].tolist() if str(v).strip()}
        if "lob" not in present:
            self.client.execute("ALTER TABLE core_vendor_offering ADD COLUMN lob TEXT")
        if "service_type" not in present:
            self.client.execute("ALTER TABLE core_vendor_offering ADD COLUMN service_type TEXT")
        self._local_offering_columns_ensured = True

    def _ensure_local_offering_extension_tables(self) -> None:
        if not self.config.use_local_db or self.config.use_mock:
            return
        if self._local_offering_extension_tables_ensured:
            return
        self.client.execute(
            """
            CREATE TABLE IF NOT EXISTS app_offering_profile (
              offering_id TEXT PRIMARY KEY,
              vendor_id TEXT NOT NULL,
              estimated_monthly_cost REAL,
              implementation_notes TEXT,
              data_sent TEXT,
              data_received TEXT,
              integration_method TEXT,
              inbound_method TEXT,
              inbound_landing_zone TEXT,
              inbound_identifiers TEXT,
              inbound_reporting_layer TEXT,
              inbound_ingestion_notes TEXT,
              outbound_method TEXT,
              outbound_creation_process TEXT,
              outbound_delivery_process TEXT,
              outbound_responsible_owner TEXT,
              outbound_notes TEXT,
              updated_at TEXT NOT NULL,
              updated_by TEXT NOT NULL
            )
            """
        )
        profile_table_info = self.client.query("PRAGMA table_info(app_offering_profile)")
        profile_present = {
            str(v).strip().lower() for v in profile_table_info.get("name", pd.Series(dtype="object")).tolist()
        }
        if "inbound_method" not in profile_present:
            self.client.execute("ALTER TABLE app_offering_profile ADD COLUMN inbound_method TEXT")
        if "inbound_landing_zone" not in profile_present:
            self.client.execute("ALTER TABLE app_offering_profile ADD COLUMN inbound_landing_zone TEXT")
        if "inbound_identifiers" not in profile_present:
            self.client.execute("ALTER TABLE app_offering_profile ADD COLUMN inbound_identifiers TEXT")
        if "inbound_reporting_layer" not in profile_present:
            self.client.execute("ALTER TABLE app_offering_profile ADD COLUMN inbound_reporting_layer TEXT")
        if "inbound_ingestion_notes" not in profile_present:
            self.client.execute("ALTER TABLE app_offering_profile ADD COLUMN inbound_ingestion_notes TEXT")
        if "outbound_method" not in profile_present:
            self.client.execute("ALTER TABLE app_offering_profile ADD COLUMN outbound_method TEXT")
        if "outbound_creation_process" not in profile_present:
            self.client.execute("ALTER TABLE app_offering_profile ADD COLUMN outbound_creation_process TEXT")
        if "outbound_delivery_process" not in profile_present:
            self.client.execute("ALTER TABLE app_offering_profile ADD COLUMN outbound_delivery_process TEXT")
        if "outbound_responsible_owner" not in profile_present:
            self.client.execute("ALTER TABLE app_offering_profile ADD COLUMN outbound_responsible_owner TEXT")
        if "outbound_notes" not in profile_present:
            self.client.execute("ALTER TABLE app_offering_profile ADD COLUMN outbound_notes TEXT")
        self.client.execute(
            """
            CREATE TABLE IF NOT EXISTS app_offering_ticket (
              ticket_id TEXT PRIMARY KEY,
              offering_id TEXT NOT NULL,
              vendor_id TEXT NOT NULL,
              ticket_system TEXT,
              external_ticket_id TEXT,
              title TEXT NOT NULL,
              status TEXT NOT NULL,
              priority TEXT,
              opened_date TEXT,
              closed_date TEXT,
              notes TEXT,
              active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
              created_at TEXT NOT NULL,
              created_by TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              updated_by TEXT NOT NULL
            )
            """
        )
        self.client.execute(
            """
            CREATE TABLE IF NOT EXISTS app_offering_data_flow (
              data_flow_id TEXT PRIMARY KEY,
              offering_id TEXT NOT NULL,
              vendor_id TEXT NOT NULL,
              direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
              flow_name TEXT NOT NULL,
              method TEXT,
              data_description TEXT,
              endpoint_details TEXT,
              identifiers TEXT,
              reporting_layer TEXT,
              creation_process TEXT,
              delivery_process TEXT,
              owner_user_principal TEXT,
              notes TEXT,
              active_flag INTEGER NOT NULL DEFAULT 1 CHECK (active_flag IN (0, 1)),
              created_at TEXT NOT NULL,
              created_by TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              updated_by TEXT NOT NULL
            )
            """
        )
        self.client.execute(
            "CREATE INDEX IF NOT EXISTS idx_app_offering_ticket_offering ON app_offering_ticket(offering_id, active_flag, opened_date)"
        )
        self.client.execute(
            "CREATE INDEX IF NOT EXISTS idx_app_offering_ticket_vendor ON app_offering_ticket(vendor_id, active_flag)"
        )
        self.client.execute(
            "CREATE INDEX IF NOT EXISTS idx_app_offering_data_flow_offering ON app_offering_data_flow(offering_id, active_flag, direction)"
        )
        self._local_offering_extension_tables_ensured = True

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return int(value) != 0
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def _parse_lookup_ts(value: Any, *, fallback: datetime) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                return fallback
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except Exception:
                try:
                    parsed = pd.to_datetime(raw, errors="raise", utc=True).to_pydatetime()
                except Exception:
                    return fallback
        elif value is None:
            return fallback
        else:
            return fallback
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @classmethod
    def _normalize_lookup_window(
        cls,
        valid_from_ts: Any,
        valid_to_ts: Any,
    ) -> tuple[datetime, datetime]:
        start = cls._parse_lookup_ts(valid_from_ts, fallback=datetime(1900, 1, 1, tzinfo=timezone.utc))
        end = cls._parse_lookup_ts(valid_to_ts, fallback=datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc))
        if end < start:
            raise ValueError("Valid To must be on or after Valid From.")
        return start, end

    @staticmethod
    def _lookup_status_for_window(start: datetime, end: datetime, *, as_of: datetime) -> str:
        start_date = start.date()
        end_date = end.date()
        as_of_date = as_of.date()
        if end_date < as_of_date:
            return "historical"
        if start_date > as_of_date:
            return "future"
        return "active"

    @staticmethod
    def _lookup_windows_overlap(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
        start_a_date = start_a.date()
        end_a_date = end_a.date()
        start_b_date = start_b.date()
        end_b_date = end_b.date()
        return start_a_date <= end_b_date and start_b_date <= end_a_date

    @staticmethod
    def _principal_to_display_name(user_principal: str) -> str:
        raw = str(user_principal or "").strip()
        if not raw:
            return "Unknown User"

        normalized = raw.split("\\")[-1].split("/")[-1]
        if "@" in normalized:
            normalized = normalized.split("@", 1)[0]
        normalized = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", normalized)
        normalized = re.sub(r"[._-]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if not normalized:
            return "Unknown User"

        parts = [part.capitalize() for part in normalized.split(" ") if part]
        if not parts:
            return "Unknown User"
        if len(parts) == 1:
            return f"{parts[0]} User"
        return " ".join(parts)

    @staticmethod
    def _parse_user_identity(user_principal: str) -> dict[str, str | None]:
        login_identifier = str(user_principal or "").strip()
        if not login_identifier:
            return {
                "login_identifier": "",
                "email": None,
                "network_id": None,
                "first_name": None,
                "last_name": None,
                "display_name": "Unknown User",
            }

        email: str | None = None
        network_id: str | None = None
        if "@" in login_identifier:
            email = login_identifier
        elif "\\" in login_identifier or "/" in login_identifier:
            network_id = login_identifier.split("\\")[-1].split("/")[-1]

        display_name = VendorRepository._principal_to_display_name(login_identifier)
        parts = [part for part in display_name.split(" ") if part and part.lower() != "user"]
        first_name = parts[0] if parts else None
        last_name = " ".join(parts[1:]) if len(parts) > 1 else None

        return {
            "login_identifier": login_identifier,
            "email": email,
            "network_id": network_id,
            "first_name": first_name,
            "last_name": last_name,
            "display_name": display_name,
        }

    def _ensure_user_directory_entry(self, user_principal: str) -> str:
        login_identifier = str(user_principal or "").strip()
        if not login_identifier:
            return UNKNOWN_USER_PRINCIPAL

        identity = self._parse_user_identity(login_identifier)
        lookup_key = login_identifier.lower()

        if self.config.use_mock:
            existing = self._mock_user_directory.get(lookup_key)
            if existing:
                return str(existing.get("user_id") or login_identifier)
            user_id = f"usr-{uuid.uuid5(uuid.NAMESPACE_DNS, lookup_key).hex[:20]}"
            self._mock_user_directory[lookup_key] = {
                "user_id": user_id,
                "login_identifier": login_identifier,
                "display_name": str(identity["display_name"] or login_identifier),
            }
            return user_id

        now = self._now()
        existing = self._query_file(
            "ingestion/select_user_directory_by_login.sql",
            params=(login_identifier,),
            columns=[
                "user_id",
                "login_identifier",
                "email",
                "network_id",
                "first_name",
                "last_name",
                "display_name",
            ],
            app_user_directory=self._table("app_user_directory"),
        )
        if not existing.empty:
            user_id = str(existing.iloc[0]["user_id"])
            try:
                self._execute_file(
                    "updates/update_user_directory_profile.sql",
                    params=(
                        identity["email"],
                        identity["network_id"],
                        identity["first_name"],
                        identity["last_name"],
                        identity["display_name"],
                        now,
                        now,
                        user_id,
                    ),
                    app_user_directory=self._table("app_user_directory"),
                )
            except Exception:
                pass
            return user_id

        user_id = f"usr-{uuid.uuid4().hex[:20]}"
        try:
            self._execute_file(
                "inserts/create_user_directory.sql",
                params=(
                    user_id,
                    login_identifier,
                    identity["email"],
                    identity["network_id"],
                    identity["first_name"],
                    identity["last_name"],
                    identity["display_name"],
                    True,
                    now,
                    now,
                    now,
                ),
                app_user_directory=self._table("app_user_directory"),
            )
            return user_id
        except Exception:
            return login_identifier

    def _actor_ref(self, user_principal: str) -> str:
        if self.config.use_mock:
            return str(user_principal or "")
        return self._ensure_user_directory_entry(user_principal)

    def _user_display_lookup(self) -> dict[str, str]:
        lookup: dict[str, str] = {}
        if self.config.use_mock:
            for entry in self._mock_user_directory.values():
                user_id = str(entry.get("user_id") or "").strip()
                login_identifier = str(entry.get("login_identifier") or "").strip()
                display_name = str(entry.get("display_name") or "").strip()
                if user_id and display_name:
                    lookup[user_id] = display_name
                if login_identifier and display_name:
                    lookup[login_identifier] = display_name
                    lookup[login_identifier.lower()] = display_name
            return lookup

        df = self._query_file(
            "ingestion/select_user_directory_all.sql",
            columns=["user_id", "login_identifier", "display_name"],
            app_user_directory=self._table("app_user_directory"),
        )
        if df.empty:
            return lookup
        for row in df.to_dict("records"):
            user_id = str(row.get("user_id") or "").strip()
            login_identifier = str(row.get("login_identifier") or "").strip()
            display_name = str(row.get("display_name") or "").strip()
            if not display_name:
                continue
            if user_id:
                lookup[user_id] = display_name
            if login_identifier:
                lookup[login_identifier] = display_name
                lookup[login_identifier.lower()] = display_name
        return lookup

    def _decorate_user_columns(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        if df.empty:
            return df
        out = df.copy()
        lookup = self._user_display_lookup()

        def _resolve(value: Any) -> Any:
            if value is None:
                return value
            raw = str(value).strip()
            if not raw:
                return value
            if raw in lookup:
                return lookup[raw]
            lowered = raw.lower()
            if lowered in lookup:
                return lookup[lowered]
            if raw.startswith("usr-"):
                return raw
            return self._principal_to_display_name(raw)

        for column in columns:
            if column in out.columns:
                out[column] = out[column].map(_resolve)
        return out

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

    def _mock_vendor_owners_df(self) -> pd.DataFrame:
        base = mock_data.vendor_business_owners().copy()
        if self._mock_new_vendor_owners:
            base = pd.concat([base, pd.DataFrame(self._mock_new_vendor_owners)], ignore_index=True)
        if "vendor_owner_id" in base.columns and self._mock_removed_vendor_owner_ids:
            base = base[~base["vendor_owner_id"].astype(str).isin(self._mock_removed_vendor_owner_ids)].copy()
        return base

    def _mock_vendor_contacts_df(self) -> pd.DataFrame:
        base = mock_data.contacts().copy()
        if self._mock_new_vendor_contacts:
            base = pd.concat([base, pd.DataFrame(self._mock_new_vendor_contacts)], ignore_index=True)
        if "vendor_contact_id" in base.columns and self._mock_removed_vendor_contact_ids:
            base = base[~base["vendor_contact_id"].astype(str).isin(self._mock_removed_vendor_contact_ids)].copy()
        return base

    def _mock_vendor_org_assignments_df(self) -> pd.DataFrame:
        base = mock_data.vendor_org_assignments().copy()
        if self._mock_new_vendor_org_assignments:
            base = pd.concat([base, pd.DataFrame(self._mock_new_vendor_org_assignments)], ignore_index=True)
        if "vendor_org_assignment_id" in base.columns and self._mock_removed_vendor_org_assignment_ids:
            base = base[
                ~base["vendor_org_assignment_id"].astype(str).isin(self._mock_removed_vendor_org_assignment_ids)
            ].copy()
        return base

    def _mock_append_audit_event(
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
        self._mock_audit_change_overrides.append(
            {
                "change_event_id": change_event_id,
                "entity_name": entity_name,
                "entity_id": entity_id,
                "action_type": action_type,
                "event_ts": self._now().isoformat(),
                "actor_user_principal": actor_user_principal,
                "before_json": before_json,
                "after_json": after_json,
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
        actor_ref = self._actor_ref(actor_user_principal)
        if self.config.use_mock:
            return self._mock_append_audit_event(
                entity_name=entity_name,
                entity_id=entity_id,
                action_type=action_type,
                actor_user_principal=actor_ref,
                before_json=before_json,
                after_json=after_json,
                request_id=request_id,
            )
        try:
            self._execute_file(
                "inserts/audit_entity_change.sql",
                params=(
                    change_event_id,
                    entity_name,
                    entity_id,
                    action_type,
                    json.dumps(before_json, default=str) if before_json is not None else None,
                    json.dumps(after_json, default=str) if after_json is not None else None,
                    actor_ref,
                    self._now(),
                    request_id,
                ),
                audit_entity_change=self._table("audit_entity_change"),
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
        if "change_request_id" in base.columns:
            if "updated_at" in base.columns:
                base = base.sort_values("updated_at")
            base = base.drop_duplicates(subset=["change_request_id"], keep="last")
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

    def _mock_offering_profile_df(self) -> pd.DataFrame:
        columns = [
            "offering_id",
            "vendor_id",
            "estimated_monthly_cost",
            "implementation_notes",
            "data_sent",
            "data_received",
            "integration_method",
            "inbound_method",
            "inbound_landing_zone",
            "inbound_identifiers",
            "inbound_reporting_layer",
            "inbound_ingestion_notes",
            "outbound_method",
            "outbound_creation_process",
            "outbound_delivery_process",
            "outbound_responsible_owner",
            "outbound_notes",
            "updated_at",
            "updated_by",
        ]
        rows = []
        for offering_id, overrides in self._mock_offering_profile_overrides.items():
            rows.append(
                {
                    "offering_id": offering_id,
                    "vendor_id": str(overrides.get("vendor_id") or ""),
                    "estimated_monthly_cost": overrides.get("estimated_monthly_cost"),
                    "implementation_notes": overrides.get("implementation_notes"),
                    "data_sent": overrides.get("data_sent"),
                    "data_received": overrides.get("data_received"),
                    "integration_method": overrides.get("integration_method"),
                    "inbound_method": overrides.get("inbound_method"),
                    "inbound_landing_zone": overrides.get("inbound_landing_zone"),
                    "inbound_identifiers": overrides.get("inbound_identifiers"),
                    "inbound_reporting_layer": overrides.get("inbound_reporting_layer"),
                    "inbound_ingestion_notes": overrides.get("inbound_ingestion_notes"),
                    "outbound_method": overrides.get("outbound_method"),
                    "outbound_creation_process": overrides.get("outbound_creation_process"),
                    "outbound_delivery_process": overrides.get("outbound_delivery_process"),
                    "outbound_responsible_owner": overrides.get("outbound_responsible_owner"),
                    "outbound_notes": overrides.get("outbound_notes"),
                    "updated_at": overrides.get("updated_at"),
                    "updated_by": overrides.get("updated_by"),
                }
            )
        if not rows:
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(rows, columns=columns)

    def _mock_offering_data_flow_df(self) -> pd.DataFrame:
        columns = [
            "data_flow_id",
            "offering_id",
            "vendor_id",
            "direction",
            "flow_name",
            "method",
            "data_description",
            "endpoint_details",
            "identifiers",
            "reporting_layer",
            "creation_process",
            "delivery_process",
            "owner_user_principal",
            "notes",
            "active_flag",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
        ]
        base = (
            pd.DataFrame(self._mock_new_offering_data_flows, columns=columns)
            if self._mock_new_offering_data_flows
            else pd.DataFrame(columns=columns)
        )
        base = self._apply_row_overrides(base, self._mock_offering_data_flow_overrides, "data_flow_id")
        if "data_flow_id" in base.columns and self._mock_removed_offering_data_flow_ids:
            base = base[~base["data_flow_id"].astype(str).isin(self._mock_removed_offering_data_flow_ids)].copy()
        if "active_flag" in base.columns:
            base = base[base["active_flag"].fillna(True) == True].copy()
        return base

    def _mock_offering_tickets_df(self) -> pd.DataFrame:
        columns = [
            "ticket_id",
            "offering_id",
            "vendor_id",
            "ticket_system",
            "external_ticket_id",
            "title",
            "status",
            "priority",
            "opened_date",
            "closed_date",
            "notes",
            "active_flag",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
        ]
        base = pd.DataFrame(self._mock_new_offering_tickets, columns=columns) if self._mock_new_offering_tickets else pd.DataFrame(columns=columns)
        base = self._apply_row_overrides(base, self._mock_offering_ticket_overrides, "ticket_id")
        if "active_flag" in base.columns:
            base = base[base["active_flag"].fillna(True) == True].copy()
        return base

    def _mock_offering_notes_df(self) -> pd.DataFrame:
        columns = ["note_id", "entity_name", "entity_id", "note_type", "note_text", "created_at", "created_by"]
        if not self._mock_new_offering_notes:
            return pd.DataFrame(columns=columns)
        rows = []
        for row in self._mock_new_offering_notes:
            rows.append(
                {
                    "note_id": row.get("note_id"),
                    "entity_name": "offering",
                    "entity_id": row.get("entity_id"),
                    "note_type": row.get("note_type"),
                    "note_text": row.get("note_text"),
                    "created_at": row.get("created_at"),
                    "created_by": row.get("created_by"),
                }
            )
        return pd.DataFrame(rows, columns=columns)

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
        if self._runtime_tables_ensured:
            return

        required_tables = (
            "core_vendor",
            "sec_user_role_map",
            "app_user_settings",
            "app_user_directory",
            "app_lookup_option",
        )
        missing_or_blocked: list[str] = []
        for table_name in required_tables:
            try:
                self.client.query(f"SELECT 1 AS present FROM {self._table(table_name)} LIMIT 1")
            except Exception:
                missing_or_blocked.append(self._table(table_name))

        try:
            self.client.query(
                f"SELECT lob, service_type FROM {self._table('core_vendor_offering')} LIMIT 1"
            )
        except Exception:
            missing_or_blocked.append(f"{self._table('core_vendor_offering')}.lob")
            missing_or_blocked.append(f"{self._table('core_vendor_offering')}.service_type")
        try:
            self.client.query(
                f"SELECT valid_from_ts, valid_to_ts, is_current, deleted_flag FROM {self._table('app_lookup_option')} LIMIT 1"
            )
        except Exception:
            missing_or_blocked.append(f"{self._table('app_lookup_option')}.valid_from_ts")
            missing_or_blocked.append(f"{self._table('app_lookup_option')}.valid_to_ts")
            missing_or_blocked.append(f"{self._table('app_lookup_option')}.is_current")
            missing_or_blocked.append(f"{self._table('app_lookup_option')}.deleted_flag")

        if missing_or_blocked:
            raise SchemaBootstrapRequiredError(
                "Databricks schema is not initialized or access is blocked. "
                "Run the bootstrap SQL and migrations manually before starting the app: "
                f"{self.config.schema_bootstrap_sql_path}, "
                "setup/databricks/002_add_offering_lob_service_type.sql, "
                "setup/databricks/003_add_lookup_scd_columns.sql. "
                f"Configured schema: {self.config.fq_schema}. "
                f"Missing/inaccessible objects: {', '.join(missing_or_blocked)}"
            )

        self._runtime_tables_ensured = True

    def bootstrap_user_access(self, user_principal: str) -> set[str]:
        self._ensure_user_directory_entry(user_principal)
        roles = self.get_user_roles(user_principal)
        if roles:
            return roles
        self.ensure_user_record(user_principal)
        return self.get_user_roles(user_principal)

    def ensure_user_record(self, user_principal: str) -> None:
        self._ensure_user_directory_entry(user_principal)

        if self.config.use_mock:
            current = self.get_user_roles(user_principal)
            if not current:
                self._mock_role_overrides[user_principal] = {"vendor_viewer"}
            return

        current = self._query_file(
            "ingestion/select_user_role_presence.sql",
            params=(user_principal,),
            columns=["has_role"],
            sec_user_role_map=self._table("sec_user_role_map"),
        )
        if not current.empty:
            return

        now = self._now()
        try:
            self._execute_file(
                "inserts/grant_role.sql",
                params=(user_principal, "vendor_viewer", True, "system:auto-bootstrap", now, None),
                sec_user_role_map=self._table("sec_user_role_map"),
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
        self._ensure_user_directory_entry(user_principal)
        if self.config.use_mock:
            return self._mock_user_settings.get((user_principal, setting_key), {})

        df = self._query_file(
            "ingestion/select_user_setting_latest.sql",
            params=(user_principal, setting_key),
            columns=["setting_value_json"],
            app_user_settings=self._table("app_user_settings"),
        )
        if df.empty:
            return {}
        try:
            return json.loads(str(df.iloc[0]["setting_value_json"]))
        except Exception:
            return {}

    def save_user_setting(self, user_principal: str, setting_key: str, setting_value: dict[str, Any]) -> None:
        self._ensure_user_directory_entry(user_principal)
        if self.config.use_mock:
            self._mock_user_settings[(user_principal, setting_key)] = setting_value
            return

        now = self._now()
        payload = self._serialize_payload(setting_value)
        try:
            self._execute_file(
                "updates/delete_user_setting.sql",
                params=(user_principal, setting_key),
                app_user_settings=self._table("app_user_settings"),
            )
            self._execute_file(
                "inserts/save_user_setting.sql",
                params=(str(uuid.uuid4()), user_principal, setting_key, payload, now, user_principal),
                app_user_settings=self._table("app_user_settings"),
            )
        except Exception:
            pass

    def log_usage_event(
        self, user_principal: str, page_name: str, event_type: str, payload: dict[str, Any] | None = None
    ) -> None:
        actor_ref = self._actor_ref(user_principal)
        if self.config.use_mock:
            self._mock_usage_events.append(
                {
                    "usage_event_id": str(uuid.uuid4()),
                    "user_principal": actor_ref,
                    "page_name": page_name,
                    "event_type": event_type,
                    "event_ts": self._now().isoformat(),
                    "payload_json": self._serialize_payload(payload),
                }
            )
            return

        try:
            self._execute_file(
                "inserts/log_usage_event.sql",
                params=(
                    str(uuid.uuid4()),
                    actor_ref,
                    page_name,
                    event_type,
                    self._now(),
                    self._serialize_payload(payload),
                ),
                app_usage_log=self._table("app_usage_log"),
            )
        except Exception:
            pass

    def get_current_user(self) -> str:
        if self.config.use_mock:
            return "admin@example.com"
        if self.config.use_local_db:
            return os.getenv("TVENDOR_TEST_USER", "admin@example.com")
        df = self._query_file(
            "ingestion/select_current_user.sql",
            columns=["user_principal"],
        )
        if df.empty:
            return UNKNOWN_USER_PRINCIPAL
        return str(df.iloc[0]["user_principal"])

    def get_user_roles(self, user_principal: str) -> set[str]:
        if self.config.use_mock:
            df = mock_data.role_map()
            rows = df[(df["user_principal"] == user_principal) & (df["active_flag"] == True)]
            base_roles = set(rows["role_code"].tolist())
            return base_roles.union(self._mock_role_overrides.get(user_principal, set()))

        df = self._query_file(
            "ingestion/select_user_roles.sql",
            params=(user_principal,),
            columns=["role_code"],
            sec_user_role_map=self._table("sec_user_role_map"),
        )
        return set(df["role_code"].tolist()) if not df.empty else set()

    def get_user_display_name(self, user_principal: str) -> str:
        raw = str(user_principal or "").strip()
        if not raw:
            return "Unknown User"
        user_ref = self._ensure_user_directory_entry(raw)
        lookup = self._user_display_lookup()
        return lookup.get(user_ref) or lookup.get(raw) or lookup.get(raw.lower()) or self._principal_to_display_name(raw)

    def _mock_seed_user_directory(self) -> None:
        principals: set[str] = set()
        try:
            for row in mock_data.role_map().to_dict("records"):
                principals.add(str(row.get("user_principal") or "").strip())
        except Exception:
            pass
        for row in self._mock_projects_df().to_dict("records"):
            principals.add(str(row.get("owner_principal") or "").strip())
        for row in self._mock_doc_links_df().to_dict("records"):
            principals.add(str(row.get("owner") or "").strip())
        for row in self._mock_vendors_df().to_dict("records"):
            principals.add(str(row.get("updated_by") or "").strip())
        principals.add("admin@example.com")
        principals.update(
            {
                "pm@example.com",
                "procurement@example.com",
                "secops@example.com",
                "owner@example.com",
            }
        )
        for principal in principals:
            if principal:
                self._ensure_user_directory_entry(principal)

    def search_user_directory(self, q: str = "", limit: int = 20) -> pd.DataFrame:
        normalized_limit = max(1, min(int(limit or 20), 250))
        columns = ["user_id", "login_identifier", "display_name", "label"]
        if self.config.use_mock:
            self._mock_seed_user_directory()
            rows = [
                {
                    "user_id": str(item.get("user_id") or ""),
                    "login_identifier": str(item.get("login_identifier") or ""),
                    "display_name": str(item.get("display_name") or ""),
                }
                for item in self._mock_user_directory.values()
            ]
            df = pd.DataFrame(rows, columns=["user_id", "login_identifier", "display_name"])
        else:
            df = self._query_file(
                "ingestion/select_user_directory_all.sql",
                columns=["user_id", "login_identifier", "display_name"],
                app_user_directory=self._table("app_user_directory"),
            )

        if df.empty:
            return pd.DataFrame(columns=columns)

        for field in ("user_id", "login_identifier", "display_name"):
            if field not in df.columns:
                df[field] = ""
            df[field] = df[field].fillna("").astype(str).str.strip()

        needle = (q or "").strip().lower()
        if needle:
            mask = (
                df["login_identifier"].str.lower().str.contains(needle, regex=False, na=False)
                | df["display_name"].str.lower().str.contains(needle, regex=False, na=False)
            )
            df = df[mask].copy()

        if df.empty:
            return pd.DataFrame(columns=columns)

        df = df[df["login_identifier"] != ""].copy()
        if df.empty:
            return pd.DataFrame(columns=columns)

        df = df.sort_values(["display_name", "login_identifier"], ascending=[True, True])
        df = df.drop_duplicates(subset=["login_identifier"], keep="first")
        df = df.head(normalized_limit).copy()
        df["label"] = df.apply(
            lambda row: (
                f"{row['display_name']} ({row['login_identifier']})"
                if str(row["display_name"]).strip()
                else str(row["login_identifier"])
            ),
            axis=1,
        )
        return df[columns]

    def resolve_user_login_identifier(self, user_value: str) -> str | None:
        cleaned = str(user_value or "").strip()
        if not cleaned:
            return None

        if not self.config.use_mock:
            exact = self._query_file(
                "ingestion/select_user_directory_by_login.sql",
                params=(cleaned,),
                columns=["login_identifier"],
                app_user_directory=self._table("app_user_directory"),
            )
            if not exact.empty:
                return str(exact.iloc[0]["login_identifier"]).strip()

        candidates = self.search_user_directory(q=cleaned, limit=250)
        if candidates.empty:
            return None

        lowered = cleaned.lower()
        for row in candidates.to_dict("records"):
            login_identifier = str(row.get("login_identifier") or "").strip()
            if login_identifier.lower() == lowered:
                return login_identifier
        for row in candidates.to_dict("records"):
            display_name = str(row.get("display_name") or "").strip()
            if display_name and display_name.lower() == lowered:
                return str(row.get("login_identifier") or "").strip() or None
        return None

    def dashboard_kpis(self) -> dict[str, int]:
        if self.config.use_mock:
            return {
                "active_vendors": int((self._mock_vendors_df()["lifecycle_state"] == "active").sum()),
                "active_offerings": int((self._mock_offerings_df()["lifecycle_state"] == "active").sum()),
                "demos_logged": int(len(self._mock_demos_df())),
                "cancelled_contracts": int(len(mock_data.contract_cancellations())),
            }

        vendor_df = self.client.query(
            self._sql(
                "reporting/dashboard_active_vendors.sql",
                core_vendor=self._table("core_vendor"),
            )
        )
        offering_df = self.client.query(
            self._sql(
                "reporting/dashboard_active_offerings.sql",
                core_vendor_offering=self._table("core_vendor_offering"),
            )
        )
        demo_df = self.client.query(
            self._sql(
                "reporting/dashboard_demo_count.sql",
                core_vendor_demo=self._table("core_vendor_demo"),
            )
        )
        cancel_df = self.client.query(
            self._sql(
                "reporting/dashboard_cancelled_contract_count.sql",
                core_contract_event=self._table("core_contract_event"),
            )
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
        df = self._query_file(
            "reporting/available_orgs.sql",
            columns=["org_id"],
            core_vendor=self._table("core_vendor"),
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
        return self._query_file(
            "reporting/executive_spend_by_category.sql",
            params=params,
            columns=["category", "total_spend"],
            rpt_spend_fact=self._table("rpt_spend_fact"),
            months_back=(months - 1),
            org_clause=org_clause,
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
        return self._query_file(
            "reporting/executive_monthly_spend_trend.sql",
            params=params,
            columns=["month", "total_spend"],
            rpt_spend_fact=self._table("rpt_spend_fact"),
            months_back=(months - 1),
            org_clause=org_clause,
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
        return self._query_file(
            "reporting/executive_top_vendors_by_spend.sql",
            params=params,
            columns=["vendor_id", "vendor_name", "risk_tier", "total_spend"],
            rpt_spend_fact=self._table("rpt_spend_fact"),
            core_vendor=self._table("core_vendor"),
            months_back=(months - 1),
            org_clause=org_clause,
            limit_rows=limit,
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
        return self._query_file(
            "reporting/executive_risk_distribution.sql",
            params=params,
            columns=["risk_tier", "vendor_count"],
            core_vendor=self._table("core_vendor"),
            org_clause=org_clause,
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
        return self._query_file(
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

        if self.config.use_mock:
            project_vendor_map = self._mock_project_vendor_map_df()[["project_id", "vendor_id"]].copy()
            project_offering_map = self._mock_project_offering_map_df()[["project_id", "offering_id"]].copy()
            project_notes = self._mock_project_notes_df()[["project_id", "project_note_id"]].copy()
            project_docs = self._mock_doc_links_df()
            project_docs = project_docs[project_docs["entity_type"].astype(str) == "project"][["entity_id", "doc_id"]].copy()
        else:
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

        if self.config.use_mock:
            offerings = self._mock_offerings_df().copy()
            offerings = offerings[offerings["vendor_id"].astype(str).isin(cleaned_ids)].copy()
            if offerings.empty:
                return pd.DataFrame(columns=columns)
            out = offerings[columns].copy()
            return out.sort_values(["vendor_id", "offering_name"], ascending=[True, True])

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
        if self.config.use_mock:
            vendors = self._mock_vendors_df().copy()
            vendors = vendors[vendors["vendor_id"].astype(str).isin(cleaned_ids)].copy()
            for col in columns:
                if col not in vendors.columns:
                    vendors[col] = None
            return vendors[columns]
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
        if self.config.use_mock:
            offerings = self._mock_offerings_df().copy()
            offerings = offerings[offerings["offering_id"].astype(str).isin(cleaned_ids)].copy()
            vendors = self._mock_vendors_df()[["vendor_id", "display_name", "legal_name"]].copy()
            offerings = offerings.merge(vendors, on="vendor_id", how="left")
            offerings["vendor_display_name"] = offerings["display_name"].fillna(offerings["legal_name"]).fillna(
                offerings["vendor_id"]
            )
            for col in columns:
                if col not in offerings.columns:
                    offerings[col] = None
            return offerings[columns]
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
        if self.config.use_mock:
            df = self._mock_vendors_df().copy()
            if q.strip():
                needle = q.strip().lower()
                df = df[
                    df.apply(
                        lambda r: any(
                            self._matches_needle(r.get(field), needle)
                            for field in ["vendor_id", "display_name", "legal_name", "owner_org_id", "risk_tier"]
                        ),
                        axis=1,
                    )
                ].copy()
            df["label"] = df["display_name"].fillna(df["legal_name"]).fillna(df["vendor_id"])
            for col in columns:
                if col not in df.columns:
                    df[col] = None
            return df.sort_values(["label", "vendor_id"]).head(limit)[columns]
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
        if self.config.use_mock:
            offerings = self._mock_offerings_df().copy()
            vendors = self._mock_vendors_df()[["vendor_id", "display_name", "legal_name"]].copy()
            offerings = offerings.merge(vendors, on="vendor_id", how="left")
            offerings["vendor_display_name"] = offerings["display_name"].fillna(offerings["legal_name"]).fillna(
                offerings["vendor_id"]
            )
            if filter_vendor:
                offerings = offerings[offerings["vendor_id"].astype(str) == filter_vendor].copy()
            if q.strip():
                needle = q.strip().lower()
                offerings = offerings[
                    offerings.apply(
                        lambda r: any(
                            self._matches_needle(r.get(field), needle)
                            for field in [
                                "offering_id",
                                "offering_name",
                                "offering_type",
                                "lob",
                                "service_type",
                                "vendor_id",
                                "vendor_display_name",
                            ]
                        ),
                        axis=1,
                    )
                ].copy()
            offerings["label"] = (
                offerings["offering_name"].fillna(offerings["offering_id"])
                + " ("
                + offerings["offering_id"].astype(str)
                + ") - "
                + offerings["vendor_display_name"].astype(str)
            )
            for col in columns:
                if col not in offerings.columns:
                    offerings[col] = None
            return offerings.sort_values(["vendor_display_name", "offering_name"]).head(limit)[columns]

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
        if self.config.use_mock:
            projects = self.list_all_projects(search_text=q, status="all", vendor_id="all", limit=max(50, limit)).copy()
            if projects.empty:
                return pd.DataFrame(columns=columns)
            projects["vendor_display_name"] = projects["vendor_display_name"].fillna("Unassigned")
            projects["label"] = (
                projects["project_name"].fillna(projects["project_id"])
                + " ("
                + projects["project_id"].astype(str)
                + ") - "
                + projects["vendor_display_name"].astype(str)
            )
            for col in columns:
                if col not in projects.columns:
                    projects[col] = None
            return projects[columns].head(limit)

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

        if self.config.use_mock:
            df = self.search_vendors(search_text=search_text, lifecycle_state=lifecycle_state).copy()
            if owner_org_id != "all" and "owner_org_id" in df.columns:
                df = df[df["owner_org_id"].astype(str) == str(owner_org_id)].copy()
            if risk_tier != "all" and "risk_tier" in df.columns:
                df = df[df["risk_tier"].astype(str) == str(risk_tier)].copy()
            if sort_col in df.columns:
                df = df.sort_values(sort_col, ascending=(sort_dir == "asc"), kind="mergesort", na_position="last")
            if "vendor_id" in df.columns:
                df = df.sort_values(
                    [sort_col, "vendor_id"] if sort_col in df.columns else ["vendor_id"],
                    ascending=[sort_dir == "asc", True] if sort_col in df.columns else [True],
                    kind="mergesort",
                    na_position="last",
                )
            total = int(len(df))
            page_df = df.iloc[offset : offset + page_size].copy()
            for col in columns:
                if col not in page_df.columns:
                    page_df[col] = None
            return page_df[columns], total

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
        except Exception:
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
                        for field in [
                            "offering_id",
                            "offering_name",
                            "offering_type",
                            "lob",
                            "service_type",
                            "lifecycle_state",
                        ]
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
        except Exception:
            return self._query_file(
                "reporting/search_vendors_fallback.sql",
                params=tuple([like, like, like] + params),
                state_clause=state_clause,
                core_vendor=self._table("core_vendor"),
            )

    def get_vendor_profile(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            return self._mock_vendors_df().query("vendor_id == @vendor_id")
        return self._query_file(
            "ingestion/select_vendor_profile_by_id.sql",
            params=(vendor_id,),
            core_vendor=self._table("core_vendor"),
        )

    def get_vendor_offerings(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            return self._mock_offerings_df().query("vendor_id == @vendor_id")
        self._ensure_local_offering_columns()
        return self._query_file(
            "ingestion/select_vendor_offerings.sql",
            params=(vendor_id,),
            core_vendor_offering=self._table("core_vendor_offering"),
        )

    def get_vendor_contacts(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            return self._mock_vendor_contacts_df().query("vendor_id == @vendor_id")
        return self._query_file(
            "ingestion/select_vendor_contacts.sql",
            params=(vendor_id,),
            core_vendor_contact=self._table("core_vendor_contact"),
        )

    def get_vendor_identifiers(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            return mock_data.vendor_identifiers().query("vendor_id == @vendor_id")
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
        if self.config.use_mock:
            return self._mock_vendor_owners_df().query("vendor_id == @vendor_id")
        return self._query_file(
            "ingestion/select_vendor_business_owners.sql",
            params=(vendor_id,),
            columns=["vendor_owner_id", "vendor_id", "owner_user_principal", "owner_role", "active_flag"],
            core_vendor_business_owner=self._table("core_vendor_business_owner"),
        )

    def get_vendor_org_assignments(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            return self._mock_vendor_org_assignments_df().query("vendor_id == @vendor_id")
        return self._query_file(
            "ingestion/select_vendor_org_assignments.sql",
            params=(vendor_id,),
            columns=["vendor_org_assignment_id", "vendor_id", "org_id", "assignment_type", "active_flag"],
            core_vendor_org_assignment=self._table("core_vendor_org_assignment"),
        )

    def get_vendor_offering_business_owners(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            offs = self._mock_offerings_df().query("vendor_id == @vendor_id")[["offering_id", "offering_name"]]
            owners = self._mock_offering_owners_df()
            merged = owners.merge(offs, on="offering_id", how="inner")
            return merged
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
        )

    def get_vendor_offering_contacts(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            offs = self._mock_offerings_df().query("vendor_id == @vendor_id")[["offering_id", "offering_name"]]
            contacts = self._mock_offering_contacts_df()
            merged = contacts.merge(offs, on="offering_id", how="inner")
            return merged
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
        if self.config.use_mock:
            return self._mock_contracts_df().query("vendor_id == @vendor_id")
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
        if self.config.use_mock:
            contracts = self._mock_contracts_df().query("vendor_id == @vendor_id")[["contract_id"]]
            events = mock_data.contract_events()
            out = events.merge(contracts, on="contract_id", how="inner").sort_values("event_ts", ascending=False)
            return self._decorate_user_columns(out, ["actor_user_principal"])
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
        if self.config.use_mock:
            return self._mock_demos_df().query("vendor_id == @vendor_id").sort_values("demo_date", ascending=False)
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
        if self.config.use_mock:
            demos = self._mock_demos_df().query("vendor_id == @vendor_id")[["demo_id"]]
            return mock_data.demo_scores().merge(demos, on="demo_id", how="inner")
        return self._query_file(
            "ingestion/select_vendor_demo_scores.sql",
            params=(vendor_id,),
            columns=["demo_score_id", "demo_id", "score_category", "score_value", "weight", "comments"],
            core_vendor_demo_score=self._table("core_vendor_demo_score"),
            core_vendor_demo=self._table("core_vendor_demo"),
        )

    def get_vendor_demo_notes(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            demos = self._mock_demos_df().query("vendor_id == @vendor_id")[["demo_id"]]
            return mock_data.demo_notes().merge(demos, on="demo_id", how="inner")
        return self._query_file(
            "ingestion/select_vendor_demo_notes.sql",
            params=(vendor_id,),
            columns=["demo_note_id", "demo_id", "note_type", "note_text", "created_at", "created_by"],
            core_vendor_demo_note=self._table("core_vendor_demo_note"),
            core_vendor_demo=self._table("core_vendor_demo"),
        )

    def get_vendor_change_requests(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            out = self._mock_change_requests_df().query("vendor_id == @vendor_id").sort_values("submitted_at", ascending=False)
            if "requestor_user_principal" in out.columns and "requestor_user_principal_raw" not in out.columns:
                out["requestor_user_principal_raw"] = out["requestor_user_principal"]
            return self._decorate_user_columns(out, ["requestor_user_principal"])
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
        if self.config.use_mock:
            rows = self._mock_change_requests_df().copy()
            if normalized_status != "all" and "status" in rows.columns:
                rows = rows[rows["status"].astype(str).str.lower() == normalized_status].copy()
            if "submitted_at" in rows.columns:
                rows = rows.sort_values("submitted_at", ascending=False)
            if "requestor_user_principal" in rows.columns and "requestor_user_principal_raw" not in rows.columns:
                rows["requestor_user_principal_raw"] = rows["requestor_user_principal"]
            return self._decorate_user_columns(rows, ["requestor_user_principal"])

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
        if self.config.use_mock:
            rows = self._mock_change_requests_df()
            if rows.empty:
                return None
            match = rows[rows["change_request_id"].astype(str) == request_id]
            if match.empty:
                return None
            out = self._decorate_user_columns(match.tail(1), ["requestor_user_principal"])
            if "requestor_user_principal_raw" not in out and "requestor_user_principal" in out:
                out["requestor_user_principal_raw"] = match.tail(1)["requestor_user_principal"].tolist()
            return out.iloc[-1].to_dict()
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
        if self.config.use_mock:
            updated = dict(current)
            updated["status"] = target_status
            updated["updated_at"] = now.isoformat()
            self._mock_change_request_overrides.append(updated)
        else:
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
        except Exception:
            pass

        updated_row = self.get_change_request_by_id(request_id)
        return updated_row or {"change_request_id": request_id, "status": target_status}

    def get_vendor_audit_events(self, vendor_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            events = self._mock_audit_changes_df()
            requests = self._mock_change_requests_df().query("vendor_id == @vendor_id")["change_request_id"].tolist()
            vendor_events = events[(events["entity_id"] == vendor_id) | (events["request_id"].isin(requests))]
            out = vendor_events.sort_values("event_ts", ascending=False)
            out = self._with_audit_change_summaries(out)
            return self._decorate_user_columns(out, ["actor_user_principal"])
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
        return self._query_file(
            "reporting/vendor_spend_by_category.sql",
            params=(vendor_id,),
            columns=["category", "total_spend"],
            rpt_spend_fact=self._table("rpt_spend_fact"),
            months_back=(months - 1),
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

    def get_offering_profile(self, vendor_id: str, offering_id: str) -> dict[str, Any]:
        default = {
            "offering_id": offering_id,
            "vendor_id": vendor_id,
            "estimated_monthly_cost": None,
            "implementation_notes": None,
            "data_sent": None,
            "data_received": None,
            "integration_method": None,
            "inbound_method": None,
            "inbound_landing_zone": None,
            "inbound_identifiers": None,
            "inbound_reporting_layer": None,
            "inbound_ingestion_notes": None,
            "outbound_method": None,
            "outbound_creation_process": None,
            "outbound_delivery_process": None,
            "outbound_responsible_owner": None,
            "outbound_notes": None,
            "updated_at": None,
            "updated_by": None,
        }
        if self.config.use_mock:
            rows = self._mock_offering_profile_df()
            if rows.empty:
                return default
            match = rows[rows["offering_id"].astype(str) == str(offering_id)]
            if match.empty:
                return default
            row = match.iloc[-1].to_dict()
            out = dict(default)
            out.update(row)
            return out

        self._ensure_local_offering_extension_tables()
        rows = self._query_file(
            "ingestion/select_offering_profile.sql",
            params=(offering_id, vendor_id),
            columns=[
                "offering_id",
                "vendor_id",
                "estimated_monthly_cost",
                "implementation_notes",
                "data_sent",
                "data_received",
                "integration_method",
                "inbound_method",
                "inbound_landing_zone",
                "inbound_identifiers",
                "inbound_reporting_layer",
                "inbound_ingestion_notes",
                "outbound_method",
                "outbound_creation_process",
                "outbound_delivery_process",
                "outbound_responsible_owner",
                "outbound_notes",
                "updated_at",
                "updated_by",
            ],
            app_offering_profile=self._table("app_offering_profile"),
        )
        if rows.empty:
            return default
        row = rows.iloc[0].to_dict()
        out = dict(default)
        out.update(row)
        return out

    def save_offering_profile(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        actor_user_principal: str,
        updates: dict[str, Any],
        reason: str,
    ) -> dict[str, str]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to this vendor.")

        allowed = {
            "estimated_monthly_cost",
            "implementation_notes",
            "data_sent",
            "data_received",
            "integration_method",
            "inbound_method",
            "inbound_landing_zone",
            "inbound_identifiers",
            "inbound_reporting_layer",
            "inbound_ingestion_notes",
            "outbound_method",
            "outbound_creation_process",
            "outbound_delivery_process",
            "outbound_responsible_owner",
            "outbound_notes",
        }
        clean_updates = {k: v for k, v in updates.items() if k in allowed}
        if not clean_updates:
            raise ValueError("No profile fields were provided.")
        if "outbound_responsible_owner" in clean_updates:
            candidate_owner = str(clean_updates.get("outbound_responsible_owner") or "").strip()
            if candidate_owner:
                resolved_owner = self.resolve_user_login_identifier(candidate_owner)
                if not resolved_owner:
                    raise ValueError("Outbound responsible owner must exist in the app user directory.")
                clean_updates["outbound_responsible_owner"] = resolved_owner
            else:
                clean_updates["outbound_responsible_owner"] = None

        current = self.get_offering_profile(vendor_id, offering_id)
        had_existing = any(current.get(field) not in (None, "") for field in allowed)
        before = dict(current)
        after = dict(current)
        after.update(clean_updates)

        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        request_id = str(uuid.uuid4())
        payload = {
            "offering_id": offering_id,
            "vendor_id": vendor_id,
            "estimated_monthly_cost": after.get("estimated_monthly_cost"),
            "implementation_notes": after.get("implementation_notes"),
            "data_sent": after.get("data_sent"),
            "data_received": after.get("data_received"),
            "integration_method": after.get("integration_method"),
            "inbound_method": after.get("inbound_method"),
            "inbound_landing_zone": after.get("inbound_landing_zone"),
            "inbound_identifiers": after.get("inbound_identifiers"),
            "inbound_reporting_layer": after.get("inbound_reporting_layer"),
            "inbound_ingestion_notes": after.get("inbound_ingestion_notes"),
            "outbound_method": after.get("outbound_method"),
            "outbound_creation_process": after.get("outbound_creation_process"),
            "outbound_delivery_process": after.get("outbound_delivery_process"),
            "outbound_responsible_owner": after.get("outbound_responsible_owner"),
            "outbound_notes": after.get("outbound_notes"),
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }

        if self.config.use_mock:
            self._mock_offering_profile_overrides[offering_id] = payload
            action_type = "update" if had_existing else "insert"
            change_event_id = self._write_audit_entity_change(
                entity_name="app_offering_profile",
                entity_id=offering_id,
                action_type=action_type,
                actor_user_principal=actor_user_principal,
                before_json=before if had_existing else None,
                after_json=payload,
                request_id=request_id,
            )
            return {"request_id": request_id, "change_event_id": change_event_id}

        self._ensure_local_offering_extension_tables()
        existing = self._query_file(
            "ingestion/select_offering_profile.sql",
            params=(offering_id, vendor_id),
            columns=["offering_id"],
            app_offering_profile=self._table("app_offering_profile"),
        )
        if existing.empty:
            self._execute_file(
                "inserts/create_offering_profile.sql",
                params=(
                    offering_id,
                    vendor_id,
                    payload["estimated_monthly_cost"],
                    payload["implementation_notes"],
                    payload["data_sent"],
                    payload["data_received"],
                    payload["integration_method"],
                    payload["inbound_method"],
                    payload["inbound_landing_zone"],
                    payload["inbound_identifiers"],
                    payload["inbound_reporting_layer"],
                    payload["inbound_ingestion_notes"],
                    payload["outbound_method"],
                    payload["outbound_creation_process"],
                    payload["outbound_delivery_process"],
                    payload["outbound_responsible_owner"],
                    payload["outbound_notes"],
                    now,
                    actor_ref,
                ),
                app_offering_profile=self._table("app_offering_profile"),
            )
            action_type = "insert"
            before_json = None
        else:
            self._execute_file(
                "updates/update_offering_profile.sql",
                params=(
                    payload["estimated_monthly_cost"],
                    payload["implementation_notes"],
                    payload["data_sent"],
                    payload["data_received"],
                    payload["integration_method"],
                    payload["inbound_method"],
                    payload["inbound_landing_zone"],
                    payload["inbound_identifiers"],
                    payload["inbound_reporting_layer"],
                    payload["inbound_ingestion_notes"],
                    payload["outbound_method"],
                    payload["outbound_creation_process"],
                    payload["outbound_delivery_process"],
                    payload["outbound_responsible_owner"],
                    payload["outbound_notes"],
                    now,
                    actor_ref,
                    offering_id,
                    vendor_id,
                ),
                app_offering_profile=self._table("app_offering_profile"),
            )
            action_type = "update"
            before_json = before

        change_event_id = self._write_audit_entity_change(
            entity_name="app_offering_profile",
            entity_id=offering_id,
            action_type=action_type,
            actor_user_principal=actor_user_principal,
            before_json=before_json,
            after_json=payload,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def list_offering_data_flows(self, vendor_id: str, offering_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            rows = self._mock_offering_data_flow_df()
            if rows.empty:
                return rows
            rows = rows[
                (rows["offering_id"].astype(str) == str(offering_id))
                & (rows["vendor_id"].astype(str) == str(vendor_id))
            ].copy()
            if "direction" in rows.columns:
                rows["direction_sort"] = rows["direction"].astype(str).str.lower().map({"inbound": 0, "outbound": 1}).fillna(9)
            else:
                rows["direction_sort"] = 9
            if "updated_at" in rows.columns:
                rows = rows.sort_values(["direction_sort", "updated_at"], ascending=[True, False])
            rows = rows.drop(columns=["direction_sort"], errors="ignore")
            return self._decorate_user_columns(rows, ["owner_user_principal", "created_by", "updated_by"])

        self._ensure_local_offering_extension_tables()
        rows = self._query_file(
            "ingestion/select_offering_data_flows.sql",
            params=(offering_id, vendor_id),
            columns=[
                "data_flow_id",
                "offering_id",
                "vendor_id",
                "direction",
                "flow_name",
                "method",
                "data_description",
                "endpoint_details",
                "identifiers",
                "reporting_layer",
                "creation_process",
                "delivery_process",
                "owner_user_principal",
                "notes",
                "active_flag",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ],
            app_offering_data_flow=self._table("app_offering_data_flow"),
        )
        return self._decorate_user_columns(rows, ["owner_user_principal", "created_by", "updated_by"])

    def get_offering_data_flow(self, *, vendor_id: str, offering_id: str, data_flow_id: str) -> dict[str, Any] | None:
        if self.config.use_mock:
            rows = self._mock_offering_data_flow_df()
            if rows.empty:
                return None
            match = rows[
                (rows["data_flow_id"].astype(str) == str(data_flow_id))
                & (rows["offering_id"].astype(str) == str(offering_id))
                & (rows["vendor_id"].astype(str) == str(vendor_id))
            ]
            if match.empty:
                return None
            return match.iloc[0].to_dict()

        self._ensure_local_offering_extension_tables()
        rows = self._query_file(
            "ingestion/select_offering_data_flow_by_id.sql",
            params=(data_flow_id, offering_id, vendor_id),
            columns=[
                "data_flow_id",
                "offering_id",
                "vendor_id",
                "direction",
                "flow_name",
                "method",
                "data_description",
                "endpoint_details",
                "identifiers",
                "reporting_layer",
                "creation_process",
                "delivery_process",
                "owner_user_principal",
                "notes",
                "active_flag",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ],
            app_offering_data_flow=self._table("app_offering_data_flow"),
        )
        if rows.empty:
            return None
        return rows.iloc[0].to_dict()

    def add_offering_data_flow(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        direction: str,
        flow_name: str,
        method: str | None,
        data_description: str | None,
        endpoint_details: str | None,
        identifiers: str | None,
        reporting_layer: str | None,
        creation_process: str | None,
        delivery_process: str | None,
        owner_user_principal: str | None,
        notes: str | None,
        actor_user_principal: str,
    ) -> str:
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to this vendor.")
        clean_direction = str(direction or "").strip().lower()
        if clean_direction not in {"inbound", "outbound"}:
            raise ValueError("Direction must be inbound or outbound.")
        clean_flow_name = str(flow_name or "").strip()
        if not clean_flow_name:
            raise ValueError("Data flow name is required.")
        clean_method = str(method or "").strip().lower() or None
        clean_data_description = str(data_description or "").strip() or None
        clean_endpoint_details = str(endpoint_details or "").strip() or None
        clean_identifiers = str(identifiers or "").strip() or None
        clean_reporting_layer = str(reporting_layer or "").strip() or None
        clean_creation_process = str(creation_process or "").strip() or None
        clean_delivery_process = str(delivery_process or "").strip() or None
        clean_notes = str(notes or "").strip() or None
        clean_owner = str(owner_user_principal or "").strip()
        resolved_owner: str | None = None
        if clean_owner:
            resolved_owner = self.resolve_user_login_identifier(clean_owner)
            if not resolved_owner:
                raise ValueError("Owner must exist in the app user directory.")

        data_flow_id = self._new_id("odf")
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        row = {
            "data_flow_id": data_flow_id,
            "offering_id": offering_id,
            "vendor_id": vendor_id,
            "direction": clean_direction,
            "flow_name": clean_flow_name,
            "method": clean_method,
            "data_description": clean_data_description,
            "endpoint_details": clean_endpoint_details,
            "identifiers": clean_identifiers,
            "reporting_layer": clean_reporting_layer,
            "creation_process": clean_creation_process,
            "delivery_process": clean_delivery_process,
            "owner_user_principal": resolved_owner,
            "notes": clean_notes,
            "active_flag": True,
            "created_at": now.isoformat(),
            "created_by": actor_ref,
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }
        if self.config.use_mock:
            self._mock_new_offering_data_flows.append(row)
            self._write_audit_entity_change(
                entity_name="app_offering_data_flow",
                entity_id=data_flow_id,
                action_type="insert",
                actor_user_principal=actor_user_principal,
                before_json=None,
                after_json=row,
                request_id=None,
            )
            return data_flow_id

        self._ensure_local_offering_extension_tables()
        self._execute_file(
            "inserts/create_offering_data_flow.sql",
            params=(
                data_flow_id,
                offering_id,
                vendor_id,
                clean_direction,
                clean_flow_name,
                clean_method,
                clean_data_description,
                clean_endpoint_details,
                clean_identifiers,
                clean_reporting_layer,
                clean_creation_process,
                clean_delivery_process,
                resolved_owner,
                clean_notes,
                True,
                now,
                actor_ref,
                now,
                actor_ref,
            ),
            app_offering_data_flow=self._table("app_offering_data_flow"),
        )
        self._write_audit_entity_change(
            entity_name="app_offering_data_flow",
            entity_id=data_flow_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return data_flow_id

    def remove_offering_data_flow(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        data_flow_id: str,
        actor_user_principal: str,
    ) -> None:
        current = self.get_offering_data_flow(
            vendor_id=vendor_id,
            offering_id=offering_id,
            data_flow_id=data_flow_id,
        )
        if current is None:
            raise ValueError("Offering data flow was not found.")
        actor_ref = self._actor_ref(actor_user_principal)
        if self.config.use_mock:
            self._mock_removed_offering_data_flow_ids.add(str(data_flow_id))
            self._write_audit_entity_change(
                entity_name="app_offering_data_flow",
                entity_id=data_flow_id,
                action_type="delete",
                actor_user_principal=actor_user_principal,
                before_json=current,
                after_json=None,
                request_id=None,
            )
            return
        try:
            self._execute_file(
                "updates/remove_offering_data_flow_soft.sql",
                params=(self._now(), actor_ref, data_flow_id, offering_id, vendor_id),
                app_offering_data_flow=self._table("app_offering_data_flow"),
            )
        except Exception:
            self._execute_file(
                "updates/remove_offering_data_flow_delete.sql",
                params=(data_flow_id, offering_id, vendor_id),
                app_offering_data_flow=self._table("app_offering_data_flow"),
            )
        self._write_audit_entity_change(
            entity_name="app_offering_data_flow",
            entity_id=data_flow_id,
            action_type="delete",
            actor_user_principal=actor_user_principal,
            before_json=current,
            after_json=None,
            request_id=None,
        )

    def update_offering_data_flow(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        data_flow_id: str,
        actor_user_principal: str,
        updates: dict[str, Any],
        reason: str,
    ) -> dict[str, str]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to this vendor.")
        current = self.get_offering_data_flow(
            vendor_id=vendor_id,
            offering_id=offering_id,
            data_flow_id=data_flow_id,
        )
        if current is None:
            raise ValueError("Offering data flow was not found.")

        allowed = {
            "direction",
            "flow_name",
            "method",
            "data_description",
            "endpoint_details",
            "identifiers",
            "reporting_layer",
            "creation_process",
            "delivery_process",
            "owner_user_principal",
            "notes",
        }
        clean_updates = {k: v for k, v in updates.items() if k in allowed}
        if not clean_updates:
            raise ValueError("No data flow fields were provided.")

        if "direction" in clean_updates:
            direction = str(clean_updates.get("direction") or "").strip().lower()
            if direction not in {"inbound", "outbound"}:
                raise ValueError("Direction must be inbound or outbound.")
            clean_updates["direction"] = direction
        if "flow_name" in clean_updates:
            flow_name = str(clean_updates.get("flow_name") or "").strip()
            if not flow_name:
                raise ValueError("Data flow name is required.")
            clean_updates["flow_name"] = flow_name
        if "method" in clean_updates:
            clean_updates["method"] = str(clean_updates.get("method") or "").strip().lower() or None
        for optional_text_key in {
            "data_description",
            "endpoint_details",
            "identifiers",
            "reporting_layer",
            "creation_process",
            "delivery_process",
            "notes",
        }:
            if optional_text_key in clean_updates:
                clean_updates[optional_text_key] = str(clean_updates.get(optional_text_key) or "").strip() or None
        if "owner_user_principal" in clean_updates:
            owner_candidate = str(clean_updates.get("owner_user_principal") or "").strip()
            if owner_candidate:
                resolved_owner = self.resolve_user_login_identifier(owner_candidate)
                if not resolved_owner:
                    raise ValueError("Owner must exist in the app user directory.")
                clean_updates["owner_user_principal"] = resolved_owner
            else:
                clean_updates["owner_user_principal"] = None

        before = dict(current)
        after = dict(current)
        after.update(clean_updates)
        request_id = str(uuid.uuid4())
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        clean_updates["updated_at"] = now.isoformat()
        clean_updates["updated_by"] = actor_ref

        if self.config.use_mock:
            self._mock_offering_data_flow_overrides[data_flow_id] = {
                **self._mock_offering_data_flow_overrides.get(data_flow_id, {}),
                **clean_updates,
            }
        else:
            set_clause = ", ".join(
                [f"{key} = %s" for key in clean_updates.keys() if key not in {"updated_at", "updated_by"}]
            )
            params = [clean_updates[key] for key in clean_updates.keys() if key not in {"updated_at", "updated_by"}]
            self._execute_file(
                "updates/update_offering_data_flow.sql",
                params=tuple(params + [now, actor_ref, data_flow_id, offering_id, vendor_id]),
                app_offering_data_flow=self._table("app_offering_data_flow"),
                set_clause=set_clause,
            )

        after.update(clean_updates)
        change_event_id = self._write_audit_entity_change(
            entity_name="app_offering_data_flow",
            entity_id=data_flow_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def list_offering_tickets(self, vendor_id: str, offering_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            rows = self._mock_offering_tickets_df()
            if rows.empty:
                return rows
            rows = rows[
                (rows["offering_id"].astype(str) == str(offering_id))
                & (rows["vendor_id"].astype(str) == str(vendor_id))
            ].copy()
            if "opened_date" in rows.columns:
                rows = rows.sort_values("opened_date", ascending=False)
            return self._decorate_user_columns(rows, ["created_by", "updated_by"])

        self._ensure_local_offering_extension_tables()
        rows = self._query_file(
            "ingestion/select_offering_tickets.sql",
            params=(offering_id, vendor_id),
            columns=[
                "ticket_id",
                "offering_id",
                "vendor_id",
                "ticket_system",
                "external_ticket_id",
                "title",
                "status",
                "priority",
                "opened_date",
                "closed_date",
                "notes",
                "active_flag",
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ],
            app_offering_ticket=self._table("app_offering_ticket"),
        )
        return self._decorate_user_columns(rows, ["created_by", "updated_by"])

    def add_offering_ticket(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        title: str,
        ticket_system: str | None,
        external_ticket_id: str | None,
        status: str,
        priority: str | None,
        opened_date: str | None,
        notes: str | None,
        actor_user_principal: str,
    ) -> str:
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to this vendor.")
        clean_title = str(title or "").strip()
        clean_status = str(status or "").strip().lower() or "open"
        if not clean_title:
            raise ValueError("Ticket title is required.")

        ticket_id = self._new_id("otk")
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        row = {
            "ticket_id": ticket_id,
            "offering_id": offering_id,
            "vendor_id": vendor_id,
            "ticket_system": str(ticket_system or "").strip() or None,
            "external_ticket_id": str(external_ticket_id or "").strip() or None,
            "title": clean_title,
            "status": clean_status,
            "priority": str(priority or "").strip().lower() or None,
            "opened_date": str(opened_date or "").strip() or None,
            "closed_date": None,
            "notes": str(notes or "").strip() or None,
            "active_flag": True,
            "created_at": now.isoformat(),
            "created_by": actor_ref,
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }

        if self.config.use_mock:
            self._mock_new_offering_tickets.append(row)
            self._write_audit_entity_change(
                entity_name="app_offering_ticket",
                entity_id=ticket_id,
                action_type="insert",
                actor_user_principal=actor_user_principal,
                before_json=None,
                after_json=row,
                request_id=None,
            )
            return ticket_id

        self._ensure_local_offering_extension_tables()
        self._execute_file(
            "inserts/create_offering_ticket.sql",
            params=(
                ticket_id,
                offering_id,
                vendor_id,
                row["ticket_system"],
                row["external_ticket_id"],
                clean_title,
                clean_status,
                row["priority"],
                row["opened_date"],
                row["closed_date"],
                row["notes"],
                True,
                now,
                actor_ref,
                now,
                actor_ref,
            ),
            app_offering_ticket=self._table("app_offering_ticket"),
        )
        self._write_audit_entity_change(
            entity_name="app_offering_ticket",
            entity_id=ticket_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return ticket_id

    def update_offering_ticket(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        ticket_id: str,
        actor_user_principal: str,
        updates: dict[str, Any],
        reason: str,
    ) -> dict[str, str]:
        if not reason.strip():
            raise ValueError("Reason is required.")
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to this vendor.")

        allowed = {
            "ticket_system",
            "external_ticket_id",
            "title",
            "status",
            "priority",
            "opened_date",
            "closed_date",
            "notes",
        }
        clean_updates = {k: v for k, v in updates.items() if k in allowed}
        if not clean_updates:
            raise ValueError("No ticket fields were provided.")

        if self.config.use_mock:
            rows = self._mock_offering_tickets_df()
            match = rows[rows["ticket_id"].astype(str) == str(ticket_id)] if not rows.empty else pd.DataFrame()
        else:
            self._ensure_local_offering_extension_tables()
            match = self._query_file(
                "ingestion/select_offering_ticket_by_id.sql",
                params=(ticket_id, offering_id, vendor_id),
                columns=[
                    "ticket_id",
                    "offering_id",
                    "vendor_id",
                    "ticket_system",
                    "external_ticket_id",
                    "title",
                    "status",
                    "priority",
                    "opened_date",
                    "closed_date",
                    "notes",
                    "active_flag",
                    "created_at",
                    "created_by",
                    "updated_at",
                    "updated_by",
                ],
                app_offering_ticket=self._table("app_offering_ticket"),
            )

        if match.empty:
            raise ValueError("Ticket not found for this offering.")
        current = match.iloc[0].to_dict()
        before = dict(current)
        after = dict(current)
        after.update(clean_updates)
        request_id = str(uuid.uuid4())
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        clean_updates["updated_at"] = now.isoformat()
        clean_updates["updated_by"] = actor_ref

        if self.config.use_mock:
            self._mock_offering_ticket_overrides[ticket_id] = {
                **self._mock_offering_ticket_overrides.get(ticket_id, {}),
                **clean_updates,
            }
        else:
            set_clause = ", ".join([f"{key} = %s" for key in clean_updates.keys() if key not in {"updated_at", "updated_by"}])
            params = [clean_updates[key] for key in clean_updates.keys() if key not in {"updated_at", "updated_by"}]
            self._execute_file(
                "updates/update_offering_ticket.sql",
                params=tuple(params + [now, actor_ref, ticket_id, offering_id, vendor_id]),
                app_offering_ticket=self._table("app_offering_ticket"),
                set_clause=set_clause,
            )

        after.update(clean_updates)
        change_event_id = self._write_audit_entity_change(
            entity_name="app_offering_ticket",
            entity_id=ticket_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
        return {"request_id": request_id, "change_event_id": change_event_id}

    def list_offering_notes(self, offering_id: str, note_type: str | None = None) -> pd.DataFrame:
        normalized_type = str(note_type or "").strip().lower()
        if self.config.use_mock:
            rows = self._mock_offering_notes_df()
            if rows.empty:
                return rows
            rows = rows[rows["entity_id"].astype(str) == str(offering_id)].copy()
            if normalized_type:
                rows = rows[rows["note_type"].astype(str).str.lower() == normalized_type].copy()
            if "created_at" in rows.columns:
                rows = rows.sort_values("created_at", ascending=False)
            return self._decorate_user_columns(rows, ["created_by"])

        note_type_clause = "AND lower(note_type) = lower(%s)" if normalized_type else ""
        params: tuple[Any, ...] = (offering_id, normalized_type) if normalized_type else (offering_id,)
        rows = self._query_file(
            "ingestion/select_offering_notes.sql",
            params=params,
            columns=["note_id", "entity_name", "entity_id", "note_type", "note_text", "created_at", "created_by"],
            note_type_clause=note_type_clause,
            app_note=self._table("app_note"),
        )
        return self._decorate_user_columns(rows, ["created_by"])

    def add_offering_note(
        self,
        *,
        vendor_id: str,
        offering_id: str,
        note_type: str,
        note_text: str,
        actor_user_principal: str,
    ) -> str:
        if not self.offering_belongs_to_vendor(vendor_id, offering_id):
            raise ValueError("Offering does not belong to this vendor.")
        clean_note_type = str(note_type or "").strip().lower() or "general"
        clean_note_text = str(note_text or "").strip()
        if not clean_note_text:
            raise ValueError("Note text is required.")

        note_id = self._new_id("ont")
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        row = {
            "note_id": note_id,
            "entity_name": "offering",
            "entity_id": offering_id,
            "note_type": clean_note_type,
            "note_text": clean_note_text,
            "created_at": now.isoformat(),
            "created_by": actor_ref,
        }
        if self.config.use_mock:
            self._mock_new_offering_notes.append(row)
            self._write_audit_entity_change(
                entity_name="app_note",
                entity_id=note_id,
                action_type="insert",
                actor_user_principal=actor_user_principal,
                before_json=None,
                after_json=row,
                request_id=None,
            )
            return note_id

        self._execute_file(
            "inserts/add_offering_note.sql",
            params=(
                note_id,
                "offering",
                offering_id,
                clean_note_type,
                clean_note_text,
                now,
                actor_ref,
            ),
            app_note=self._table("app_note"),
        )
        self._write_audit_entity_change(
            entity_name="app_note",
            entity_id=note_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return note_id

    def get_offering_activity(self, vendor_id: str, offering_id: str) -> pd.DataFrame:
        if self.config.use_mock:
            events = self._mock_audit_changes_df().copy()
            data_flow_rows = self.list_offering_data_flows(vendor_id, offering_id)
            ticket_rows = self.list_offering_tickets(vendor_id, offering_id)
            note_rows = self.list_offering_notes(offering_id)
            doc_rows = self.list_docs("offering", offering_id)
            data_flow_ids = (
                data_flow_rows["data_flow_id"].astype(str).tolist()
                if not data_flow_rows.empty and "data_flow_id" in data_flow_rows.columns
                else []
            )
            ticket_ids = (
                ticket_rows["ticket_id"].astype(str).tolist()
                if not ticket_rows.empty and "ticket_id" in ticket_rows.columns
                else []
            )
            note_ids = (
                note_rows["note_id"].astype(str).tolist()
                if not note_rows.empty and "note_id" in note_rows.columns
                else []
            )
            doc_ids = doc_rows["doc_id"].astype(str).tolist() if not doc_rows.empty and "doc_id" in doc_rows.columns else []
            ids = {str(offering_id), *data_flow_ids, *ticket_ids, *note_ids, *doc_ids}
            filtered = events[events["entity_id"].astype(str).isin(ids)].copy()
            if "event_ts" in filtered.columns:
                filtered = filtered.sort_values("event_ts", ascending=False)
            filtered = self._with_audit_change_summaries(filtered)
            return self._decorate_user_columns(filtered, ["actor_user_principal"])

        self._ensure_local_offering_extension_tables()
        out = self._query_file(
            "ingestion/select_offering_activity.sql",
            params=(offering_id, offering_id, offering_id, offering_id, offering_id),
            columns=[
                "change_event_id",
                "entity_name",
                "entity_id",
                "action_type",
                "before_json",
                "after_json",
                "event_ts",
                "actor_user_principal",
                "request_id",
            ],
            audit_entity_change=self._table("audit_entity_change"),
            app_offering_data_flow=self._table("app_offering_data_flow"),
            app_offering_ticket=self._table("app_offering_ticket"),
            app_note=self._table("app_note"),
            app_document_link=self._table("app_document_link"),
        )
        out = self._with_audit_change_summaries(out)
        return self._decorate_user_columns(out, ["actor_user_principal"])

    def offering_belongs_to_vendor(self, vendor_id: str, offering_id: str) -> bool:
        if not offering_id:
            return False
        if self.config.use_mock:
            return self.get_offering_record(vendor_id, offering_id) is not None
        check = self._query_file(
            "ingestion/select_offering_belongs_to_vendor.sql",
            params=(vendor_id, offering_id),
            columns=["present"],
            core_vendor_offering=self._table("core_vendor_offering"),
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

        self._execute_file(
            "inserts/create_vendor_profile.sql",
            params=(
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
            core_vendor=self._table("core_vendor"),
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
        lob: str | None = None,
        service_type: str | None = None,
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
            "lob": (lob or "").strip() or None,
            "service_type": (service_type or "").strip() or None,
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

        self._ensure_local_offering_columns()
        self._execute_file(
            "inserts/create_offering.sql",
            params=(
                offering_id,
                vendor_id,
                row["offering_name"],
                row["offering_type"],
                row["lob"],
                row["service_type"],
                row["lifecycle_state"],
                row["criticality_tier"],
            ),
            core_vendor_offering=self._table("core_vendor_offering"),
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
        allowed = {"offering_name", "offering_type", "lob", "service_type", "lifecycle_state", "criticality_tier"}
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
        self._ensure_local_offering_columns()
        self._execute_file(
            "updates/update_offering_fields.sql",
            params=tuple(params),
            core_vendor_offering=self._table("core_vendor_offering"),
            set_clause=set_clause,
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

        self._execute_file(
            "updates/map_contract_to_offering.sql",
            params=(offering_id, self._now(), actor_user_principal, contract_id, vendor_id),
            core_contract=self._table("core_contract"),
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

        self._execute_file(
            "updates/map_demo_to_offering.sql",
            params=(offering_id, self._now(), actor_user_principal, demo_id, vendor_id),
            core_vendor_demo=self._table("core_vendor_demo"),
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

    def add_vendor_owner(
        self,
        *,
        vendor_id: str,
        owner_user_principal: str,
        owner_role: str,
        actor_user_principal: str,
    ) -> str:
        if self.get_vendor_profile(vendor_id).empty:
            raise ValueError("Vendor not found.")
        owner_principal = owner_user_principal.strip()
        if not owner_principal:
            raise ValueError("Owner principal is required.")
        owner_role_options = self.list_owner_role_options() or ["business_owner"]
        owner_role_value = self._normalize_choice(
            owner_role,
            field_name="Owner role",
            allowed=set(owner_role_options),
            default=owner_role_options[0],
        )
        owner_id = self._new_id("vown")
        now = self._now()
        row = {
            "vendor_owner_id": owner_id,
            "vendor_id": vendor_id,
            "owner_user_principal": owner_principal,
            "owner_role": owner_role_value,
            "active_flag": True,
            "updated_at": now.isoformat(),
            "updated_by": actor_user_principal,
        }
        if self.config.use_mock:
            self._mock_new_vendor_owners.append(row)
            self._write_audit_entity_change(
                entity_name="core_vendor_business_owner",
                entity_id=owner_id,
                action_type="insert",
                actor_user_principal=actor_user_principal,
                before_json=None,
                after_json=row,
                request_id=None,
            )
            return owner_id

        self._execute_file(
            "inserts/add_vendor_owner.sql",
            params=(
                owner_id,
                vendor_id,
                row["owner_user_principal"],
                row["owner_role"],
                True,
                now,
                actor_user_principal,
            ),
            core_vendor_business_owner=self._table("core_vendor_business_owner"),
        )
        self._write_audit_entity_change(
            entity_name="core_vendor_business_owner",
            entity_id=owner_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return owner_id

    def add_vendor_org_assignment(
        self,
        *,
        vendor_id: str,
        org_id: str,
        assignment_type: str,
        actor_user_principal: str,
    ) -> str:
        if self.get_vendor_profile(vendor_id).empty:
            raise ValueError("Vendor not found.")
        org_value = org_id.strip()
        if not org_value:
            raise ValueError("Org ID is required.")
        assignment_options = self.list_assignment_type_options() or ["consumer"]
        assignment_type_value = self._normalize_choice(
            assignment_type,
            field_name="Assignment type",
            allowed=set(assignment_options),
            default=assignment_options[0],
        )
        assignment_id = self._new_id("voa")
        now = self._now()
        row = {
            "vendor_org_assignment_id": assignment_id,
            "vendor_id": vendor_id,
            "org_id": org_value,
            "assignment_type": assignment_type_value,
            "active_flag": True,
            "updated_at": now.isoformat(),
            "updated_by": actor_user_principal,
        }
        if self.config.use_mock:
            self._mock_new_vendor_org_assignments.append(row)
            self._write_audit_entity_change(
                entity_name="core_vendor_org_assignment",
                entity_id=assignment_id,
                action_type="insert",
                actor_user_principal=actor_user_principal,
                before_json=None,
                after_json=row,
                request_id=None,
            )
            return assignment_id

        self._execute_file(
            "inserts/add_vendor_org_assignment.sql",
            params=(
                assignment_id,
                vendor_id,
                row["org_id"],
                row["assignment_type"],
                True,
                now,
                actor_user_principal,
            ),
            core_vendor_org_assignment=self._table("core_vendor_org_assignment"),
        )
        self._write_audit_entity_change(
            entity_name="core_vendor_org_assignment",
            entity_id=assignment_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return assignment_id

    def add_vendor_contact(
        self,
        *,
        vendor_id: str,
        full_name: str,
        contact_type: str,
        email: str | None,
        phone: str | None,
        actor_user_principal: str,
    ) -> str:
        if self.get_vendor_profile(vendor_id).empty:
            raise ValueError("Vendor not found.")
        contact_name = full_name.strip()
        if not contact_name:
            raise ValueError("Contact name is required.")
        contact_type_options = self.list_contact_type_options() or ["business"]
        contact_type_value = self._normalize_choice(
            contact_type,
            field_name="Contact type",
            allowed=set(contact_type_options),
            default=contact_type_options[0],
        )
        contact_id = self._new_id("con")
        now = self._now()
        row = {
            "vendor_contact_id": contact_id,
            "vendor_id": vendor_id,
            "contact_type": contact_type_value,
            "full_name": contact_name,
            "email": (email or "").strip() or None,
            "phone": (phone or "").strip() or None,
            "active_flag": True,
            "updated_at": now.isoformat(),
            "updated_by": actor_user_principal,
        }
        if self.config.use_mock:
            self._mock_new_vendor_contacts.append(row)
            self._write_audit_entity_change(
                entity_name="core_vendor_contact",
                entity_id=contact_id,
                action_type="insert",
                actor_user_principal=actor_user_principal,
                before_json=None,
                after_json=row,
                request_id=None,
            )
            return contact_id

        self._execute_file(
            "inserts/add_vendor_contact.sql",
            params=(
                contact_id,
                vendor_id,
                row["contact_type"],
                row["full_name"],
                row["email"],
                row["phone"],
                True,
                now,
                actor_user_principal,
            ),
            core_vendor_contact=self._table("core_vendor_contact"),
        )
        self._write_audit_entity_change(
            entity_name="core_vendor_contact",
            entity_id=contact_id,
            action_type="insert",
            actor_user_principal=actor_user_principal,
            before_json=None,
            after_json=row,
            request_id=None,
        )
        return contact_id

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
        owner_role_options = self.list_owner_role_options() or ["business_owner"]
        owner_role_value = self._normalize_choice(
            owner_role,
            field_name="Owner role",
            allowed=set(owner_role_options),
            default=owner_role_options[0],
        )
        owner_id = self._new_id("oown")
        row = {
            "offering_owner_id": owner_id,
            "offering_id": offering_id,
            "owner_user_principal": owner_user_principal.strip(),
            "owner_role": owner_role_value,
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

        self._execute_file(
            "inserts/add_offering_owner.sql",
            params=(owner_id, offering_id, row["owner_user_principal"], row["owner_role"], True),
            core_offering_business_owner=self._table("core_offering_business_owner"),
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
            self._execute_file(
                "updates/remove_offering_owner_soft.sql",
                params=(offering_owner_id, offering_id),
                core_offering_business_owner=self._table("core_offering_business_owner"),
            )
        except Exception:
            self._execute_file(
                "updates/remove_offering_owner_delete.sql",
                params=(offering_owner_id, offering_id),
                core_offering_business_owner=self._table("core_offering_business_owner"),
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
        contact_type_options = self.list_contact_type_options() or ["business"]
        contact_type_value = self._normalize_choice(
            contact_type,
            field_name="Contact type",
            allowed=set(contact_type_options),
            default=contact_type_options[0],
        )
        contact_id = self._new_id("ocon")
        row = {
            "offering_contact_id": contact_id,
            "offering_id": offering_id,
            "contact_type": contact_type_value,
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

        self._execute_file(
            "inserts/add_offering_contact.sql",
            params=(contact_id, offering_id, row["contact_type"], row["full_name"], row["email"], row["phone"], True),
            core_offering_contact=self._table("core_offering_contact"),
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
            self._execute_file(
                "updates/remove_offering_contact_soft.sql",
                params=(offering_contact_id, offering_id),
                core_offering_contact=self._table("core_offering_contact"),
            )
        except Exception:
            self._execute_file(
                "updates/remove_offering_contact_delete.sql",
                params=(offering_contact_id, offering_id),
                core_offering_contact=self._table("core_offering_contact"),
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
                " OR lower(coalesce(p.description, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.display_name, '')) LIKE lower(%s)"
                ")"
            )
            like = f"%{search_text.strip()}%"
            params.extend([like, like, like, like, like, like])

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
        if self.config.use_mock:
            offerings = self._mock_offerings_df()
        else:
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
                actor_user_principal,
                now,
                actor_user_principal,
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
                    actor_user_principal,
                    now,
                    actor_user_principal,
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
                    actor_user_principal,
                    now,
                    actor_user_principal,
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
            if self.config.use_mock:
                offerings = self._mock_offerings_df()
            else:
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
            self._execute_file(
                "updates/update_project.sql",
                params=tuple(params),
                app_project=self._table("app_project"),
                set_clause=set_clause,
            )
        if target_vendor_ids is not None:
            try:
                self._execute_file(
                    "updates/update_project_vendor_map_soft.sql",
                    params=(now, actor_user_principal, project_id),
                    app_project_vendor_map=self._table("app_project_vendor_map"),
                )
            except Exception:
                self._execute_file(
                    "updates/delete_project_vendor_map.sql",
                    params=(project_id,),
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
                        actor_user_principal,
                        now,
                        actor_user_principal,
                    ),
                    app_project_vendor_map=self._table("app_project_vendor_map"),
                )
        if target_offering_ids is not None:
            try:
                self._execute_file(
                    "updates/update_project_offering_map_soft.sql",
                    params=(now, actor_user_principal, project_id),
                    app_project_offering_map=self._table("app_project_offering_map"),
                )
            except Exception:
                self._execute_file(
                    "updates/delete_project_offering_map.sql",
                    params=(project_id,),
                    app_project_offering_map=self._table("app_project_offering_map"),
                )
            if self.config.use_mock:
                offerings = self._mock_offerings_df()
            else:
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
                        actor_user_principal,
                        now,
                        actor_user_principal,
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
        return self._query_file(
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
                actor_user_principal,
                now,
                actor_user_principal,
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
            self._execute_file(
                "updates/remove_project_demo_soft.sql",
                params=(self._now(), actor_user_principal, project_demo_id, project_id, vendor_id),
                app_project_demo=self._table("app_project_demo"),
            )
        except Exception:
            self._execute_file(
                "updates/remove_project_demo_delete.sql",
                params=(project_demo_id, project_id, vendor_id),
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
        return self._query_file(
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

        self._execute_file(
            "inserts/add_project_note.sql",
            params=(
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
            filtered = self._with_audit_change_summaries(filtered)
            return self._decorate_user_columns(filtered, ["actor_user_principal"])

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

    def get_doc_link(self, doc_id: str) -> dict[str, Any] | None:
        if self.config.use_mock:
            docs = self._mock_doc_links_df()
            matched = docs[docs["doc_id"].astype(str) == str(doc_id)]
            if matched.empty:
                return None
            row = matched.iloc[0].to_dict()
            row["doc_fqdn"] = re.sub(r"^https?://", "", str(row.get("doc_url") or "")).split("/", 1)[0].lower()
            return row
        rows = self._query_file(
            "ingestion/select_doc_link_by_id.sql",
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
            app_document_link=self._table("app_document_link"),
        )
        if rows.empty:
            return None
        row = rows.iloc[0].to_dict()
        row["doc_fqdn"] = re.sub(r"^https?://", "", str(row.get("doc_url") or "")).split("/", 1)[0].lower()
        return row

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
            if "doc_url" in docs.columns:
                docs["doc_fqdn"] = docs["doc_url"].fillna("").astype(str).str.extract(r"https?://([^/]+)", expand=False).fillna("").str.lower()
            return docs
        out = self._query_file(
            "ingestion/select_docs_by_entity.sql",
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
            app_document_link=self._table("app_document_link"),
        )
        if not out.empty and "doc_url" in out.columns:
            out["doc_fqdn"] = out["doc_url"].fillna("").astype(str).str.extract(r"https?://([^/]+)", expand=False).fillna("").str.lower()
        return out

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
        doc_fqdn: str | None = None,
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
        clean_fqdn = (doc_fqdn or "").strip().lower()
        clean_owner = (owner or "").strip()
        if not clean_owner:
            clean_owner = str(actor_user_principal or "").strip()
        resolved_owner = self.resolve_user_login_identifier(clean_owner)
        if not resolved_owner:
            raise ValueError("Owner must exist in the app user directory.")

        doc_id = self._new_id("doc")
        now = self._now()
        row = {
            "doc_id": doc_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "doc_title": clean_title,
            "doc_url": clean_url,
            "doc_type": clean_type,
            "doc_fqdn": clean_fqdn or None,
            "tags": (tags or "").strip() or None,
            "owner": resolved_owner,
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

        self._execute_file(
            "inserts/create_doc_link.sql",
            params=(
                doc_id,
                entity_type,
                entity_id,
                clean_title,
                clean_url,
                clean_type,
                row["tags"],
                resolved_owner,
                True,
                now,
                actor_user_principal,
                now,
                actor_user_principal,
            ),
            app_document_link=self._table("app_document_link"),
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
        if "owner" in clean_updates:
            resolved_owner = self.resolve_user_login_identifier(str(clean_updates.get("owner") or "").strip())
            if not resolved_owner:
                raise ValueError("Owner must exist in the app user directory.")
            clean_updates["owner"] = resolved_owner
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
        self._execute_file(
            "updates/update_doc_link.sql",
            params=tuple(params),
            app_document_link=self._table("app_document_link"),
            set_clause=set_clause,
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
            self._execute_file(
                "updates/remove_doc_link_soft.sql",
                params=(self._now(), actor_user_principal, doc_id),
                app_document_link=self._table("app_document_link"),
            )
        except Exception:
            self._execute_file(
                "updates/remove_doc_link_delete.sql",
                params=(doc_id,),
                app_document_link=self._table("app_document_link"),
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
        change_type_clean = (change_type or "").strip().lower()
        vendor_id_clean = str(vendor_id or "").strip() or GLOBAL_CHANGE_VENDOR_ID
        payload_clean = self._prepare_change_request_payload(change_type_clean, payload or {})
        requestor_ref = self._actor_ref(requestor_user_principal)

        if self.config.use_mock:
            self._mock_change_request_overrides.append(
                {
                    "change_request_id": request_id,
                    "vendor_id": vendor_id_clean,
                    "requestor_user_principal": requestor_ref,
                    "change_type": change_type_clean,
                    "requested_payload_json": self._serialize_payload(payload_clean),
                    "status": "submitted",
                    "submitted_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            )
            self._write_audit_entity_change(
                entity_name="app_vendor_change_request",
                entity_id=request_id,
                action_type="insert",
                actor_user_principal=requestor_ref,
                before_json=None,
                after_json={
                    "vendor_id": vendor_id_clean,
                    "change_type": change_type_clean,
                    "status": "submitted",
                },
                request_id=request_id,
            )
            return request_id

        try:
            self._execute_file(
                "inserts/create_vendor_change_request.sql",
                params=(
                    request_id,
                    vendor_id_clean,
                    requestor_ref,
                    change_type_clean,
                    self._serialize_payload(payload_clean),
                    "submitted",
                    now,
                    now,
                ),
                app_vendor_change_request=self._table("app_vendor_change_request"),
            )
        except Exception as exc:
            raise RuntimeError("Could not persist change request.") from exc

        try:
            self._execute_file(
                "inserts/create_workflow_event.sql",
                params=(
                    str(uuid.uuid4()),
                    "vendor_change_request",
                    request_id,
                    None,
                    "submitted",
                    requestor_ref,
                    now,
                    f"{change_type_clean} request created",
                ),
                audit_workflow_event=self._table("audit_workflow_event"),
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
        actor_ref = self._actor_ref(actor_user_principal)
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
                    "requestor_user_principal": actor_ref,
                    "change_type": "direct_update_vendor_profile",
                    "requested_payload_json": self._serialize_payload({"updates": clean_updates, "reason": reason}),
                    "status": "approved",
                    "submitted_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            )
            change_event_id = self._write_audit_entity_change(
                entity_name="core_vendor",
                entity_id=vendor_id,
                action_type="update",
                actor_user_principal=actor_ref,
                before_json=old_row,
                after_json=new_row,
                request_id=request_id,
            )
            self.log_usage_event(
                user_principal=actor_user_principal,
                page_name="vendor_360",
                event_type="vendor_profile_update_applied",
                payload={"vendor_id": vendor_id, "request_id": request_id, "reason": reason},
            )
            return {"request_id": request_id, "change_event_id": change_event_id}

        existing = self._query_file(
            "ingestion/select_vendor_profile_by_id.sql",
            params=(vendor_id,),
            columns=[],
            core_vendor=self._table("core_vendor"),
        )
        if existing.empty:
            raise ValueError("Vendor not found.")
        old_row = existing.iloc[0].to_dict()

        # Create and immediately approve a change request so all direct edits remain traceable.
        try:
            self._execute_file(
                "inserts/create_vendor_change_request.sql",
                params=(
                    request_id,
                    vendor_id,
                    actor_ref,
                    "direct_update_vendor_profile",
                    self._serialize_payload({"updates": clean_updates, "reason": reason}),
                    "approved",
                    now,
                    now,
                ),
                app_vendor_change_request=self._table("app_vendor_change_request"),
            )
            self._execute_file(
                "inserts/create_workflow_event.sql",
                params=(
                    str(uuid.uuid4()),
                    "vendor_change_request",
                    request_id,
                    "submitted",
                    "approved",
                    actor_ref,
                    now,
                    "Direct vendor profile update approved and applied.",
                ),
                audit_workflow_event=self._table("audit_workflow_event"),
            )
        except Exception:
            # Continue to apply update even if app workflow tables are unavailable.
            pass

        set_clause = ", ".join([f"{field} = %s" for field in clean_updates.keys()])
        params = list(clean_updates.values()) + [now, actor_user_principal, vendor_id]
        self._execute_file(
            "updates/apply_vendor_profile_update.sql",
            params=tuple(params),
            core_vendor=self._table("core_vendor"),
            set_clause=set_clause,
        )

        updated = self._query_file(
            "ingestion/select_vendor_profile_by_id.sql",
            params=(vendor_id,),
            columns=[],
            core_vendor=self._table("core_vendor"),
        )
        new_row = updated.iloc[0].to_dict() if not updated.empty else {**old_row, **clean_updates}

        # Maintain SCD-style vendor history.
        try:
            version_df = self._query_file(
                "ingestion/select_next_hist_vendor_version.sql",
                params=(vendor_id,),
                columns=["next_version"],
                hist_vendor=self._table("hist_vendor"),
            )
            next_version = int(version_df.iloc[0]["next_version"]) if not version_df.empty else 1

            self._execute_file(
                "updates/apply_vendor_hist_close_current.sql",
                params=(now, vendor_id),
                hist_vendor=self._table("hist_vendor"),
            )
            self._execute_file(
                "inserts/apply_vendor_hist_insert.sql",
                params=(
                    str(uuid.uuid4()),
                    vendor_id,
                    next_version,
                    now,
                    None,
                    True,
                    json.dumps(new_row, default=str),
                    actor_ref,
                    reason,
                ),
                hist_vendor=self._table("hist_vendor"),
            )
        except Exception:
            pass

        try:
            self._execute_file(
                "inserts/audit_entity_change.sql",
                params=(
                    change_event_id,
                    "core_vendor",
                    vendor_id,
                    "update",
                    json.dumps(old_row, default=str),
                    json.dumps(new_row, default=str),
                    actor_ref,
                    now,
                    request_id,
                ),
                audit_entity_change=self._table("audit_entity_change"),
            )
        except Exception:
            pass

        return {"request_id": request_id, "change_event_id": change_event_id}

    def demo_outcomes(self) -> pd.DataFrame:
        if self.config.use_mock:
            return self._mock_demos_df()
        return self.client.query(
            self._sql(
                "reporting/demo_outcomes.sql",
                core_vendor_demo=self._table("core_vendor_demo"),
            )
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
        actor_ref = self._actor_ref(actor_user_principal)
        if self.config.use_mock:
            return demo_id

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

    def contract_cancellations(self) -> pd.DataFrame:
        if self.config.use_mock:
            return mock_data.contract_cancellations()
        return self.client.query(
            self._sql(
                "reporting/contract_cancellations.sql",
                rpt_contract_cancellations=self._table("rpt_contract_cancellations"),
            )
        )

    @staticmethod
    def _lookup_columns() -> list[str]:
        return [
            "option_id",
            "lookup_type",
            "option_code",
            "option_label",
            "sort_order",
            "active_flag",
            "valid_from_ts",
            "valid_to_ts",
            "is_current",
            "deleted_flag",
            "updated_at",
            "updated_by",
        ]

    def _lookup_versions_frame(self, lookup_type: str | None = None) -> pd.DataFrame:
        columns = self._lookup_columns()
        normalized_lookup_type = self._normalize_lookup_type(lookup_type) if lookup_type else None
        default_rows = [
            row
            for row in self._default_lookup_option_rows()
            if not normalized_lookup_type or str(row.get("lookup_type") or "") == normalized_lookup_type
        ]

        if self.config.use_mock:
            records = [
                dict(row)
                for row in self._mock_lookup_options
                if not normalized_lookup_type or str(row.get("lookup_type") or "") == normalized_lookup_type
            ]
            if not records:
                records = [dict(row) for row in default_rows]
            out = pd.DataFrame(records, columns=columns)
        else:
            self._ensure_local_lookup_option_table()
            rows = self._query_file(
                "reporting/list_lookup_options.sql",
                params=(normalized_lookup_type, normalized_lookup_type),
                columns=columns,
                app_lookup_option=self._table("app_lookup_option"),
            )
            records = rows.to_dict("records")
            if not records:
                records = [dict(row) for row in default_rows]
            out = pd.DataFrame(records, columns=columns)

        if out.empty:
            return out
        out["sort_order"] = pd.to_numeric(out["sort_order"], errors="coerce").fillna(999).astype(int)
        if "active_flag" not in out.columns:
            out["active_flag"] = True
        if "is_current" not in out.columns:
            out["is_current"] = True
        if "deleted_flag" not in out.columns:
            out["deleted_flag"] = False
        out["active_flag"] = out["active_flag"].map(self._as_bool)
        out["is_current"] = out["is_current"].map(self._as_bool)
        out["deleted_flag"] = out["deleted_flag"].map(self._as_bool)
        return out.reset_index(drop=True)

    def _lookup_rows_with_status(self, rows: pd.DataFrame, *, as_of_ts: Any) -> pd.DataFrame:
        if rows.empty:
            out = rows.copy()
            out["status"] = pd.Series(dtype="object")
            return out

        as_of = self._parse_lookup_ts(as_of_ts, fallback=self._now())
        statuses: list[str] = []
        normalized_from: list[str] = []
        normalized_to: list[str] = []
        for row in rows.to_dict("records"):
            start, end = self._normalize_lookup_window(row.get("valid_from_ts"), row.get("valid_to_ts"))
            statuses.append(self._lookup_status_for_window(start, end, as_of=as_of))
            normalized_from.append(start.isoformat())
            normalized_to.append(end.isoformat())
        out = rows.copy()
        out["status"] = statuses
        out["valid_from_ts"] = normalized_from
        out["valid_to_ts"] = normalized_to
        return out

    def list_lookup_option_versions(
        self,
        lookup_type: str,
        *,
        as_of_ts: Any = None,
        status_filter: str = "all",
        include_deleted: bool = False,
    ) -> pd.DataFrame:
        lookup_key = self._normalize_lookup_type(lookup_type)
        out = self._lookup_versions_frame(lookup_key)
        if out.empty:
            return pd.DataFrame(columns=self._lookup_columns() + ["status"])
        out = out[out["is_current"]].copy()
        if not include_deleted:
            out = out[~out["deleted_flag"]].copy()
        out = self._lookup_rows_with_status(out, as_of_ts=as_of_ts)
        filter_value = str(status_filter or "all").strip().lower()
        if filter_value in {"active", "historical", "future"}:
            out = out[out["status"].astype(str) == filter_value].copy()
        return out.sort_values(
            ["sort_order", "option_label", "valid_from_ts", "option_code"],
            kind="stable",
        ).reset_index(drop=True)

    def list_lookup_options(
        self,
        lookup_type: str | None = None,
        *,
        active_only: bool = False,
        as_of_ts: Any = None,
    ) -> pd.DataFrame:
        out = self._lookup_versions_frame(lookup_type)
        if out.empty:
            return out
        out = out[out["is_current"]].copy()
        out = out[~out["deleted_flag"]].copy()
        out = self._lookup_rows_with_status(out, as_of_ts=as_of_ts)
        if active_only:
            out = out[out["status"].astype(str) == "active"].copy()
        return out.sort_values(
            ["lookup_type", "sort_order", "option_label", "option_code"],
            kind="stable",
        ).reset_index(drop=True)

    def list_doc_source_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_DOC_SOURCE, active_only=True)
        if rows.empty:
            return list(DEFAULT_DOC_SOURCE_OPTIONS)
        values: list[str] = []
        seen: set[str] = set()
        for raw in rows["option_code"].tolist():
            value = str(raw).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values or list(DEFAULT_DOC_SOURCE_OPTIONS)

    def list_doc_tag_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_DOC_TAG, active_only=True)
        if rows.empty:
            return list(DEFAULT_DOC_TAG_OPTIONS)
        values: list[str] = []
        seen: set[str] = set()
        for raw in rows["option_code"].tolist():
            value = str(raw).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values or list(DEFAULT_DOC_TAG_OPTIONS)

    def list_owner_role_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_OWNER_ROLE, active_only=True)
        if rows.empty:
            return list(DEFAULT_OWNER_ROLE_OPTIONS)
        values: list[str] = []
        seen: set[str] = set()
        for raw in rows["option_code"].tolist():
            value = str(raw).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values or list(DEFAULT_OWNER_ROLE_OPTIONS)

    def list_assignment_type_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_ASSIGNMENT_TYPE, active_only=True)
        if rows.empty:
            return list(DEFAULT_ASSIGNMENT_TYPE_OPTIONS)
        values: list[str] = []
        seen: set[str] = set()
        for raw in rows["option_code"].tolist():
            value = str(raw).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values or list(DEFAULT_ASSIGNMENT_TYPE_OPTIONS)

    def list_contact_type_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_CONTACT_TYPE, active_only=True)
        if rows.empty:
            return list(DEFAULT_CONTACT_TYPE_OPTIONS)
        values: list[str] = []
        seen: set[str] = set()
        for raw in rows["option_code"].tolist():
            value = str(raw).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values or list(DEFAULT_CONTACT_TYPE_OPTIONS)

    def list_project_type_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_PROJECT_TYPE, active_only=True)
        if rows.empty:
            return list(DEFAULT_PROJECT_TYPE_OPTIONS)
        values: list[str] = []
        seen: set[str] = set()
        for raw in rows["option_code"].tolist():
            value = str(raw).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values or list(DEFAULT_PROJECT_TYPE_OPTIONS)

    def list_workflow_status_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_WORKFLOW_STATUS, active_only=True)
        if rows.empty:
            return list(DEFAULT_WORKFLOW_STATUS_OPTIONS)
        values: list[str] = []
        seen: set[str] = set()
        for raw in rows["option_code"].tolist():
            value = str(raw).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values or list(DEFAULT_WORKFLOW_STATUS_OPTIONS)

    def list_offering_type_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_OFFERING_TYPE, active_only=True)
        if rows.empty:
            return [label for _, label in DEFAULT_OFFERING_TYPE_CHOICES]
        out: list[str] = []
        for row in rows.to_dict("records"):
            label = str(row.get("option_label") or "").strip()
            code = str(row.get("option_code") or "").strip().lower()
            value = label or self._lookup_label_from_code(code)
            if value and value not in out:
                out.append(value)
        return out or [label for _, label in DEFAULT_OFFERING_TYPE_CHOICES]

    def list_offering_lob_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_OFFERING_LOB, active_only=True)
        if rows.empty:
            return [label for _, label in DEFAULT_OFFERING_LOB_CHOICES]
        out: list[str] = []
        for row in rows.to_dict("records"):
            label = str(row.get("option_label") or "").strip()
            code = str(row.get("option_code") or "").strip().lower()
            value = label or self._lookup_label_from_code(code)
            if value and value not in out:
                out.append(value)
        return out or [label for _, label in DEFAULT_OFFERING_LOB_CHOICES]

    def list_offering_service_type_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_OFFERING_SERVICE_TYPE, active_only=True)
        if rows.empty:
            return [label for _, label in DEFAULT_OFFERING_SERVICE_TYPE_CHOICES]
        out: list[str] = []
        for row in rows.to_dict("records"):
            label = str(row.get("option_label") or "").strip()
            code = str(row.get("option_code") or "").strip().lower()
            value = label or self._lookup_label_from_code(code)
            if value and value not in out:
                out.append(value)
        return out or [label for _, label in DEFAULT_OFFERING_SERVICE_TYPE_CHOICES]

    def save_lookup_option(
        self,
        *,
        option_id: str | None,
        lookup_type: str,
        option_code: str,
        option_label: str | None,
        sort_order: int,
        valid_from_ts: Any,
        valid_to_ts: Any,
        updated_by: str,
    ) -> None:
        lookup_key = self._normalize_lookup_type(lookup_type)
        code = self._normalize_lookup_code(option_code)
        label = str(option_label or "").strip() or self._lookup_label_from_code(code)
        safe_sort_order = max(1, int(sort_order or 1))
        start_ts, end_ts = self._normalize_lookup_window(valid_from_ts, valid_to_ts)
        now = self._now()
        actor_ref = self._actor_ref(updated_by)
        current_rows = self.list_lookup_options(lookup_key, active_only=False).to_dict("records")

        selected_row: dict[str, Any] | None = None
        selected_id = str(option_id or "").strip()
        if selected_id:
            selected_row = next(
                (row for row in current_rows if str(row.get("option_id") or "") == selected_id),
                None,
            )
            if selected_row is None:
                raise ValueError("The selected option is no longer available for update.")
        else:
            matching_code_rows = [
                row
                for row in current_rows
                if self._normalize_lookup_code(str(row.get("option_code") or "")) == code
            ]
            if len(matching_code_rows) == 1:
                selected_row = matching_code_rows[0]

        for row in current_rows:
            if selected_row and str(row.get("option_id") or "") == str(selected_row.get("option_id") or ""):
                continue
            row_label = str(row.get("option_label") or "").strip().lower()
            if row_label != label.lower():
                continue
            row_start, row_end = self._normalize_lookup_window(row.get("valid_from_ts"), row.get("valid_to_ts"))
            if self._lookup_windows_overlap(start_ts, end_ts, row_start, row_end):
                raise ValueError("Label already exists in the selected active window.")

        overlapping_rows: list[dict[str, Any]] = []
        for row in current_rows:
            if selected_row and str(row.get("option_id") or "") == str(selected_row.get("option_id") or ""):
                continue
            row_start, row_end = self._normalize_lookup_window(row.get("valid_from_ts"), row.get("valid_to_ts"))
            if self._lookup_windows_overlap(start_ts, end_ts, row_start, row_end):
                overlapping_rows.append(row)
        overlapping_rows.sort(
            key=lambda item: (
                int(item.get("sort_order") or 999),
                str(item.get("option_label") or "").lower(),
                str(item.get("option_id") or ""),
            )
        )

        target = {
            "option_id": str(selected_row.get("option_id") or "") if selected_row else "",
            "lookup_type": lookup_key,
            "option_code": code,
            "option_label": label,
            "sort_order": safe_sort_order,
            "active_flag": True,
            "valid_from_ts": start_ts.isoformat(),
            "valid_to_ts": end_ts.isoformat(),
            "is_current": True,
            "deleted_flag": False,
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }
        target_index = min(safe_sort_order, len(overlapping_rows) + 1) - 1
        ordered = [dict(item) for item in overlapping_rows]
        ordered.insert(target_index, target)
        for idx, row in enumerate(ordered, start=1):
            row["sort_order"] = idx

        rows_to_close: dict[str, dict[str, Any]] = {}
        rows_to_insert: list[dict[str, Any]] = []
        overlap_by_id = {str(row.get("option_id") or ""): row for row in overlapping_rows}

        for row in ordered:
            row_id = str(row.get("option_id") or "")
            if row_id and row_id in overlap_by_id:
                prior = overlap_by_id[row_id]
                if int(prior.get("sort_order") or 0) == int(row.get("sort_order") or 0):
                    continue
                rows_to_close[row_id] = prior
                rows_to_insert.append(
                    {
                        "lookup_type": lookup_key,
                        "option_code": self._normalize_lookup_code(str(prior.get("option_code") or "")),
                        "option_label": str(prior.get("option_label") or "").strip()
                        or self._lookup_label_from_code(str(prior.get("option_code") or "")),
                        "sort_order": int(row.get("sort_order") or 1),
                        "active_flag": True,
                        "valid_from_ts": str(prior.get("valid_from_ts") or start_ts.isoformat()),
                        "valid_to_ts": str(prior.get("valid_to_ts") or end_ts.isoformat()),
                        "is_current": True,
                        "deleted_flag": False,
                    }
                )
                continue

            if selected_row:
                prior = selected_row
                changed = (
                    self._normalize_lookup_code(str(prior.get("option_code") or "")) != code
                    or str(prior.get("option_label") or "").strip() != label
                    or int(prior.get("sort_order") or 0) != int(row.get("sort_order") or 0)
                    or str(prior.get("valid_from_ts") or "") != start_ts.isoformat()
                    or str(prior.get("valid_to_ts") or "") != end_ts.isoformat()
                )
                if not changed:
                    continue
                rows_to_close[str(prior.get("option_id") or "")] = prior
            rows_to_insert.append(
                {
                    "lookup_type": lookup_key,
                    "option_code": code,
                    "option_label": label,
                    "sort_order": int(row.get("sort_order") or 1),
                    "active_flag": True,
                    "valid_from_ts": start_ts.isoformat(),
                    "valid_to_ts": end_ts.isoformat(),
                    "is_current": True,
                    "deleted_flag": False,
                }
            )

        if not rows_to_close and not rows_to_insert:
            return

        if self.config.use_mock:
            for close_row in rows_to_close.values():
                close_id = str(close_row.get("option_id") or "")
                for entry in self._mock_lookup_options:
                    if str(entry.get("option_id") or "") != close_id:
                        continue
                    entry["is_current"] = False
                    entry["valid_to_ts"] = now.isoformat()
                    entry["updated_at"] = now.isoformat()
                    entry["updated_by"] = actor_ref
                    break
            for row in rows_to_insert:
                self._mock_lookup_options.append(
                    {
                        "option_id": f"lkp-{lookup_key}-{row['option_code']}-{uuid.uuid4().hex[:12]}",
                        "lookup_type": row["lookup_type"],
                        "option_code": row["option_code"],
                        "option_label": row["option_label"],
                        "sort_order": int(row["sort_order"]),
                        "active_flag": True,
                        "valid_from_ts": row["valid_from_ts"],
                        "valid_to_ts": row["valid_to_ts"],
                        "is_current": True,
                        "deleted_flag": False,
                        "updated_at": now.isoformat(),
                        "updated_by": actor_ref,
                    }
                )
            return

        self._ensure_local_lookup_option_table()
        for close_row in rows_to_close.values():
            self._execute_file(
                "updates/close_lookup_option_version.sql",
                params=(now, False, now, actor_ref, str(close_row.get("option_id") or "")),
                app_lookup_option=self._table("app_lookup_option"),
            )
        for row in rows_to_insert:
            self._execute_file(
                "inserts/create_lookup_option.sql",
                params=(
                    f"lkp-{lookup_key}-{row['option_code']}-{uuid.uuid4().hex[:12]}",
                    row["lookup_type"],
                    row["option_code"],
                    row["option_label"],
                    row["sort_order"],
                    row["active_flag"],
                    row["valid_from_ts"],
                    row["valid_to_ts"],
                    row["is_current"],
                    row["deleted_flag"],
                    now,
                    actor_ref,
                ),
                app_lookup_option=self._table("app_lookup_option"),
            )

    def delete_lookup_option(
        self,
        *,
        lookup_type: str,
        option_id: str,
        updated_by: str = "system",
    ) -> None:
        lookup_key = self._normalize_lookup_type(lookup_type)
        target_id = str(option_id or "").strip()
        if not target_id:
            raise ValueError("Lookup option id is required.")
        current_rows = self.list_lookup_options(lookup_key, active_only=False).to_dict("records")
        target = next((row for row in current_rows if str(row.get("option_id") or "") == target_id), None)
        if target is None:
            raise ValueError("The selected option is no longer available for removal.")
        now = self._now()
        actor_ref = self._actor_ref(updated_by)

        if self.config.use_mock:
            for row in self._mock_lookup_options:
                if str(row.get("option_id") or "") != target_id:
                    continue
                row["is_current"] = False
                row["valid_to_ts"] = now.isoformat()
                row["updated_at"] = now.isoformat()
                row["updated_by"] = actor_ref
                break
            self._mock_lookup_options.append(
                {
                    "option_id": f"lkp-{lookup_key}-{self._normalize_lookup_code(str(target.get('option_code') or 'removed'))}-{uuid.uuid4().hex[:12]}",
                    "lookup_type": lookup_key,
                    "option_code": self._normalize_lookup_code(str(target.get("option_code") or "removed")),
                    "option_label": str(target.get("option_label") or ""),
                    "sort_order": int(target.get("sort_order") or 999),
                    "active_flag": False,
                    "valid_from_ts": now.isoformat(),
                    "valid_to_ts": datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc).isoformat(),
                    "is_current": True,
                    "deleted_flag": True,
                    "updated_at": now.isoformat(),
                    "updated_by": actor_ref,
                }
            )
        else:
            self._ensure_local_lookup_option_table()
            self._execute_file(
                "updates/close_lookup_option_version.sql",
                params=(now, False, now, actor_ref, target_id),
                app_lookup_option=self._table("app_lookup_option"),
            )
            self._execute_file(
                "inserts/create_lookup_option.sql",
                params=(
                    f"lkp-{lookup_key}-{self._normalize_lookup_code(str(target.get('option_code') or 'removed'))}-{uuid.uuid4().hex[:12]}",
                    lookup_key,
                    self._normalize_lookup_code(str(target.get("option_code") or "removed")),
                    str(target.get("option_label") or ""),
                    int(target.get("sort_order") or 999),
                    False,
                    now,
                    datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
                    True,
                    True,
                    now,
                    actor_ref,
                ),
                app_lookup_option=self._table("app_lookup_option"),
            )

        target_start, target_end = self._normalize_lookup_window(
            target.get("valid_from_ts"),
            target.get("valid_to_ts"),
        )
        remaining = self.list_lookup_options(lookup_key, active_only=False).to_dict("records")
        overlapping: list[dict[str, Any]] = []
        for row in remaining:
            row_start, row_end = self._normalize_lookup_window(row.get("valid_from_ts"), row.get("valid_to_ts"))
            if self._lookup_windows_overlap(target_start, target_end, row_start, row_end):
                overlapping.append(row)
        overlapping.sort(
            key=lambda item: (
                int(item.get("sort_order") or 999),
                str(item.get("option_label") or "").lower(),
                str(item.get("option_id") or ""),
            )
        )
        rows_to_close: list[dict[str, Any]] = []
        rows_to_insert: list[dict[str, Any]] = []
        for idx, row in enumerate(overlapping, start=1):
            if int(row.get("sort_order") or 0) == idx:
                continue
            rows_to_close.append(row)
            rows_to_insert.append(
                {
                    "lookup_type": lookup_key,
                    "option_code": self._normalize_lookup_code(str(row.get("option_code") or "")),
                    "option_label": str(row.get("option_label") or "").strip()
                    or self._lookup_label_from_code(str(row.get("option_code") or "")),
                    "sort_order": idx,
                    "active_flag": True,
                    "valid_from_ts": str(row.get("valid_from_ts") or now.isoformat()),
                    "valid_to_ts": str(row.get("valid_to_ts") or datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc).isoformat()),
                    "is_current": True,
                    "deleted_flag": False,
                }
            )
        if self.config.use_mock:
            for close_row in rows_to_close:
                close_id = str(close_row.get("option_id") or "")
                for entry in self._mock_lookup_options:
                    if str(entry.get("option_id") or "") != close_id:
                        continue
                    entry["is_current"] = False
                    entry["valid_to_ts"] = now.isoformat()
                    entry["updated_at"] = now.isoformat()
                    entry["updated_by"] = actor_ref
                    break
            for row in rows_to_insert:
                self._mock_lookup_options.append(
                    {
                        "option_id": f"lkp-{lookup_key}-{row['option_code']}-{uuid.uuid4().hex[:12]}",
                        "lookup_type": row["lookup_type"],
                        "option_code": row["option_code"],
                        "option_label": row["option_label"],
                        "sort_order": int(row["sort_order"]),
                        "active_flag": True,
                        "valid_from_ts": row["valid_from_ts"],
                        "valid_to_ts": row["valid_to_ts"],
                        "is_current": True,
                        "deleted_flag": False,
                        "updated_at": now.isoformat(),
                        "updated_by": actor_ref,
                    }
                )
            return

        for close_row in rows_to_close:
            self._execute_file(
                "updates/close_lookup_option_version.sql",
                params=(now, False, now, actor_ref, str(close_row.get("option_id") or "")),
                app_lookup_option=self._table("app_lookup_option"),
            )
        for row in rows_to_insert:
            self._execute_file(
                "inserts/create_lookup_option.sql",
                params=(
                    f"lkp-{lookup_key}-{row['option_code']}-{uuid.uuid4().hex[:12]}",
                    row["lookup_type"],
                    row["option_code"],
                    row["option_label"],
                    row["sort_order"],
                    row["active_flag"],
                    row["valid_from_ts"],
                    row["valid_to_ts"],
                    row["is_current"],
                    row["deleted_flag"],
                    now,
                    actor_ref,
                ),
                app_lookup_option=self._table("app_lookup_option"),
            )

    def record_contract_cancellation(
        self, contract_id: str, reason_code: str, notes: str, actor_user_principal: str
    ) -> str:
        event_id = str(uuid.uuid4())
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        if self.config.use_mock:
            return event_id

        self._execute_file(
            "inserts/record_contract_cancellation_event.sql",
            params=(event_id, contract_id, "contract_cancelled", now, reason_code, notes, actor_ref),
            core_contract_event=self._table("core_contract_event"),
        )

        self._execute_file(
            "updates/record_contract_cancellation_contract_update.sql",
            params=("cancelled", True, now, actor_ref, contract_id),
            core_contract=self._table("core_contract"),
        )

        self._write_audit_entity_change(
            entity_name="core_contract",
            entity_id=contract_id,
            action_type="update",
            actor_user_principal=actor_ref,
            before_json=None,
            after_json={
                "contract_status": "cancelled",
                "cancelled_flag": True,
                "reason_code": reason_code,
                "notes": notes,
            },
            request_id=None,
        )
        return event_id

    def list_role_definitions(self) -> pd.DataFrame:
        columns = [
            "role_code",
            "role_name",
            "description",
            "approval_level",
            "can_edit",
            "can_report",
            "can_direct_apply",
            "active_flag",
            "updated_at",
            "updated_by",
        ]
        defaults = self._default_role_definition_rows()
        if self.config.use_mock:
            records = dict(defaults)
            records.update(self._mock_role_definitions)
            out = pd.DataFrame(list(records.values()))
            if out.empty:
                return pd.DataFrame(columns=columns)
            return out.sort_values("role_code")

        rows = self._query_file(
            "reporting/list_role_definitions.sql",
            columns=columns,
            sec_role_definition=self._table("sec_role_definition"),
        )
        records = dict(defaults)
        if not rows.empty:
            for row in rows.to_dict("records"):
                role_code = str(row.get("role_code") or "").strip()
                if not role_code:
                    continue
                records[role_code] = {
                    "role_code": role_code,
                    "role_name": str(row.get("role_name") or role_code),
                    "description": str(row.get("description") or "").strip() or None,
                    "approval_level": int(row.get("approval_level") or 0),
                    "can_edit": self._as_bool(row.get("can_edit")),
                    "can_report": self._as_bool(row.get("can_report")),
                    "can_direct_apply": self._as_bool(row.get("can_direct_apply")),
                    "active_flag": self._as_bool(row.get("active_flag")),
                    "updated_at": row.get("updated_at"),
                    "updated_by": row.get("updated_by"),
                }
        out = pd.DataFrame(list(records.values()))
        if out.empty:
            return pd.DataFrame(columns=columns)
        return out.sort_values("role_code")

    def list_role_permissions(self) -> pd.DataFrame:
        columns = ["role_code", "object_name", "action_code", "active_flag", "updated_at"]
        if self.config.use_mock:
            rows: list[dict[str, Any]] = []
            for role_code, actions in self._mock_role_permissions.items():
                for action_code in sorted(actions):
                    rows.append(
                        {
                            "role_code": role_code,
                            "object_name": "change_action",
                            "action_code": action_code,
                            "active_flag": True,
                            "updated_at": self._now().isoformat(),
                        }
                    )
            return pd.DataFrame(rows, columns=columns)

        out = self._query_file(
            "reporting/list_role_permissions.sql",
            columns=columns,
            sec_role_permission=self._table("sec_role_permission"),
        )
        if out.empty:
            rows: list[dict[str, Any]] = []
            for role_code, actions in self._default_role_permissions_by_role().items():
                for action_code in sorted(actions):
                    rows.append(
                        {
                            "role_code": role_code,
                            "object_name": "change_action",
                            "action_code": action_code,
                            "active_flag": True,
                            "updated_at": None,
                        }
                    )
            return pd.DataFrame(rows, columns=columns)
        return out

    def list_known_roles(self) -> list[str]:
        roles = set(self._default_role_definition_rows().keys())
        role_defs = self.list_role_definitions()
        if not role_defs.empty and "role_code" in role_defs.columns:
            roles.update(role_defs["role_code"].dropna().astype(str).tolist())

        if self.config.use_mock:
            base = mock_data.role_map()
            if not base.empty and "role_code" in base.columns:
                roles.update(base["role_code"].dropna().astype(str).tolist())
            for granted in self._mock_role_overrides.values():
                roles.update(granted)
            return sorted(role for role in roles if role)

        grants = self._query_file(
            "reporting/list_role_grants.sql",
            columns=["role_code"],
            sec_user_role_map=self._table("sec_user_role_map"),
        )
        if not grants.empty and "role_code" in grants.columns:
            roles.update(grants["role_code"].dropna().astype(str).tolist())
        return sorted(role for role in roles if role)

    def resolve_role_policy(self, user_roles: set[str]) -> dict[str, Any]:
        active_roles = {str(role).strip() for role in (user_roles or set()) if str(role).strip()}
        definitions = self.list_role_definitions()
        def_by_role: dict[str, dict[str, Any]] = {}
        for row in definitions.to_dict("records"):
            role_code = str(row.get("role_code") or "").strip()
            if not role_code:
                continue
            if not self._as_bool(row.get("active_flag", True)):
                continue
            def_by_role[role_code] = row

        selected_defs: list[dict[str, Any]] = []
        for role in active_roles:
            payload = def_by_role.get(role)
            if payload:
                selected_defs.append(payload)
                continue
            fallback = self._default_role_definition_rows().get(role)
            if fallback:
                selected_defs.append(fallback)

        if not selected_defs:
            selected_defs.append(self._default_role_definition_rows()[ROLE_VIEWER])

        approval_level = max(int(item.get("approval_level") or 0) for item in selected_defs)
        can_edit = any(self._as_bool(item.get("can_edit")) for item in selected_defs)
        can_report = any(self._as_bool(item.get("can_report")) for item in selected_defs)
        can_direct_apply = any(self._as_bool(item.get("can_direct_apply")) for item in selected_defs)
        can_submit_requests = can_edit or (ROLE_VIEWER in active_roles)
        can_approve_requests = bool(
            {ROLE_ADMIN, ROLE_APPROVER, ROLE_STEWARD}.intersection(active_roles)
        ) or (can_edit and int(approval_level) > 0)

        permissions = self.list_role_permissions()
        allowed_actions: set[str] = set()
        for row in permissions.to_dict("records"):
            role_code = str(row.get("role_code") or "").strip()
            if role_code not in active_roles:
                continue
            if not self._as_bool(row.get("active_flag", True)):
                continue
            object_name = str(row.get("object_name") or "change_action").strip().lower()
            if object_name not in {"change_action", "workflow", "app"}:
                continue
            action_code = str(row.get("action_code") or "").strip().lower()
            if action_code in CHANGE_APPROVAL_LEVELS:
                allowed_actions.add(action_code)

        if ROLE_ADMIN in active_roles:
            can_edit = True
            can_report = True
            can_direct_apply = True
            can_submit_requests = True
            can_approve_requests = True
            approval_level = max(approval_level, 3)
            allowed_actions = set(CHANGE_APPROVAL_LEVELS.keys())

        if ROLE_SYSTEM_ADMIN in active_roles and ROLE_ADMIN not in active_roles:
            can_edit = False
            can_direct_apply = False
            can_submit_requests = False
            can_approve_requests = False
            approval_level = 0

        if not allowed_actions:
            allowed_actions = {
                action for action, required in CHANGE_APPROVAL_LEVELS.items() if int(required) <= int(approval_level)
            }

        return {
            "roles": sorted(active_roles),
            "can_edit": bool(can_edit),
            "can_report": bool(can_report),
            "can_submit_requests": bool(can_submit_requests),
            "can_approve_requests": bool(can_approve_requests),
            "can_direct_apply": bool(can_direct_apply),
            "approval_level": int(approval_level),
            "allowed_change_actions": sorted(allowed_actions),
        }

    def save_role_definition(
        self,
        *,
        role_code: str,
        role_name: str,
        description: str | None,
        approval_level: int,
        can_edit: bool,
        can_report: bool,
        can_direct_apply: bool,
        updated_by: str,
    ) -> None:
        role_key = str(role_code or "").strip().lower()
        if not role_key:
            raise ValueError("Role code is required.")
        now = self._now()
        if self.config.use_mock:
            self._mock_role_definitions[role_key] = {
                "role_code": role_key,
                "role_name": str(role_name or role_key).strip() or role_key,
                "description": str(description or "").strip() or None,
                "approval_level": max(0, min(int(approval_level or 0), 3)),
                "can_edit": bool(can_edit),
                "can_report": bool(can_report),
                "can_direct_apply": bool(can_direct_apply),
                "active_flag": True,
                "updated_at": now.isoformat(),
                "updated_by": updated_by,
            }
            self._mock_role_permissions.setdefault(role_key, set())
            return

        self._execute_file(
            "updates/delete_role_definition_by_code.sql",
            params=(role_key,),
            sec_role_definition=self._table("sec_role_definition"),
        )
        self._execute_file(
            "inserts/create_role_definition.sql",
            params=(
                role_key,
                str(role_name or role_key).strip() or role_key,
                str(description or "").strip() or None,
                max(0, min(int(approval_level or 0), 3)),
                bool(can_edit),
                bool(can_report),
                bool(can_direct_apply),
                True,
                now,
                updated_by,
            ),
            sec_role_definition=self._table("sec_role_definition"),
        )

    def replace_role_permissions(self, *, role_code: str, action_codes: set[str], updated_by: str) -> None:
        role_key = str(role_code or "").strip().lower()
        if not role_key:
            raise ValueError("Role code is required.")
        normalized_actions = {
            str(action).strip().lower()
            for action in (action_codes or set())
            if str(action).strip().lower() in CHANGE_APPROVAL_LEVELS
        }
        if self.config.use_mock:
            self._mock_role_permissions[role_key] = set(normalized_actions)
            return

        self._execute_file(
            "updates/delete_role_permissions_by_role.sql",
            params=(role_key,),
            sec_role_permission=self._table("sec_role_permission"),
        )
        now = self._now()
        for action_code in sorted(normalized_actions):
            self._execute_file(
                "inserts/create_role_permission.sql",
                params=(role_key, "change_action", action_code, True, now),
                sec_role_permission=self._table("sec_role_permission"),
            )

    def list_role_grants(self) -> pd.DataFrame:
        columns = ["user_principal", "role_code", "active_flag", "granted_by", "granted_at", "revoked_at"]
        if self.config.use_mock:
            base = mock_data.role_map().copy()
            rows: list[dict[str, Any]] = []
            for user_principal, roles in self._mock_role_overrides.items():
                for role in roles:
                    rows.append(
                        {
                            "user_principal": user_principal,
                            "role_code": role,
                            "active_flag": True,
                            "granted_by": "mock-admin",
                            "granted_at": self._now().isoformat(),
                            "revoked_at": None,
                        }
                    )
            if rows:
                base = pd.concat([base, pd.DataFrame(rows)], ignore_index=True)
            if base.empty:
                return pd.DataFrame(columns=columns)
            base = base.drop_duplicates(subset=["user_principal", "role_code"], keep="last")
            return base[columns]
        return self._query_file(
            "reporting/list_role_grants.sql",
            columns=columns,
            sec_user_role_map=self._table("sec_user_role_map"),
        )

    def list_scope_grants(self) -> pd.DataFrame:
        if self.config.use_mock:
            base = mock_data.org_scope().copy()
            if self._mock_scope_overrides:
                base = pd.concat([base, pd.DataFrame(self._mock_scope_overrides)], ignore_index=True)
            columns = ["user_principal", "org_id", "scope_level", "active_flag", "granted_at"]
            for column in columns:
                if column not in base.columns:
                    base[column] = None
            if base.empty:
                return pd.DataFrame(columns=columns)
            base["user_principal"] = base["user_principal"].astype(str)
            base["org_id"] = base["org_id"].astype(str)
            base = base.sort_values("granted_at").drop_duplicates(subset=["user_principal", "org_id"], keep="last")
            return base[columns]
        return self.client.query(
            self._sql(
                "reporting/list_scope_grants.sql",
                sec_user_org_scope=self._table("sec_user_org_scope"),
            )
        )

    def grant_role(self, target_user_principal: str, role_code: str, granted_by: str) -> None:
        if self.config.use_mock:
            target = str(target_user_principal or "").strip()
            role = str(role_code or "").strip().lower()
            if target and role:
                grants = self._mock_role_overrides.setdefault(target, set())
                grants.add(role)
            return
        self._ensure_user_directory_entry(target_user_principal)
        self._ensure_user_directory_entry(granted_by)
        now = self._now()
        self._execute_file(
            "inserts/grant_role.sql",
            params=(target_user_principal, role_code, True, granted_by, now, None),
            sec_user_role_map=self._table("sec_user_role_map"),
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
            target = str(target_user_principal or "").strip()
            org = str(org_id or "").strip()
            level = str(scope_level or "").strip().lower()
            if target and org and level:
                self._mock_scope_overrides.append(
                    {
                        "user_principal": target,
                        "org_id": org,
                        "scope_level": level,
                        "active_flag": True,
                        "granted_at": self._now().isoformat(),
                    }
                )
            return
        self._ensure_user_directory_entry(target_user_principal)
        self._ensure_user_directory_entry(granted_by)
        now = self._now()
        self._execute_file(
            "inserts/grant_org_scope.sql",
            params=(target_user_principal, org_id, scope_level, True, now),
            sec_user_org_scope=self._table("sec_user_org_scope"),
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
        actor_ref = self._actor_ref(actor_user_principal)
        target_ref = self._actor_ref(target_user_principal) if target_user_principal else None
        self._execute_file(
            "inserts/audit_access.sql",
            params=(
                str(uuid.uuid4()),
                actor_ref,
                action_type,
                target_ref,
                target_role,
                self._now(),
                notes,
            ),
            audit_access_event=self._table("audit_access_event"),
        )
