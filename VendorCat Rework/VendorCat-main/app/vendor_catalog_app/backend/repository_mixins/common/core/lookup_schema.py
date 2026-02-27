from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from vendor_catalog_app.core.repository_constants import *
from vendor_catalog_app.core.repository_errors import SchemaBootstrapRequiredError
from vendor_catalog_app.core.security import (
    ROLE_CHOICES,
    default_change_permissions_for_role,
    default_role_definitions,
)


class RepositoryCoreLookupMixin:
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
        now = datetime(1900, 1, 1, tzinfo=UTC).isoformat()
        open_end = datetime(9999, 12, 31, 23, 59, 59, tzinfo=UTC).isoformat()
        groups: dict[str, list[str | tuple[str, str]]] = {
            LOOKUP_TYPE_DOC_SOURCE: DEFAULT_DOC_SOURCE_OPTIONS,
            LOOKUP_TYPE_DOC_TAG: DEFAULT_DOC_TAG_OPTIONS,
            LOOKUP_TYPE_OWNER_ROLE: DEFAULT_OWNER_ROLE_OPTIONS,
            LOOKUP_TYPE_ASSIGNMENT_TYPE: DEFAULT_ASSIGNMENT_TYPE_OPTIONS,
            LOOKUP_TYPE_CONTACT_TYPE: DEFAULT_CONTACT_TYPE_OPTIONS,
            LOOKUP_TYPE_PROJECT_TYPE: DEFAULT_PROJECT_TYPE_OPTIONS,
            LOOKUP_TYPE_WORKFLOW_STATUS: DEFAULT_WORKFLOW_STATUS_OPTIONS,
            LOOKUP_TYPE_OFFERING_TYPE: list(DEFAULT_OFFERING_TYPE_CHOICES),
            LOOKUP_TYPE_OFFERING_BUSINESS_UNIT: list(DEFAULT_OFFERING_BUSINESS_UNIT_CHOICES),
            LOOKUP_TYPE_OFFERING_SERVICE_TYPE: list(DEFAULT_OFFERING_SERVICE_TYPE_CHOICES),
            LOOKUP_TYPE_OWNER_ORGANIZATION: list(DEFAULT_OWNER_ORGANIZATION_CHOICES),
            LOOKUP_TYPE_VENDOR_CATEGORY: list(DEFAULT_VENDOR_CATEGORY_CHOICES),
            LOOKUP_TYPE_COMPLIANCE_CATEGORY: list(DEFAULT_COMPLIANCE_CATEGORY_CHOICES),
            LOOKUP_TYPE_GL_CATEGORY: list(DEFAULT_GL_CATEGORY_CHOICES),
            LOOKUP_TYPE_RISK_TIER: list(DEFAULT_RISK_TIER_CHOICES),
            LOOKUP_TYPE_LIFECYCLE_STATE: list(DEFAULT_LIFECYCLE_STATE_CHOICES),
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
                label_value = str(raw_label or RepositoryCoreLookupMixin._lookup_label_from_code(normalized_code)).strip()
                if not label_value:
                    label_value = RepositoryCoreLookupMixin._lookup_label_from_code(normalized_code)
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
        self._require_local_table_columns("core_vendor_offering", ["business_unit", "service_type"])
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
        self._require_local_table_columns(
            "app_offering_invoice",
            [
                "invoice_id",
                "offering_id",
                "vendor_id",
                "invoice_number",
                "invoice_date",
                "amount",
                "currency_code",
                "invoice_status",
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
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @classmethod
    def _normalize_lookup_window(
        cls,
        valid_from_ts: Any,
        valid_to_ts: Any,
    ) -> tuple[datetime, datetime]:
        start = cls._parse_lookup_ts(valid_from_ts, fallback=datetime(1900, 1, 1, tzinfo=UTC))
        end = cls._parse_lookup_ts(valid_to_ts, fallback=datetime(9999, 12, 31, 23, 59, 59, tzinfo=UTC))
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
