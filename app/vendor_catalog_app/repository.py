from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from vendor_catalog_app.config import AppConfig
from vendor_catalog_app.db import DataConnectionError, DataExecutionError, DataQueryError, DatabricksSQLClient
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

from vendor_catalog_app.repository_admin import RepositoryAdminMixin
from vendor_catalog_app.repository_documents import RepositoryDocumentsMixin
from vendor_catalog_app.repository_identity import RepositoryIdentityMixin
from vendor_catalog_app.repository_lookup import RepositoryLookupMixin
from vendor_catalog_app.repository_offering import RepositoryOfferingMixin
from vendor_catalog_app.repository_project import RepositoryProjectMixin
from vendor_catalog_app.repository_reporting import RepositoryReportingMixin
from vendor_catalog_app.repository_workflow import RepositoryWorkflowMixin

from vendor_catalog_app.repository_constants import *
from vendor_catalog_app.repository_errors import SchemaBootstrapRequiredError

LOGGER = logging.getLogger(__name__)


class VendorRepository(
    RepositoryIdentityMixin,
    RepositoryReportingMixin,
    RepositoryOfferingMixin,
    RepositoryProjectMixin,
    RepositoryDocumentsMixin,
    RepositoryWorkflowMixin,
    RepositoryLookupMixin,
    RepositoryAdminMixin,
):
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.client = DatabricksSQLClient(config)
        self._runtime_tables_ensured = False
        self._local_lookup_table_ensured = False
        self._local_offering_columns_ensured = False
        self._local_offering_extension_tables_ensured = False

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

    def _probe_file(
        self,
        relative_path: str,
        *,
        params: tuple | None = None,
        **format_args: Any,
    ) -> pd.DataFrame:
        statement = self._sql(relative_path, **format_args)
        return self.client.query(statement, params)

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
        except (DataQueryError, DataConnectionError):
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

    def _local_schema_setup_hint(self) -> str:
        init_script = (Path(__file__).resolve().parents[2] / "setup" / "local_db" / "init_local_db.py").resolve()
        return (
            f"Run `{init_script}` (or `python {init_script} --reset`) to initialize the local schema before starting the app. "
            f"Configured local DB path: {self.config.local_db_path}"
        )

    def _local_table_columns(self, table_name: str) -> set[str]:
        try:
            table_info = self._probe_file("local/select_table_info.sql", table_name=table_name)
        except Exception as exc:
            raise SchemaBootstrapRequiredError(
                f"Local schema probe failed for table '{table_name}'. {self._local_schema_setup_hint()}"
            ) from exc
        if table_info.empty or "name" not in table_info.columns:
            raise SchemaBootstrapRequiredError(
                f"Required local table is missing: {table_name}. {self._local_schema_setup_hint()}"
            )
        return {
            str(value).strip().lower()
            for value in table_info["name"].tolist()
            if str(value).strip()
        }

    def _require_local_table_columns(self, table_name: str, required_columns: list[str]) -> None:
        present = self._local_table_columns(table_name)
        missing = [column for column in required_columns if column.lower() not in present]
        if missing:
            raise SchemaBootstrapRequiredError(
                f"Local table '{table_name}' is missing required columns: {', '.join(missing)}. "
                f"{self._local_schema_setup_hint()}"
            )

    def _ensure_local_lookup_option_table(self) -> None:
        if not self.config.use_local_db:
            return
        if self._local_lookup_table_ensured:
            return
        self._require_local_table_columns(
            "app_lookup_option",
            [
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
            ],
        )
        self._local_lookup_table_ensured = True

    def _ensure_local_offering_columns(self) -> None:
        if not self.config.use_local_db:
            return
        if self._local_offering_columns_ensured:
            return
        self._require_local_table_columns("core_vendor_offering", ["lob", "service_type"])
        self._local_offering_columns_ensured = True

    def _ensure_local_offering_extension_tables(self) -> None:
        if not self.config.use_local_db:
            return
        if self._local_offering_extension_tables_ensured:
            return
        self._require_local_table_columns(
            "app_offering_profile",
            [
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
        )
        self._require_local_table_columns(
            "app_offering_ticket",
            [
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
        )
        self._require_local_table_columns(
            "app_offering_data_flow",
            [
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

    @staticmethod
    def _merge_user_identity(
        base: dict[str, str | None],
        overrides: dict[str, str | None] | None = None,
    ) -> dict[str, str | None]:
        if not overrides:
            return base
        merged = dict(base)
        for key in ("email", "network_id", "first_name", "last_name", "display_name"):
            if key not in overrides:
                continue
            raw = overrides.get(key)
            value = str(raw or "").strip()
            if value:
                merged[key] = value
        return merged

    def sync_user_directory_identity(
        self,
        *,
        login_identifier: str,
        email: str | None = None,
        network_id: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        display_name: str | None = None,
    ) -> str:
        return self._ensure_user_directory_entry(
            login_identifier,
            identity_overrides={
                "email": email,
                "network_id": network_id,
                "first_name": first_name,
                "last_name": last_name,
                "display_name": display_name,
            },
        )

    def _ensure_user_directory_entry(
        self,
        user_principal: str,
        *,
        identity_overrides: dict[str, str | None] | None = None,
    ) -> str:
        login_identifier = str(user_principal or "").strip()
        if not login_identifier:
            return UNKNOWN_USER_PRINCIPAL

        identity = self._merge_user_identity(self._parse_user_identity(login_identifier), identity_overrides)
        lookup_key = login_identifier.lower()

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
            existing_row = existing.iloc[0].to_dict()
            user_id = str(existing.iloc[0]["user_id"])
            merged_identity = {
                "email": str(identity.get("email") or "").strip()
                or str(existing_row.get("email") or "").strip()
                or None,
                "network_id": str(identity.get("network_id") or "").strip()
                or str(existing_row.get("network_id") or "").strip()
                or None,
                "first_name": str(identity.get("first_name") or "").strip()
                or str(existing_row.get("first_name") or "").strip()
                or None,
                "last_name": str(identity.get("last_name") or "").strip()
                or str(existing_row.get("last_name") or "").strip()
                or None,
                "display_name": str(identity.get("display_name") or "").strip()
                or str(existing_row.get("display_name") or "").strip()
                or self._principal_to_display_name(login_identifier),
            }
            try:
                self._execute_file(
                    "updates/update_user_directory_profile.sql",
                    params=(
                        merged_identity["email"],
                        merged_identity["network_id"],
                        merged_identity["first_name"],
                        merged_identity["last_name"],
                        merged_identity["display_name"],
                        now,
                        now,
                        user_id,
                    ),
                    app_user_directory=self._table("app_user_directory"),
                )
            except (DataExecutionError, DataConnectionError):
                LOGGER.warning("Failed to update user directory profile for '%s'.", login_identifier, exc_info=True)
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
                    str(identity.get("display_name") or self._principal_to_display_name(login_identifier)),
                    True,
                    now,
                    now,
                    now,
                ),
                app_user_directory=self._table("app_user_directory"),
            )
            return user_id
        except (DataExecutionError, DataConnectionError):
            LOGGER.warning("Failed to create user directory record for '%s'.", login_identifier, exc_info=True)
            return login_identifier

    def _actor_ref(self, user_principal: str) -> str:
        return self._ensure_user_directory_entry(user_principal)

    def _user_display_lookup(self) -> dict[str, str]:
        lookup: dict[str, str] = {}
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
        except (DataExecutionError, DataConnectionError):
            LOGGER.debug(
                "Failed to write audit_entity_change for '%s/%s'.",
                entity_name,
                entity_id,
                exc_info=True,
            )
        return change_event_id

