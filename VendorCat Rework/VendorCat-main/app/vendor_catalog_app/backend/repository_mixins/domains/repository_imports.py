from __future__ import annotations

import copy
import json
import logging
import re
import uuid
from typing import Any

import pandas as pd

IMPORT_STAGE_AREA_TABLES = {
    "vendor": "app_import_stage_vendor",
    "vendor_identifier": "app_import_stage_vendor_identifier",
    "vendor_contact": "app_import_stage_vendor_contact",
    "vendor_owner": "app_import_stage_vendor_owner",
    "offering": "app_import_stage_offering",
    "offering_owner": "app_import_stage_offering_owner",
    "offering_contact": "app_import_stage_offering_contact",
    "contract": "app_import_stage_contract",
    "project": "app_import_stage_project",
    "invoice": "app_import_stage_invoice",
    "payment": "app_import_stage_payment",
}

IMPORT_STAGE_DESTINATION_TABLES = {
    "app_import_stage_vendor": ("core_vendor",),
    "app_import_stage_vendor_identifier": ("core_vendor_identifier",),
    "app_import_stage_vendor_contact": ("core_vendor_contact",),
    "app_import_stage_vendor_owner": ("core_vendor_business_owner",),
    "app_import_stage_offering": ("core_vendor_offering",),
    "app_import_stage_offering_owner": ("core_offering_business_owner",),
    "app_import_stage_offering_contact": ("core_offering_contact",),
    "app_import_stage_contract": ("core_contract",),
    "app_import_stage_project": ("app_project",),
    "app_import_stage_invoice": ("app_offering_invoice",),
    "app_import_stage_payment": ("app_offering_payment",),
}

IMPORT_MAPPING_PROFILE_TABLE = "app_import_mapping_profile"
IMPORT_MAPPING_PROFILE_REQUEST_TABLE = "app_import_mapping_profile_request"
IMPORT_MAPPING_PROFILE_SETTING_KEY = "imports.mapping_profiles.v1"
IMPORT_MAPPING_MIGRATION_MARKER_KEY = "imports.mapping_profiles.shared_migrated.v1"
IMPORT_LOOKUP_CANDIDATE_TABLE = "app_import_lookup_candidate"

IMPORT_MAPPING_PROFILE_FIELDS = (
    "profile_id",
    "layout_key",
    "profile_name",
    "file_format",
    "source_signature",
    "source_fields_json",
    "source_target_mapping_json",
    "field_mapping_json",
    "parser_options_json",
    "active_flag",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
)

IMPORT_MAPPING_PROFILE_REQUEST_FIELDS = (
    "profile_request_id",
    "import_job_id",
    "submitted_by",
    "layout_key",
    "proposed_profile_name",
    "file_format",
    "source_system",
    "source_object",
    "source_signature",
    "source_fields_json",
    "source_target_mapping_json",
    "parser_options_json",
    "sample_rows_json",
    "status",
    "review_note",
    "reviewed_by",
    "reviewed_at",
    "approved_profile_id",
    "created_at",
    "updated_at",
)

IMPORT_LOOKUP_CANDIDATE_FIELDS = (
    "candidate_id",
    "import_job_id",
    "area_key",
    "row_index",
    "lookup_type",
    "option_code",
    "option_label",
    "status",
    "review_note",
    "reviewed_by",
    "reviewed_at",
    "created_at",
    "created_by",
)

IMPORT_REVIEW_AREA_STATE_TABLE = "app_import_review_area_state"
IMPORT_REVIEW_AREA_ORDER = (
    "vendor",
    "vendor_identifier",
    "vendor_owner",
    "vendor_contact",
    "offering",
    "offering_owner",
    "offering_contact",
    "contract",
    "project",
    "invoice",
    "payment",
)

MERGE_FIELD_KEYS = (
    "legal_name",
    "display_name",
    "lifecycle_state",
    "owner_org_id",
    "risk_tier",
    "source_system",
)

OFFERING_REFERENCE_TABLES = (
    ("core_contract", "offering_id"),
    ("core_vendor_demo", "offering_id"),
    ("core_offering_business_owner", "offering_id"),
    ("core_offering_contact", "offering_id"),
    ("app_project_offering_map", "offering_id"),
    ("app_project_demo", "linked_offering_id"),
    ("app_offering_profile", "offering_id"),
    ("app_offering_data_flow", "offering_id"),
    ("app_offering_ticket", "offering_id"),
    ("app_offering_invoice", "offering_id"),
)

VENDOR_REFERENCE_TABLES = (
    "core_vendor_contact",
    "core_vendor_org_assignment",
    "core_vendor_business_owner",
    "core_contract",
    "core_vendor_demo",
    "app_project",
    "app_project_vendor_map",
    "app_project_offering_map",
    "app_project_demo",
    "app_project_note",
    "app_offering_profile",
    "app_offering_data_flow",
    "app_offering_ticket",
    "app_offering_invoice",
    "app_offering_payment",
    "app_vendor_change_request",
    "app_vendor_warning",
)

LOGGER = logging.getLogger(__name__)


class RepositoryImportsMixin:
    def _safe_json_loads(self, payload: Any, *, expected: type = dict) -> Any:
        if isinstance(payload, expected):
            return payload
        if payload is None:
            return expected()
        if not isinstance(payload, str):
            return expected()
        try:
            loaded = json.loads(payload)
        except Exception:
            return expected()
        if isinstance(loaded, expected):
            return loaded
        return expected()

    def _table_columns_safe(self, table_name: str) -> set[str]:
        cleaned = str(table_name or "").strip()
        if not cleaned:
            return set()
        cache_key = ("imports_table_columns", cleaned.lower())

        def _load() -> set[str]:
            try:
                if self.config.use_local_db:
                    return set(self._local_table_columns(cleaned))
                frame = self._query_or_empty(
                    f"SELECT * FROM {self._table(cleaned)} WHERE 1 = 0",
                    columns=[],
                )
                return {str(col).strip().lower() for col in frame.columns if str(col).strip()}
            except Exception:
                return set()

        cached = self._cached(cache_key, _load, ttl_seconds=300)
        return set(cached or set())

    def _table_has_column(self, table_name: str, column_name: str) -> bool:
        return str(column_name or "").strip().lower() in self._table_columns_safe(table_name)

    def list_import_stage_table_columns(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for table_name in sorted(set(IMPORT_STAGE_AREA_TABLES.values())):
            columns = set(self._table_columns_safe(table_name))
            for destination_table in IMPORT_STAGE_DESTINATION_TABLES.get(table_name, ()):
                columns.update(self._table_columns_safe(destination_table))
            normalized = sorted({str(col).strip().lower() for col in columns if str(col).strip()})
            if normalized:
                out[table_name] = normalized
        return out

    def _import_mapping_profile_table_available(self) -> bool:
        columns = self._table_columns_safe(IMPORT_MAPPING_PROFILE_TABLE)
        return bool(columns and {"profile_id", "layout_key", "profile_name"}.issubset(columns))

    def list_import_mapping_profiles(
        self,
        *,
        layout_key: str = "",
        include_inactive: bool = False,
    ) -> list[dict[str, Any]]:
        if not self._import_mapping_profile_table_available():
            return []

        where_parts = ["1 = 1"]
        params: list[Any] = []
        cleaned_layout = str(layout_key or "").strip().lower()
        if cleaned_layout:
            where_parts.append("lower(layout_key) = lower(%s)")
            params.append(cleaned_layout)
        if not include_inactive:
            if self.config.use_local_db:
                where_parts.append("coalesce(active_flag, 1) = 1")
            else:
                where_parts.append("coalesce(active_flag, true) = true")

        statement = (
            "SELECT "
            + ", ".join(IMPORT_MAPPING_PROFILE_FIELDS)
            + f" FROM {self._table(IMPORT_MAPPING_PROFILE_TABLE)} "
            + f"WHERE {' AND '.join(where_parts)} "
            + "ORDER BY updated_at DESC, created_at DESC"
        )
        frame = self._query_or_empty(statement, params=tuple(params), columns=list(IMPORT_MAPPING_PROFILE_FIELDS))
        if frame.empty:
            return []

        out: list[dict[str, Any]] = []
        for row in frame.to_dict("records"):
            out.append(
                {
                    "profile_id": str(row.get("profile_id") or "").strip(),
                    "layout_key": str(row.get("layout_key") or "").strip().lower(),
                    "profile_name": str(row.get("profile_name") or "").strip(),
                    "file_format": str(row.get("file_format") or "").strip().lower(),
                    "source_signature": str(row.get("source_signature") or "").strip(),
                    "source_fields": list(self._safe_json_loads(row.get("source_fields_json"), expected=list)),
                    "source_target_mapping": dict(
                        self._safe_json_loads(row.get("source_target_mapping_json"), expected=dict)
                    ),
                    "field_mapping": dict(self._safe_json_loads(row.get("field_mapping_json"), expected=dict)),
                    "parser_options": dict(self._safe_json_loads(row.get("parser_options_json"), expected=dict)),
                    "active_flag": str(row.get("active_flag") or "1").strip().lower() not in {"0", "false", "no"},
                    "created_at": str(row.get("created_at") or "").strip(),
                    "created_by": str(row.get("created_by") or "").strip(),
                    "updated_at": str(row.get("updated_at") or "").strip(),
                    "updated_by": str(row.get("updated_by") or "").strip(),
                }
            )
        return out

    def save_import_mapping_profile(
        self,
        *,
        profile_id: str = "",
        layout_key: str,
        profile_name: str,
        file_format: str,
        source_signature: str,
        source_fields: list[dict[str, Any]] | None = None,
        source_target_mapping: dict[str, str] | None = None,
        field_mapping: dict[str, str] | None = None,
        parser_options: dict[str, Any] | None = None,
        active_flag: bool = True,
        actor_user_principal: str,
    ) -> str:
        if not self._import_mapping_profile_table_available():
            return ""

        cleaned_layout = str(layout_key or "").strip().lower()
        cleaned_name = str(profile_name or "").strip()
        if not cleaned_layout or not cleaned_name:
            return ""

        target_profile_id = str(profile_id or "").strip() or f"imap-{uuid.uuid4()}"
        now = self._now().isoformat()
        actor_ref = self._actor_ref(actor_user_principal)
        source_fields_json = json.dumps(list(source_fields or []), default=str)
        source_target_mapping_json = json.dumps(dict(source_target_mapping or {}), default=str)
        field_mapping_json = json.dumps(dict(field_mapping or {}), default=str)
        parser_options_json = json.dumps(dict(parser_options or {}), default=str)
        existing = self._query_or_empty(
            f"SELECT profile_id FROM {self._table(IMPORT_MAPPING_PROFILE_TABLE)} WHERE profile_id = %s",
            params=(target_profile_id,),
            columns=["profile_id"],
        )

        if existing.empty:
            self.client.execute(
                (
                    f"INSERT INTO {self._table(IMPORT_MAPPING_PROFILE_TABLE)} ("
                    "profile_id, layout_key, profile_name, file_format, source_signature, "
                    "source_fields_json, source_target_mapping_json, field_mapping_json, parser_options_json, "
                    "active_flag, created_at, created_by, updated_at, updated_by"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                ),
                (
                    target_profile_id,
                    cleaned_layout,
                    cleaned_name,
                    str(file_format or "").strip().lower(),
                    str(source_signature or "").strip(),
                    source_fields_json,
                    source_target_mapping_json,
                    field_mapping_json,
                    parser_options_json,
                    bool(active_flag),
                    now,
                    actor_ref,
                    now,
                    actor_ref,
                ),
            )
        else:
            self.client.execute(
                (
                    f"UPDATE {self._table(IMPORT_MAPPING_PROFILE_TABLE)} "
                    "SET layout_key = %s, profile_name = %s, file_format = %s, source_signature = %s, "
                    "source_fields_json = %s, source_target_mapping_json = %s, field_mapping_json = %s, "
                    "parser_options_json = %s, active_flag = %s, updated_at = %s, updated_by = %s "
                    "WHERE profile_id = %s"
                ),
                (
                    cleaned_layout,
                    cleaned_name,
                    str(file_format or "").strip().lower(),
                    str(source_signature or "").strip(),
                    source_fields_json,
                    source_target_mapping_json,
                    field_mapping_json,
                    parser_options_json,
                    bool(active_flag),
                    now,
                    actor_ref,
                    target_profile_id,
                ),
            )

        self._cache_clear()
        return target_profile_id

    def migrate_legacy_import_mapping_profiles(
        self,
        *,
        user_principal: str,
        actor_user_principal: str = "",
    ) -> int:
        if not self._import_mapping_profile_table_available():
            return 0
        if not hasattr(self, "get_user_setting") or not hasattr(self, "save_user_setting"):
            return 0

        user_ref = str(user_principal or "").strip()
        if not user_ref:
            return 0

        marker = dict(self.get_user_setting(user_ref, IMPORT_MAPPING_MIGRATION_MARKER_KEY) or {})
        if bool(marker.get("completed")):
            return int(marker.get("migrated_count") or 0)

        payload = dict(self.get_user_setting(user_ref, IMPORT_MAPPING_PROFILE_SETTING_KEY) or {})
        rows = [dict(item) for item in list(payload.get("profiles") or []) if isinstance(item, dict)]
        if not rows:
            self.save_user_setting(
                user_ref,
                IMPORT_MAPPING_MIGRATION_MARKER_KEY,
                {
                    "completed": True,
                    "migrated_count": 0,
                    "migrated_at": self._now().isoformat(),
                },
            )
            return 0

        migrated_count = 0
        existing_dedupe: set[tuple[str, str, str, str]] = set()
        for existing in self.list_import_mapping_profiles(include_inactive=True):
            existing_dedupe.add(
                (
                    str(existing.get("layout_key") or "").strip().lower(),
                    str(existing.get("profile_name") or "").strip().lower(),
                    str(existing.get("file_format") or "").strip().lower(),
                    str(existing.get("source_signature") or "").strip(),
                )
            )

        actor = str(actor_user_principal or user_ref).strip() or user_ref
        for row in rows:
            layout_key = str(row.get("layout_key") or "").strip().lower()
            profile_name = str(row.get("profile_name") or "").strip()
            if not layout_key or not profile_name:
                continue
            dedupe_key = (
                layout_key,
                profile_name.lower(),
                str(row.get("file_format") or "").strip().lower(),
                str(row.get("source_signature") or "").strip(),
            )
            if dedupe_key in existing_dedupe:
                continue
            saved = self.save_import_mapping_profile(
                layout_key=layout_key,
                profile_name=profile_name,
                file_format=str(row.get("file_format") or "").strip().lower(),
                source_signature=str(row.get("source_signature") or "").strip(),
                source_fields=list(row.get("source_fields") or []),
                source_target_mapping=dict(row.get("source_target_mapping") or {}),
                field_mapping=dict(row.get("field_mapping") or {}),
                parser_options=dict(row.get("parser_options") or {}),
                actor_user_principal=actor,
            )
            if saved:
                migrated_count += 1
                existing_dedupe.add(dedupe_key)

        self.save_user_setting(
            user_ref,
            IMPORT_MAPPING_MIGRATION_MARKER_KEY,
            {
                "completed": True,
                "migrated_count": migrated_count,
                "migrated_at": self._now().isoformat(),
            },
        )
        return migrated_count

    def _import_mapping_profile_request_table_available(self) -> bool:
        columns = self._table_columns_safe(IMPORT_MAPPING_PROFILE_REQUEST_TABLE)
        return bool(columns and {"profile_request_id", "layout_key", "status"}.issubset(columns))

    def _import_review_area_state_table_available(self) -> bool:
        columns = self._table_columns_safe(IMPORT_REVIEW_AREA_STATE_TABLE)
        return bool(columns and {"import_review_area_state_id", "import_job_id", "area_key", "status"}.issubset(columns))

    def _import_lookup_candidate_table_available(self) -> bool:
        columns = self._table_columns_safe(IMPORT_LOOKUP_CANDIDATE_TABLE)
        required = {"candidate_id", "import_job_id", "lookup_type", "option_code", "status"}
        return bool(columns and required.issubset(columns))

    def create_import_mapping_profile_request(
        self,
        *,
        import_job_id: str,
        submitted_by: str,
        layout_key: str,
        proposed_profile_name: str,
        file_format: str,
        source_system: str,
        source_object: str,
        source_signature: str,
        source_fields: list[dict[str, Any]] | None,
        source_target_mapping: dict[str, str] | None,
        parser_options: dict[str, Any] | None,
        sample_rows: list[dict[str, Any]] | None,
    ) -> str:
        if not self._import_mapping_profile_request_table_available():
            return ""
        request_id = f"impr-{uuid.uuid4()}"
        now = self._now().isoformat()
        self.client.execute(
            (
                f"INSERT INTO {self._table(IMPORT_MAPPING_PROFILE_REQUEST_TABLE)} ("
                "profile_request_id, import_job_id, submitted_by, layout_key, proposed_profile_name, file_format, "
                "source_system, source_object, source_signature, source_fields_json, source_target_mapping_json, "
                "parser_options_json, sample_rows_json, status, review_note, reviewed_by, reviewed_at, approved_profile_id, "
                "created_at, updated_at"
                ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            ),
            (
                request_id,
                str(import_job_id or "").strip() or None,
                str(submitted_by or "").strip() or "system",
                str(layout_key or "").strip().lower(),
                str(proposed_profile_name or "").strip() or None,
                str(file_format or "").strip().lower() or None,
                str(source_system or "").strip().lower() or None,
                str(source_object or "").strip() or None,
                str(source_signature or "").strip() or None,
                json.dumps(list(source_fields or []), default=str),
                json.dumps(dict(source_target_mapping or {}), default=str),
                json.dumps(dict(parser_options or {}), default=str),
                json.dumps(list(sample_rows or []), default=str),
                "pending",
                None,
                None,
                None,
                None,
                now,
                now,
            ),
        )
        self._cache_clear()
        return request_id

    def get_import_mapping_profile_request(self, profile_request_id: str) -> dict[str, Any] | None:
        if not self._import_mapping_profile_request_table_available():
            return None
        request_id = str(profile_request_id or "").strip()
        if not request_id:
            return None
        frame = self._query_or_empty(
            (
                "SELECT " + ", ".join(IMPORT_MAPPING_PROFILE_REQUEST_FIELDS)
                + f" FROM {self._table(IMPORT_MAPPING_PROFILE_REQUEST_TABLE)} WHERE profile_request_id = %s"
            ),
            params=(request_id,),
            columns=list(IMPORT_MAPPING_PROFILE_REQUEST_FIELDS),
        )
        if frame.empty:
            return None
        row = frame.iloc[0].to_dict()
        return {
            "profile_request_id": str(row.get("profile_request_id") or "").strip(),
            "import_job_id": str(row.get("import_job_id") or "").strip(),
            "submitted_by": str(row.get("submitted_by") or "").strip(),
            "layout_key": str(row.get("layout_key") or "").strip().lower(),
            "proposed_profile_name": str(row.get("proposed_profile_name") or "").strip(),
            "file_format": str(row.get("file_format") or "").strip().lower(),
            "source_system": str(row.get("source_system") or "").strip().lower(),
            "source_object": str(row.get("source_object") or "").strip(),
            "source_signature": str(row.get("source_signature") or "").strip(),
            "source_fields": list(self._safe_json_loads(row.get("source_fields_json"), expected=list)),
            "source_target_mapping": dict(self._safe_json_loads(row.get("source_target_mapping_json"), expected=dict)),
            "parser_options": dict(self._safe_json_loads(row.get("parser_options_json"), expected=dict)),
            "sample_rows": list(self._safe_json_loads(row.get("sample_rows_json"), expected=list)),
            "status": str(row.get("status") or "").strip().lower(),
            "review_note": str(row.get("review_note") or "").strip(),
            "reviewed_by": str(row.get("reviewed_by") or "").strip(),
            "reviewed_at": str(row.get("reviewed_at") or "").strip(),
            "approved_profile_id": str(row.get("approved_profile_id") or "").strip(),
            "created_at": str(row.get("created_at") or "").strip(),
            "updated_at": str(row.get("updated_at") or "").strip(),
        }

    def list_import_mapping_profile_requests(
        self,
        *,
        status: str = "",
        submitted_by: str = "",
        include_all: bool = False,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        if not self._import_mapping_profile_request_table_available():
            return []
        where_parts = ["1 = 1"]
        params: list[Any] = []
        normalized_status = str(status or "").strip().lower()
        if normalized_status:
            where_parts.append("lower(status) = lower(%s)")
            params.append(normalized_status)
        normalized_user = str(submitted_by or "").strip()
        if normalized_user and not include_all:
            where_parts.append("lower(submitted_by) = lower(%s)")
            params.append(normalized_user)
        safe_limit = max(1, min(int(limit or 200), 1000))
        frame = self._query_or_empty(
            (
                "SELECT " + ", ".join(IMPORT_MAPPING_PROFILE_REQUEST_FIELDS)
                + f" FROM {self._table(IMPORT_MAPPING_PROFILE_REQUEST_TABLE)} "
                + f"WHERE {' AND '.join(where_parts)} ORDER BY updated_at DESC, created_at DESC LIMIT %s"
            ),
            params=tuple(params + [safe_limit]),
            columns=list(IMPORT_MAPPING_PROFILE_REQUEST_FIELDS),
        )
        if frame.empty:
            return []
        return [
            {
                "profile_request_id": str(row.get("profile_request_id") or "").strip(),
                "import_job_id": str(row.get("import_job_id") or "").strip(),
                "submitted_by": str(row.get("submitted_by") or "").strip(),
                "layout_key": str(row.get("layout_key") or "").strip().lower(),
                "proposed_profile_name": str(row.get("proposed_profile_name") or "").strip(),
                "file_format": str(row.get("file_format") or "").strip().lower(),
                "source_system": str(row.get("source_system") or "").strip().lower(),
                "source_object": str(row.get("source_object") or "").strip(),
                "source_signature": str(row.get("source_signature") or "").strip(),
                "source_fields": list(self._safe_json_loads(row.get("source_fields_json"), expected=list)),
                "source_target_mapping": dict(self._safe_json_loads(row.get("source_target_mapping_json"), expected=dict)),
                "parser_options": dict(self._safe_json_loads(row.get("parser_options_json"), expected=dict)),
                "sample_rows": list(self._safe_json_loads(row.get("sample_rows_json"), expected=list)),
                "status": str(row.get("status") or "").strip().lower(),
                "review_note": str(row.get("review_note") or "").strip(),
                "reviewed_by": str(row.get("reviewed_by") or "").strip(),
                "reviewed_at": str(row.get("reviewed_at") or "").strip(),
                "approved_profile_id": str(row.get("approved_profile_id") or "").strip(),
                "created_at": str(row.get("created_at") or "").strip(),
                "updated_at": str(row.get("updated_at") or "").strip(),
            }
            for row in frame.to_dict("records")
        ]

    def review_import_mapping_profile_request(
        self,
        *,
        profile_request_id: str,
        decision: str,
        reviewer_user_principal: str,
        review_note: str = "",
    ) -> dict[str, Any]:
        request = self.get_import_mapping_profile_request(profile_request_id)
        if request is None:
            raise ValueError("Mapping request was not found.")
        normalized_decision = str(decision or "").strip().lower()
        if normalized_decision not in {"approved", "rejected"}:
            raise ValueError("Decision must be approved or rejected.")
        now = self._now().isoformat()
        reviewer_ref = self._actor_ref(reviewer_user_principal)
        approved_profile_id = ""
        if normalized_decision == "approved":
            profile_name = str(request.get("proposed_profile_name") or "").strip() or f"approved-{profile_request_id}"
            approved_profile_id = str(
                self.save_import_mapping_profile(
                    layout_key=str(request.get("layout_key") or "").strip().lower(),
                    profile_name=profile_name,
                    file_format=str(request.get("file_format") or "").strip().lower(),
                    source_signature=str(request.get("source_signature") or "").strip(),
                    source_fields=list(request.get("source_fields") or []),
                    source_target_mapping=dict(request.get("source_target_mapping") or {}),
                    field_mapping={},
                    parser_options=dict(request.get("parser_options") or {}),
                    active_flag=True,
                    actor_user_principal=reviewer_user_principal,
                )
                or ""
            ).strip()
            if not approved_profile_id:
                raise ValueError("Could not publish approved mapping profile.")

        self.client.execute(
            (
                f"UPDATE {self._table(IMPORT_MAPPING_PROFILE_REQUEST_TABLE)} "
                "SET status = %s, review_note = %s, reviewed_by = %s, reviewed_at = %s, approved_profile_id = %s, updated_at = %s "
                "WHERE profile_request_id = %s"
            ),
            (
                normalized_decision,
                str(review_note or "").strip() or None,
                reviewer_ref,
                now,
                approved_profile_id or None,
                now,
                str(profile_request_id or "").strip(),
            ),
        )
        self._cache_clear()
        out = self.get_import_mapping_profile_request(profile_request_id) or {}
        out["approved_profile_id"] = approved_profile_id or str(out.get("approved_profile_id") or "").strip()
        return out

    def _vendor_row_by_id(self, vendor_id: str) -> dict[str, Any] | None:
        cleaned = str(vendor_id or "").strip()
        if not cleaned:
            return None
        frame = self._query_or_empty(
            f"SELECT * FROM {self._table('core_vendor')} WHERE vendor_id = %s",
            params=(cleaned,),
            columns=[],
        )
        if frame.empty:
            return None
        return frame.iloc[0].to_dict()

    @staticmethod
    def _normalize_offering_name(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().lower())

    def _offering_rows_for_vendor(self, vendor_id: str) -> list[dict[str, Any]]:
        cleaned = str(vendor_id or "").strip()
        if not cleaned:
            return []
        frame = self._query_or_empty(
            f"SELECT * FROM {self._table('core_vendor_offering')} WHERE vendor_id = %s",
            params=(cleaned,),
            columns=[],
        )
        if frame.empty:
            return []
        return [dict(row) for row in frame.to_dict("records")]

    def _count_rows_for_vendor(self, *, table_name: str, vendor_id: str) -> int:
        if not self._table_has_column(table_name, "vendor_id"):
            return 0
        frame = self._query_or_empty(
            f"SELECT count(*) AS row_count FROM {self._table(table_name)} WHERE vendor_id = %s",
            params=(str(vendor_id or "").strip(),),
            columns=["row_count"],
        )
        if frame.empty:
            return 0
        try:
            return int(frame.iloc[0]["row_count"])
        except Exception:
            return 0

    def preview_vendor_merge(
        self,
        *,
        survivor_vendor_id: str,
        source_vendor_id: str,
    ) -> dict[str, Any]:
        survivor_id = str(survivor_vendor_id or "").strip()
        source_id = str(source_vendor_id or "").strip()
        if not survivor_id or not source_id:
            raise ValueError("Both survivor_vendor_id and source_vendor_id are required.")
        if survivor_id == source_id:
            raise ValueError("Survivor and source vendor must be different records.")

        survivor_row = self._vendor_row_by_id(survivor_id)
        source_row = self._vendor_row_by_id(source_id)
        if survivor_row is None:
            raise ValueError(f"Survivor vendor '{survivor_id}' was not found.")
        if source_row is None:
            raise ValueError(f"Source vendor '{source_id}' was not found.")

        conflicts: list[dict[str, Any]] = []
        for field_name in MERGE_FIELD_KEYS:
            survivor_value = str(survivor_row.get(field_name) or "").strip()
            source_value = str(source_row.get(field_name) or "").strip()
            if survivor_value and source_value and survivor_value != source_value:
                conflicts.append(
                    {
                        "field_name": field_name,
                        "survivor_value": survivor_value,
                        "source_value": source_value,
                        "default_decision": "survivor",
                    }
                )

        survivor_offerings = self._offering_rows_for_vendor(survivor_id)
        source_offerings = self._offering_rows_for_vendor(source_id)
        survivor_by_name: dict[str, list[dict[str, Any]]] = {}
        for row in survivor_offerings:
            key = self._normalize_offering_name(str(row.get("offering_name") or ""))
            if not key:
                continue
            survivor_by_name.setdefault(key, []).append(row)

        offering_collisions: list[dict[str, Any]] = []
        for source_offering in source_offerings:
            source_offering_id = str(source_offering.get("offering_id") or "").strip()
            source_name = str(source_offering.get("offering_name") or "").strip()
            key = self._normalize_offering_name(source_name)
            if not source_offering_id or not key:
                continue
            matches = survivor_by_name.get(key, [])
            if not matches:
                continue
            offering_collisions.append(
                {
                    "source_offering_id": source_offering_id,
                    "source_offering_name": source_name,
                    "target_options": [
                        {
                            "offering_id": str(item.get("offering_id") or "").strip(),
                            "offering_name": str(item.get("offering_name") or "").strip(),
                        }
                        for item in matches
                    ],
                    "default_decision": "keep_both",
                }
            )

        source_link_counts = {
            table_name: self._count_rows_for_vendor(table_name=table_name, vendor_id=source_id)
            for table_name in VENDOR_REFERENCE_TABLES
        }
        source_link_counts = {k: v for k, v in source_link_counts.items() if int(v or 0) > 0}

        return {
            "survivor_vendor_id": survivor_id,
            "source_vendor_id": source_id,
            "survivor_vendor": survivor_row,
            "source_vendor": source_row,
            "conflicts": conflicts,
            "offering_collisions": offering_collisions,
            "survivor_offering_count": len(survivor_offerings),
            "source_offering_count": len(source_offerings),
            "source_link_counts": source_link_counts,
            "total_source_linked_rows": int(sum(source_link_counts.values())),
        }

    @staticmethod
    def _combine_merge_field_values(*, survivor_value: str, source_value: str) -> str:
        left = str(survivor_value or "").strip()
        right = str(source_value or "").strip()
        if not left:
            return right
        if not right or right == left:
            return left
        return f"{left} | {right}"

    def _build_offering_keep_both_name(
        self,
        *,
        base_name: str,
        source_vendor_id: str,
        survivor_offerings: list[dict[str, Any]],
    ) -> str:
        existing = {
            self._normalize_offering_name(str(row.get("offering_name") or ""))
            for row in survivor_offerings
            if str(row.get("offering_name") or "").strip()
        }
        candidate = str(base_name or "").strip() or "Merged Offering"
        if self._normalize_offering_name(candidate) not in existing:
            return candidate
        suffix_seed = str(source_vendor_id or "")[-6:] or "source"
        candidate = f"{str(base_name or '').strip() or 'Offering'} (Merged {suffix_seed})"
        if self._normalize_offering_name(candidate) not in existing:
            return candidate
        index = 2
        while True:
            candidate = f"{str(base_name or '').strip() or 'Offering'} (Merged {suffix_seed}-{index})"
            if self._normalize_offering_name(candidate) not in existing:
                return candidate
            index += 1

    def _update_vendor_references(
        self,
        *,
        source_vendor_id: str,
        survivor_vendor_id: str,
    ) -> dict[str, int]:
        source_id = str(source_vendor_id or "").strip()
        survivor_id = str(survivor_vendor_id or "").strip()
        if not source_id or not survivor_id:
            return {}
        updated: dict[str, int] = {}
        for table_name in VENDOR_REFERENCE_TABLES:
            if not self._table_has_column(table_name, "vendor_id"):
                continue
            before = self._query_or_empty(
                f"SELECT count(*) AS row_count FROM {self._table(table_name)} WHERE vendor_id = %s",
                params=(source_id,),
                columns=["row_count"],
            )
            count = int(before.iloc[0]["row_count"]) if not before.empty else 0
            if count <= 0:
                continue
            self.client.execute(
                f"UPDATE {self._table(table_name)} SET vendor_id = %s WHERE vendor_id = %s",
                (survivor_id, source_id),
            )
            updated[table_name] = count
        return updated

    def _vendor_merge_tables_available(self) -> bool:
        required = (
            "vendor_merge_event",
            "vendor_merge_member",
            "vendor_merge_snapshot",
            "vendor_survivorship_decision",
        )
        return all(bool(self._table_columns_safe(table_name)) for table_name in required)

    def _update_vendor_id_for_offering_related_rows(
        self,
        *,
        offering_id: str,
        survivor_vendor_id: str,
    ) -> None:
        offering_key = str(offering_id or "").strip()
        survivor_key = str(survivor_vendor_id or "").strip()
        if not offering_key or not survivor_key:
            return
        for table_name, column_name in OFFERING_REFERENCE_TABLES:
            if not self._table_has_column(table_name, "vendor_id"):
                continue
            if not self._table_has_column(table_name, column_name):
                continue
            self.client.execute(
                (
                    f"UPDATE {self._table(table_name)} "
                    "SET vendor_id = %s "
                    f"WHERE {column_name} = %s"
                ),
                (survivor_key, offering_key),
            )

    def _merge_source_offering_into_target(
        self,
        *,
        source_offering_id: str,
        target_offering_id: str,
        survivor_vendor_id: str,
    ) -> dict[str, int]:
        source_key = str(source_offering_id or "").strip()
        target_key = str(target_offering_id or "").strip()
        survivor_key = str(survivor_vendor_id or "").strip()
        if not source_key or not target_key or source_key == target_key:
            return {}

        moved_counts: dict[str, int] = {}
        for table_name, column_name in (
            ("core_contract", "offering_id"),
            ("core_vendor_demo", "offering_id"),
            ("core_offering_business_owner", "offering_id"),
            ("core_offering_contact", "offering_id"),
            ("app_project_demo", "linked_offering_id"),
        ):
            if not self._table_has_column(table_name, column_name):
                continue
            before = self._query_or_empty(
                f"SELECT count(*) AS row_count FROM {self._table(table_name)} WHERE {column_name} = %s",
                params=(source_key,),
                columns=["row_count"],
            )
            count = int(before.iloc[0]["row_count"]) if not before.empty else 0
            if count <= 0:
                continue
            if self._table_has_column(table_name, "vendor_id"):
                self.client.execute(
                    (
                        f"UPDATE {self._table(table_name)} "
                        f"SET {column_name} = %s, vendor_id = %s "
                        f"WHERE {column_name} = %s"
                    ),
                    (target_key, survivor_key, source_key),
                )
            else:
                self.client.execute(
                    (
                        f"UPDATE {self._table(table_name)} "
                        f"SET {column_name} = %s "
                        f"WHERE {column_name} = %s"
                    ),
                    (target_key, source_key),
                )
            moved_counts[f"{table_name}.{column_name}"] = count

        if self._table_has_column("app_project_offering_map", "offering_id"):
            duplicates = self._query_or_empty(
                (
                    "SELECT s.project_offering_map_id "
                    f"FROM {self._table('app_project_offering_map')} s "
                    f"JOIN {self._table('app_project_offering_map')} t "
                    "  ON s.project_id = t.project_id "
                    " AND coalesce(s.active_flag, true) = coalesce(t.active_flag, true) "
                    "WHERE s.offering_id = %s "
                    "  AND t.offering_id = %s"
                ),
                params=(source_key, target_key),
                columns=["project_offering_map_id"],
            )
            duplicate_ids = [
                str(value).strip()
                for value in duplicates.get("project_offering_map_id", pd.Series(dtype="object")).tolist()
                if str(value).strip()
            ]
            if duplicate_ids:
                placeholders = ", ".join(["%s"] * len(duplicate_ids))
                self.client.execute(
                    f"DELETE FROM {self._table('app_project_offering_map')} WHERE project_offering_map_id IN ({placeholders})",
                    tuple(duplicate_ids),
                )
            before = self._query_or_empty(
                f"SELECT count(*) AS row_count FROM {self._table('app_project_offering_map')} WHERE offering_id = %s",
                params=(source_key,),
                columns=["row_count"],
            )
            count = int(before.iloc[0]["row_count"]) if not before.empty else 0
            if count > 0:
                self.client.execute(
                    (
                        f"UPDATE {self._table('app_project_offering_map')} "
                        "SET offering_id = %s, vendor_id = %s "
                        "WHERE offering_id = %s"
                    ),
                    (target_key, survivor_key, source_key),
                )
                moved_counts["app_project_offering_map.offering_id"] = count

        return moved_counts

    def execute_vendor_merge(
        self,
        *,
        survivor_vendor_id: str,
        source_vendor_id: str,
        field_decisions: dict[str, str] | None,
        offering_decisions: dict[str, dict[str, Any]] | None,
        actor_user_principal: str,
        merge_reason: str,
    ) -> dict[str, Any]:
        preview = self.preview_vendor_merge(
            survivor_vendor_id=survivor_vendor_id,
            source_vendor_id=source_vendor_id,
        )
        survivor_id = str(preview.get("survivor_vendor_id") or "").strip()
        source_id = str(preview.get("source_vendor_id") or "").strip()
        survivor_before = dict(preview.get("survivor_vendor") or {})
        source_before = dict(preview.get("source_vendor") or {})
        if not survivor_id or not source_id:
            raise ValueError("Merge preview could not resolve source and survivor IDs.")

        normalized_reason = str(merge_reason or "").strip() or "vendor_merge_center"
        decision_map = {str(k).strip(): str(v).strip().lower() for k, v in dict(field_decisions or {}).items() if str(k).strip()}
        offering_map = {
            str(k).strip(): dict(v)
            for k, v in dict(offering_decisions or {}).items()
            if str(k).strip() and isinstance(v, dict)
        }

        conflict_fields = {str(item.get("field_name") or "").strip() for item in list(preview.get("conflicts") or [])}
        missing_conflicts = [field for field in sorted(conflict_fields) if field and field not in decision_map]
        if missing_conflicts:
            raise ValueError(
                "Conflict decisions are required before execution. Missing decisions for: "
                + ", ".join(missing_conflicts)
            )
        collision_source_offering_ids = {
            str(item.get("source_offering_id") or "").strip()
            for item in list(preview.get("offering_collisions") or [])
            if str(item.get("source_offering_id") or "").strip()
        }
        missing_offering_decisions = [
            offering_id
            for offering_id in sorted(collision_source_offering_ids)
            if offering_id and offering_id not in offering_map
        ]
        if missing_offering_decisions:
            raise ValueError(
                "Offering collision decisions are required before execution. Missing decisions for: "
                + ", ".join(missing_offering_decisions)
            )

        now = self._now().isoformat()
        actor_ref = self._actor_ref(actor_user_principal)
        merge_id = f"vmrg-{uuid.uuid4()}"
        decision_records: list[dict[str, str]] = []

        survivor_updates: dict[str, Any] = {}
        for conflict in list(preview.get("conflicts") or []):
            field_name = str(conflict.get("field_name") or "").strip()
            if not field_name:
                continue
            choice = str(decision_map.get(field_name) or "survivor").strip().lower()
            survivor_value = str(conflict.get("survivor_value") or "").strip()
            source_value = str(conflict.get("source_value") or "").strip()
            chosen = survivor_value
            if choice == "source":
                chosen = source_value
                if source_value:
                    survivor_updates[field_name] = source_value
            elif choice == "keep_both":
                chosen = self._combine_merge_field_values(
                    survivor_value=survivor_value,
                    source_value=source_value,
                )
                if chosen and chosen != survivor_value:
                    survivor_updates[field_name] = chosen
            else:
                choice = "survivor"
            decision_records.append(
                {
                    "field_name": field_name,
                    "decision": choice,
                    "chosen_value": chosen,
                }
            )

        if survivor_updates:
            self.apply_vendor_profile_update(
                vendor_id=survivor_id,
                actor_user_principal=actor_user_principal,
                updates=survivor_updates,
                reason=f"vendor merge ({normalized_reason})",
            )

        survivor_offerings = self._offering_rows_for_vendor(survivor_id)
        survivor_by_name: dict[str, list[dict[str, Any]]] = {}
        for row in survivor_offerings:
            name_key = self._normalize_offering_name(str(row.get("offering_name") or ""))
            if name_key:
                survivor_by_name.setdefault(name_key, []).append(row)

        offering_summary = {"keep_both": 0, "merged_into_existing": 0}
        moved_relation_counts: dict[str, int] = {}
        touched_offering_ids: set[str] = set()
        source_offerings = self._offering_rows_for_vendor(source_id)
        for source_offering in source_offerings:
            source_offering_id = str(source_offering.get("offering_id") or "").strip()
            if not source_offering_id:
                continue
            source_name = str(source_offering.get("offering_name") or "").strip()
            name_key = self._normalize_offering_name(source_name)
            collision_matches = list(survivor_by_name.get(name_key, [])) if name_key else []

            configured = dict(offering_map.get(source_offering_id) or {})
            decision = str(configured.get("decision") or ("merge" if collision_matches else "keep_both")).strip().lower()
            if decision == "merge":
                target_offering_id = str(configured.get("target_offering_id") or "").strip()
                if not target_offering_id and collision_matches:
                    target_offering_id = str(collision_matches[0].get("offering_id") or "").strip()
                if not target_offering_id:
                    raise ValueError(
                        f"Offering decision for '{source_offering_id}' requires target_offering_id when decision=merge."
                    )
                moved = self._merge_source_offering_into_target(
                    source_offering_id=source_offering_id,
                    target_offering_id=target_offering_id,
                    survivor_vendor_id=survivor_id,
                )
                for key, value in moved.items():
                    moved_relation_counts[key] = int(moved_relation_counts.get(key, 0)) + int(value or 0)
                self.client.execute(
                    (
                        f"UPDATE {self._table('core_vendor_offering')} "
                        "SET vendor_id = %s, offering_name = %s, lifecycle_state = %s, updated_at = %s, updated_by = %s "
                        "WHERE offering_id = %s"
                    ),
                    (
                        survivor_id,
                        f"{source_name or source_offering_id} (Merged into {target_offering_id})",
                        "retired",
                        now,
                        actor_ref,
                        source_offering_id,
                    ),
                )
                touched_offering_ids.add(source_offering_id)
                touched_offering_ids.add(target_offering_id)
                self._canonical_sync_offering_related_from_core(
                    offering_id=target_offering_id,
                    actor_user_principal=actor_user_principal,
                )
                self._canonical_sync_offering_related_from_core(
                    offering_id=source_offering_id,
                    actor_user_principal=actor_user_principal,
                )
                decision_records.append(
                    {
                        "field_name": f"offering:{source_offering_id}",
                        "decision": "merge",
                        "chosen_value": target_offering_id,
                    }
                )
                offering_summary["merged_into_existing"] += 1
                continue

            renamed = str(configured.get("renamed_offering_name") or "").strip() or source_name
            if collision_matches:
                renamed = self._build_offering_keep_both_name(
                    base_name=renamed,
                    source_vendor_id=source_id,
                    survivor_offerings=survivor_offerings,
                )
            self.client.execute(
                (
                    f"UPDATE {self._table('core_vendor_offering')} "
                    "SET vendor_id = %s, offering_name = %s, updated_at = %s, updated_by = %s "
                    "WHERE offering_id = %s"
                ),
                (survivor_id, renamed, now, actor_ref, source_offering_id),
            )
            self._update_vendor_id_for_offering_related_rows(
                offering_id=source_offering_id,
                survivor_vendor_id=survivor_id,
            )
            touched_offering_ids.add(source_offering_id)
            self._canonical_sync_offering_related_from_core(
                offering_id=source_offering_id,
                actor_user_principal=actor_user_principal,
            )
            decision_records.append(
                {
                    "field_name": f"offering:{source_offering_id}",
                    "decision": "keep_both",
                    "chosen_value": renamed,
                }
            )
            offering_summary["keep_both"] += 1

        vendor_reassign_counts = self._update_vendor_references(
            source_vendor_id=source_id,
            survivor_vendor_id=survivor_id,
        )

        set_parts = [
            "lifecycle_state = %s",
            "updated_at = %s",
            "updated_by = %s",
        ]
        params: list[Any] = ["inactive", now, actor_ref]
        if self._table_has_column("core_vendor", "merged_into_vendor_id"):
            set_parts.append("merged_into_vendor_id = %s")
            params.append(survivor_id)
        if self._table_has_column("core_vendor", "merged_at"):
            set_parts.append("merged_at = %s")
            params.append(now)
        if self._table_has_column("core_vendor", "merged_by"):
            set_parts.append("merged_by = %s")
            params.append(actor_ref)
        if self._table_has_column("core_vendor", "merge_reason"):
            set_parts.append("merge_reason = %s")
            params.append(normalized_reason)
        params.append(source_id)
        self.client.execute(
            f"UPDATE {self._table('core_vendor')} SET {', '.join(set_parts)} WHERE vendor_id = %s",
            tuple(params),
        )
        self._canonical_sync_vendor_related_from_core(
            vendor_id=survivor_id,
            actor_user_principal=actor_user_principal,
        )
        self._canonical_sync_vendor_related_from_core(
            vendor_id=source_id,
            actor_user_principal=actor_user_principal,
        )
        self._canonical_sync_vendor_from_core(
            vendor_id=survivor_id,
            actor_user_principal=actor_user_principal,
            sync_primary_business_unit_assignment=True,
            source_key_for_primary=f"core_vendor.owner_org_id:{survivor_id}",
        )
        self._canonical_sync_vendor_from_core(
            vendor_id=source_id,
            actor_user_principal=actor_user_principal,
            sync_primary_business_unit_assignment=False,
            source_key_for_primary=f"core_vendor.owner_org_id:{source_id}",
        )
        for touched_offering_id in touched_offering_ids:
            if not str(touched_offering_id or "").strip():
                continue
            self._canonical_sync_offering_related_from_core(
                offering_id=str(touched_offering_id),
                actor_user_principal=actor_user_principal,
            )

        source_after = dict(source_before)
        source_after.update(
            {
                "lifecycle_state": "inactive",
                "updated_at": now,
                "updated_by": actor_ref,
                "merged_into_vendor_id": survivor_id if self._table_has_column("core_vendor", "merged_into_vendor_id") else "",
            }
        )

        self._write_audit_entity_change(
            entity_name="core_vendor",
            entity_id=source_id,
            action_type="update",
            actor_user_principal=actor_user_principal,
            before_json=source_before,
            after_json=source_after,
            request_id=merge_id,
        )
        if survivor_updates:
            survivor_after = dict(survivor_before)
            survivor_after.update(survivor_updates)
            self._write_audit_entity_change(
                entity_name="core_vendor",
                entity_id=survivor_id,
                action_type="update",
                actor_user_principal=actor_user_principal,
                before_json=survivor_before,
                after_json=survivor_after,
                request_id=merge_id,
            )

        if self._vendor_merge_tables_available():
            try:
                self.client.execute(
                    (
                        f"INSERT INTO {self._table('vendor_merge_event')} ("
                        "merge_id, survivor_vendor_id, merge_status, merge_reason, merge_method, confidence_score, request_id, merged_at, merged_by"
                        ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                    ),
                    (merge_id, survivor_id, "completed", normalized_reason, "merge_center", None, None, now, actor_ref),
                )
                for member_role, member_id, before_row in (
                    ("survivor", survivor_id, survivor_before),
                    ("source", source_id, source_before),
                ):
                    self.client.execute(
                        (
                            f"INSERT INTO {self._table('vendor_merge_member')} ("
                            "merge_member_id, merge_id, vendor_id, member_role, source_system_code, source_vendor_key, pre_merge_display_name, active_flag, created_at"
                            ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                        ),
                        (
                            f"vmm-{uuid.uuid4()}",
                            merge_id,
                            member_id,
                            member_role,
                            str(before_row.get("source_system") or ""),
                            str(before_row.get("source_record_id") or ""),
                            str(before_row.get("display_name") or before_row.get("legal_name") or member_id),
                            True,
                            now,
                        ),
                    )
                    self.client.execute(
                        (
                            f"INSERT INTO {self._table('vendor_merge_snapshot')} ("
                            "snapshot_id, merge_id, vendor_id, snapshot_json, captured_at, captured_by"
                            ") VALUES (%s, %s, %s, %s, %s, %s)"
                        ),
                        (
                            f"vms-{uuid.uuid4()}",
                            merge_id,
                            member_id,
                            json.dumps(before_row, default=str),
                            now,
                            actor_ref,
                        ),
                    )
                for decision in decision_records:
                    self.client.execute(
                        (
                            f"INSERT INTO {self._table('vendor_survivorship_decision')} ("
                            "decision_id, merge_id, field_name, chosen_vendor_id, chosen_value_text, decision_method, decision_note, decided_at, decided_by"
                            ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                        ),
                        (
                            f"vsd-{uuid.uuid4()}",
                            merge_id,
                            str(decision.get("field_name") or ""),
                            survivor_id,
                            str(decision.get("chosen_value") or ""),
                            "manual",
                            str(decision.get("decision") or ""),
                            now,
                            actor_ref,
                        ),
                    )
            except Exception:
                LOGGER.warning("Vendor merge governance write failed for merge '%s'.", merge_id, exc_info=True)

        try:
            self._execute_file(
                "inserts/create_workflow_event.sql",
                params=(
                    str(uuid.uuid4()),
                    "vendor_merge",
                    merge_id,
                    "previewed",
                    "executed",
                    actor_ref,
                    self._now(),
                    f"Vendor merge executed: {source_id} -> {survivor_id}",
                ),
                audit_workflow_event=self._table("audit_workflow_event"),
            )
        except Exception:
            LOGGER.debug("Failed to write vendor merge workflow event for '%s'.", merge_id, exc_info=True)

        self._cache_clear()
        return {
            "merge_id": merge_id,
            "survivor_vendor_id": survivor_id,
            "source_vendor_id": source_id,
            "survivor_updates": survivor_updates,
            "field_decisions": decision_records,
            "vendor_reassign_counts": vendor_reassign_counts,
            "offering_summary": offering_summary,
            "offering_moved_relation_counts": moved_relation_counts,
            "merge_reason": normalized_reason,
        }

    def resolve_canonical_vendor_id(self, vendor_id: str) -> str:
        requested_id = str(vendor_id or "").strip()
        if not requested_id:
            return ""
        if not self._table_has_column("core_vendor", "merged_into_vendor_id"):
            return requested_id

        current_id = requested_id
        seen: set[str] = set()
        for _ in range(12):
            if current_id in seen:
                break
            seen.add(current_id)
            row = self._vendor_row_by_id(current_id)
            if row is None:
                break
            merged_into = str(row.get("merged_into_vendor_id") or "").strip()
            if not merged_into or merged_into == current_id:
                return current_id
            current_id = merged_into
        return current_id or requested_id

    def list_vendor_merge_history(
        self,
        *,
        vendor_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        vendor_key = str(vendor_id or "").strip()
        if not vendor_key:
            return []
        safe_limit = max(1, min(int(limit or 100), 500))
        if not self._vendor_merge_tables_available():
            return []

        frame = self._query_or_empty(
            (
                "SELECT "
                "e.merge_id, e.survivor_vendor_id, e.merge_status, e.merge_reason, e.merge_method, e.merged_at, e.merged_by, "
                "m.vendor_id AS member_vendor_id, m.member_role, m.pre_merge_display_name "
                f"FROM {self._table('vendor_merge_event')} e "
                f"LEFT JOIN {self._table('vendor_merge_member')} m ON m.merge_id = e.merge_id "
                "WHERE e.survivor_vendor_id = %s OR m.vendor_id = %s "
                "ORDER BY e.merged_at DESC "
                "LIMIT %s"
            ),
            params=(vendor_key, vendor_key, safe_limit),
            columns=[
                "merge_id",
                "survivor_vendor_id",
                "merge_status",
                "merge_reason",
                "merge_method",
                "merged_at",
                "merged_by",
                "member_vendor_id",
                "member_role",
                "pre_merge_display_name",
            ],
        )
        if frame.empty:
            return []

        history_by_id: dict[str, dict[str, Any]] = {}
        for row in frame.to_dict("records"):
            merge_id = str(row.get("merge_id") or "").strip()
            if not merge_id:
                continue
            entry = history_by_id.get(merge_id)
            if entry is None:
                entry = {
                    "merge_id": merge_id,
                    "survivor_vendor_id": str(row.get("survivor_vendor_id") or "").strip(),
                    "merge_status": str(row.get("merge_status") or "").strip(),
                    "merge_reason": str(row.get("merge_reason") or "").strip(),
                    "merge_method": str(row.get("merge_method") or "").strip(),
                    "merged_at": str(row.get("merged_at") or "").strip(),
                    "merged_by": str(row.get("merged_by") or "").strip(),
                    "members": [],
                    "decisions": [],
                }
                history_by_id[merge_id] = entry
            member_vendor_id = str(row.get("member_vendor_id") or "").strip()
            if member_vendor_id:
                if not any(
                    str(existing.get("vendor_id") or "").strip() == member_vendor_id
                    for existing in list(entry.get("members") or [])
                ):
                    entry["members"].append(
                        {
                            "vendor_id": member_vendor_id,
                            "member_role": str(row.get("member_role") or "").strip(),
                            "pre_merge_display_name": str(row.get("pre_merge_display_name") or "").strip(),
                        }
                    )

        merge_ids = [merge_id for merge_id in history_by_id if merge_id]
        if not merge_ids:
            return []
        decision_frame = pd.DataFrame()
        try:
            placeholders = ", ".join(["%s"] * len(merge_ids))
            decision_frame = self._query_or_empty(
                (
                    "SELECT merge_id, field_name, chosen_vendor_id, chosen_value_text, decision_method, decision_note, decided_at, decided_by "
                    f"FROM {self._table('vendor_survivorship_decision')} "
                    f"WHERE merge_id IN ({placeholders}) "
                    "ORDER BY decided_at ASC"
                ),
                params=tuple(merge_ids),
                columns=[
                    "merge_id",
                    "field_name",
                    "chosen_vendor_id",
                    "chosen_value_text",
                    "decision_method",
                    "decision_note",
                    "decided_at",
                    "decided_by",
                ],
            )
        except Exception:
            decision_frame = pd.DataFrame()

        if not decision_frame.empty:
            for row in decision_frame.to_dict("records"):
                merge_id = str(row.get("merge_id") or "").strip()
                entry = history_by_id.get(merge_id)
                if entry is None:
                    continue
                entry["decisions"].append(
                    {
                        "field_name": str(row.get("field_name") or "").strip(),
                        "chosen_vendor_id": str(row.get("chosen_vendor_id") or "").strip(),
                        "chosen_value_text": str(row.get("chosen_value_text") or "").strip(),
                        "decision_method": str(row.get("decision_method") or "").strip(),
                        "decision_note": str(row.get("decision_note") or "").strip(),
                        "decided_at": str(row.get("decided_at") or "").strip(),
                        "decided_by": str(row.get("decided_by") or "").strip(),
                    }
                )

        history = list(history_by_id.values())
        history.sort(
            key=lambda item: str(item.get("merged_at") or ""),
            reverse=True,
        )
        return history

    def get_import_job(self, import_job_id: str) -> dict[str, Any] | None:
        job_id = str(import_job_id or "").strip()
        if not job_id:
            return None
        frame = self._query_or_empty(
            f"SELECT * FROM {self._table('app_import_job')} WHERE import_job_id = %s",
            params=(job_id,),
            columns=[],
        )
        if frame.empty:
            return None
        row = frame.iloc[0].to_dict()
        return {
            "import_job_id": str(row.get("import_job_id") or "").strip(),
            "layout_key": str(row.get("layout_key") or "").strip().lower(),
            "source_system": str(row.get("source_system") or "").strip().lower(),
            "source_object": str(row.get("source_object") or "").strip(),
            "file_name": str(row.get("file_name") or "").strip(),
            "file_type": str(row.get("file_type") or "").strip().lower(),
            "detected_format": str(row.get("detected_format") or "").strip().lower(),
            "parser_config": dict(self._safe_json_loads(row.get("parser_config_json"), expected=dict)),
            "context": dict(self._safe_json_loads(row.get("context_json"), expected=dict)),
            "mapping_profile_id": str(row.get("mapping_profile_id") or "").strip(),
            "mapping_request_id": str(row.get("mapping_request_id") or "").strip(),
            "row_count": int(row.get("row_count") or 0),
            "status": str(row.get("status") or "").strip().lower(),
            "created_count": int(row.get("created_count") or 0),
            "merged_count": int(row.get("merged_count") or 0),
            "skipped_count": int(row.get("skipped_count") or 0),
            "failed_count": int(row.get("failed_count") or 0),
            "error_message": str(row.get("error_message") or "").strip(),
            "created_at": str(row.get("created_at") or "").strip(),
            "created_by": str(row.get("created_by") or "").strip(),
            "applied_at": str(row.get("applied_at") or "").strip(),
            "applied_by": str(row.get("applied_by") or "").strip(),
        }

    def update_import_job_status(
        self,
        *,
        import_job_id: str,
        status: str,
        actor_user_principal: str,
        error_message: str = "",
    ) -> None:
        job_id = str(import_job_id or "").strip()
        if not job_id:
            return
        now = self._now().isoformat()
        actor_ref = self._actor_ref(actor_user_principal)
        self.client.execute(
            (
                f"UPDATE {self._table('app_import_job')} "
                "SET status = %s, error_message = %s, applied_at = %s, applied_by = %s "
                "WHERE import_job_id = %s"
            ),
            (
                str(status or "").strip().lower() or "uploaded",
                str(error_message or "").strip() or None,
                now,
                actor_ref,
                job_id,
            ),
        )
        self._cache_clear()

    def update_import_job_context(
        self,
        *,
        import_job_id: str,
        context: dict[str, Any],
        actor_user_principal: str,
    ) -> None:
        job_id = str(import_job_id or "").strip()
        if not job_id:
            return
        now = self._now().isoformat()
        actor_ref = self._actor_ref(actor_user_principal)
        self.client.execute(
            (
                f"UPDATE {self._table('app_import_job')} "
                "SET context_json = %s, applied_at = %s, applied_by = %s WHERE import_job_id = %s"
            ),
            (json.dumps(dict(context or {}), default=str), now, actor_ref, job_id),
        )
        self._cache_clear()

    def set_import_job_mapping_links(
        self,
        *,
        import_job_id: str,
        mapping_profile_id: str = "",
        mapping_request_id: str = "",
        actor_user_principal: str,
    ) -> None:
        job_id = str(import_job_id or "").strip()
        if not job_id:
            return
        now = self._now().isoformat()
        actor_ref = self._actor_ref(actor_user_principal)
        self.client.execute(
            (
                f"UPDATE {self._table('app_import_job')} "
                "SET mapping_profile_id = %s, mapping_request_id = %s, applied_at = %s, applied_by = %s "
                "WHERE import_job_id = %s"
            ),
            (
                str(mapping_profile_id or "").strip() or None,
                str(mapping_request_id or "").strip() or None,
                now,
                actor_ref,
                job_id,
            ),
        )
        self._cache_clear()

    def clear_import_stage_rows(
        self,
        *,
        import_job_id: str,
        area_key: str = "",
        exclude_area_keys: list[str] | None = None,
    ) -> int:
        job_id = str(import_job_id or "").strip()
        if not job_id:
            return 0
        params: list[Any] = [job_id]
        where_parts = ["import_job_id = %s"]
        cleaned_area = str(area_key or "").strip().lower()
        if cleaned_area:
            where_parts.append("lower(coalesce(area_key, '')) = lower(%s)")
            params.append(cleaned_area)
        excluded = [str(item or "").strip().lower() for item in list(exclude_area_keys or []) if str(item or "").strip()]
        if excluded:
            placeholders = ", ".join(["%s"] * len(excluded))
            where_parts.append(f"lower(coalesce(area_key, '')) NOT IN ({placeholders})")
            params.extend(excluded)
        self.client.execute(
            f"DELETE FROM {self._table('app_import_stage_row')} WHERE {' AND '.join(where_parts)}",
            tuple(params),
        )
        self._cache_clear()
        return 1

    def list_import_stage_rows(
        self,
        *,
        import_job_id: str,
        area_key: str = "",
    ) -> list[dict[str, Any]]:
        job_id = str(import_job_id or "").strip()
        if not job_id:
            return []
        params: list[Any] = [job_id]
        where_parts = ["import_job_id = %s"]
        cleaned_area = str(area_key or "").strip().lower()
        if cleaned_area:
            where_parts.append("lower(coalesce(area_key, '')) = lower(%s)")
            params.append(cleaned_area)
        frame = self._query_or_empty(
            (
                f"SELECT * FROM {self._table('app_import_stage_row')} "
                f"WHERE {' AND '.join(where_parts)} ORDER BY row_index ASC"
            ),
            params=tuple(params),
            columns=[],
        )
        if frame.empty:
            return []
        out: list[dict[str, Any]] = []
        for row in frame.to_dict("records"):
            payload = dict(self._safe_json_loads(row.get("row_payload_json"), expected=dict))
            out.append(
                {
                    "import_stage_row_id": str(row.get("import_stage_row_id") or "").strip(),
                    "import_job_id": str(row.get("import_job_id") or "").strip(),
                    "row_index": int(row.get("row_index") or 0),
                    "line_number": str(row.get("line_number") or "").strip(),
                    "area_key": str(row.get("area_key") or "").strip().lower(),
                    "source_group_key": str(row.get("source_group_key") or "").strip(),
                    "row_payload": payload,
                    "suggested_action": str(row.get("suggested_action") or "").strip().lower(),
                    "suggested_target_id": str(row.get("suggested_target_id") or "").strip(),
                    "decision_action": str(row.get("decision_action") or "").strip().lower(),
                    "decision_target_id": str(row.get("decision_target_id") or "").strip(),
                    "decision_payload": dict(self._safe_json_loads(row.get("decision_payload_json"), expected=dict)),
                    "decision_updated_at": str(row.get("decision_updated_at") or "").strip(),
                    "decision_updated_by": str(row.get("decision_updated_by") or "").strip(),
                    "created_at": str(row.get("created_at") or "").strip(),
                }
            )
        return out

    def save_import_review_decisions(
        self,
        *,
        import_job_id: str,
        decisions: list[dict[str, Any]],
        actor_user_principal: str,
    ) -> int:
        job_id = str(import_job_id or "").strip()
        if not job_id:
            return 0
        now = self._now().isoformat()
        actor_ref = self._actor_ref(actor_user_principal)
        updates = 0
        for row in list(decisions or []):
            stage_row_id = str(row.get("import_stage_row_id") or "").strip()
            if not stage_row_id:
                continue
            action = str(row.get("decision_action") or "").strip().lower()
            target = str(row.get("decision_target_id") or "").strip()
            payload = dict(row.get("decision_payload") or {})
            self.client.execute(
                (
                    f"UPDATE {self._table('app_import_stage_row')} "
                    "SET decision_action = %s, decision_target_id = %s, decision_payload_json = %s, "
                    "decision_updated_at = %s, decision_updated_by = %s "
                    "WHERE import_job_id = %s AND import_stage_row_id = %s"
                ),
                (
                    action or None,
                    target or None,
                    json.dumps(payload, default=str) if payload else None,
                    now,
                    actor_ref,
                    job_id,
                    stage_row_id,
                ),
            )
            updates += 1
        if updates:
            self._cache_clear()
        return updates

    def initialize_import_review_area_states(
        self,
        *,
        import_job_id: str,
        actor_user_principal: str,
    ) -> int:
        if not self._import_review_area_state_table_available():
            return 0
        job_id = str(import_job_id or "").strip()
        if not job_id:
            return 0
        self.client.execute(
            f"DELETE FROM {self._table(IMPORT_REVIEW_AREA_STATE_TABLE)} WHERE import_job_id = %s",
            (job_id,),
        )
        now = self._now().isoformat()
        actor_ref = self._actor_ref(actor_user_principal)
        inserted = 0
        for idx, area_key in enumerate(IMPORT_REVIEW_AREA_ORDER, start=1):
            status = "in_progress" if idx == 1 else "locked"
            self.client.execute(
                (
                    f"INSERT INTO {self._table(IMPORT_REVIEW_AREA_STATE_TABLE)} ("
                    "import_review_area_state_id, import_job_id, area_key, area_order, status, confirmed_at, "
                    "confirmed_by, updated_at, updated_by"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                ),
                (
                    f"imras-{uuid.uuid4()}",
                    job_id,
                    area_key,
                    idx,
                    status,
                    None,
                    None,
                    now,
                    actor_ref,
                ),
            )
            inserted += 1
        self._cache_clear()
        return inserted

    def list_import_review_area_states(self, *, import_job_id: str) -> list[dict[str, Any]]:
        if not self._import_review_area_state_table_available():
            return []
        job_id = str(import_job_id or "").strip()
        if not job_id:
            return []
        frame = self._query_or_empty(
            (
                f"SELECT * FROM {self._table(IMPORT_REVIEW_AREA_STATE_TABLE)} "
                "WHERE import_job_id = %s ORDER BY area_order ASC"
            ),
            params=(job_id,),
            columns=[],
        )
        if frame.empty:
            return []
        return [
            {
                "import_review_area_state_id": str(row.get("import_review_area_state_id") or "").strip(),
                "import_job_id": str(row.get("import_job_id") or "").strip(),
                "area_key": str(row.get("area_key") or "").strip().lower(),
                "area_order": int(row.get("area_order") or 0),
                "status": str(row.get("status") or "").strip().lower(),
                "confirmed_at": str(row.get("confirmed_at") or "").strip(),
                "confirmed_by": str(row.get("confirmed_by") or "").strip(),
                "updated_at": str(row.get("updated_at") or "").strip(),
                "updated_by": str(row.get("updated_by") or "").strip(),
            }
            for row in frame.to_dict("records")
        ]

    def confirm_import_review_area(
        self,
        *,
        import_job_id: str,
        area_key: str,
        actor_user_principal: str,
    ) -> dict[str, Any]:
        if not self._import_review_area_state_table_available():
            return {"confirmed": False, "next_area_key": ""}
        job_id = str(import_job_id or "").strip()
        target_area = str(area_key or "").strip().lower()
        if not job_id or not target_area:
            return {"confirmed": False, "next_area_key": ""}
        states = self.list_import_review_area_states(import_job_id=job_id)
        if not states:
            return {"confirmed": False, "next_area_key": ""}
        selected = next((row for row in states if str(row.get("area_key") or "") == target_area), None)
        if selected is None:
            raise ValueError("Unknown review area.")
        if str(selected.get("status") or "") not in {"in_progress", "confirmed"}:
            raise ValueError("This review area is locked.")
        now = self._now().isoformat()
        actor_ref = self._actor_ref(actor_user_principal)
        self.client.execute(
            (
                f"UPDATE {self._table(IMPORT_REVIEW_AREA_STATE_TABLE)} "
                "SET status = %s, confirmed_at = %s, confirmed_by = %s, updated_at = %s, updated_by = %s "
                "WHERE import_job_id = %s AND lower(area_key) = lower(%s)"
            ),
            ("confirmed", now, actor_ref, now, actor_ref, job_id, target_area),
        )
        ordered = sorted(states, key=lambda row: int(row.get("area_order") or 0))
        next_area = ""
        selected_order = int(selected.get("area_order") or 0)
        for row in ordered:
            if int(row.get("area_order") or 0) <= selected_order:
                continue
            if str(row.get("status") or "").strip().lower() == "locked":
                next_area = str(row.get("area_key") or "").strip().lower()
                self.client.execute(
                    (
                        f"UPDATE {self._table(IMPORT_REVIEW_AREA_STATE_TABLE)} "
                        "SET status = %s, updated_at = %s, updated_by = %s "
                        "WHERE import_job_id = %s AND lower(area_key) = lower(%s)"
                    ),
                    ("in_progress", now, actor_ref, job_id, next_area),
                )
                break
        self._cache_clear()
        return {"confirmed": True, "next_area_key": next_area}

    def list_import_review_rows(
        self,
        *,
        import_job_id: str,
        area_key: str,
    ) -> list[dict[str, Any]]:
        return self.list_import_stage_rows(import_job_id=import_job_id, area_key=area_key)

    def log_import_workflow_event(
        self,
        *,
        import_job_id: str,
        old_status: str,
        new_status: str,
        actor_user_principal: str,
        notes: str,
    ) -> None:
        try:
            self._execute_file(
                "inserts/create_workflow_event.sql",
                params=(
                    str(uuid.uuid4()),
                    "import_job",
                    str(import_job_id or "").strip(),
                    str(old_status or "").strip() or None,
                    str(new_status or "").strip() or None,
                    self._actor_ref(actor_user_principal),
                    self._now(),
                    str(notes or "").strip() or None,
                ),
                audit_workflow_event=self._table("audit_workflow_event"),
            )
        except Exception:
            LOGGER.debug("Failed to write import workflow event for '%s'.", import_job_id, exc_info=True)

    def list_import_stage_area_rows(
        self,
        *,
        import_job_id: str,
        area_key: str,
    ) -> list[dict[str, Any]]:
        job_id = str(import_job_id or "").strip()
        normalized_area = str(area_key or "").strip().lower()
        table_name = str(IMPORT_STAGE_AREA_TABLES.get(normalized_area) or "").strip()
        if not job_id or not table_name:
            return []
        frame = self._query_or_empty(
            (
                f"SELECT import_stage_area_row_id, import_job_id, row_index, line_number, area_payload_json, created_at "
                f"FROM {self._table(table_name)} WHERE import_job_id = %s ORDER BY row_index ASC"
            ),
            params=(job_id,),
            columns=[
                "import_stage_area_row_id",
                "import_job_id",
                "row_index",
                "line_number",
                "area_payload_json",
                "created_at",
            ],
        )
        if frame.empty:
            return []
        out: list[dict[str, Any]] = []
        for row in frame.to_dict("records"):
            payload = dict(self._safe_json_loads(row.get("area_payload_json"), expected=dict))
            out.append(
                {
                    "import_stage_area_row_id": str(row.get("import_stage_area_row_id") or "").strip(),
                    "import_job_id": str(row.get("import_job_id") or "").strip(),
                    "row_index": int(row.get("row_index") or 0),
                    "line_number": str(row.get("line_number") or "").strip(),
                    "payload": payload,
                    "source_group_key": str(payload.get("__source_group_key") or payload.get("source_group_key") or "__static__"),
                    "created_at": str(row.get("created_at") or "").strip(),
                }
            )
        return out

    def clear_import_stage_area_rows(
        self,
        *,
        import_job_id: str,
        area_key: str = "",
    ) -> int:
        job_id = str(import_job_id or "").strip()
        if not job_id:
            return 0
        cleaned_area = str(area_key or "").strip().lower()
        if cleaned_area:
            table_name = str(IMPORT_STAGE_AREA_TABLES.get(cleaned_area) or "").strip()
            if not table_name:
                return 0
            self.client.execute(
                f"DELETE FROM {self._table(table_name)} WHERE import_job_id = %s",
                (job_id,),
            )
            self._cache_clear()
            return 1
        for table_name in IMPORT_STAGE_AREA_TABLES.values():
            self.client.execute(
                f"DELETE FROM {self._table(table_name)} WHERE import_job_id = %s",
                (job_id,),
            )
        self._cache_clear()
        return 1

    def list_import_lookup_candidates(
        self,
        *,
        import_job_id: str = "",
        status: str = "all",
        lookup_type: str = "",
    ) -> list[dict[str, Any]]:
        if not self._import_lookup_candidate_table_available():
            return []

        where_parts = ["1 = 1"]
        params: list[Any] = []
        job_id = str(import_job_id or "").strip()
        if job_id:
            where_parts.append("import_job_id = %s")
            params.append(job_id)

        normalized_status = str(status or "all").strip().lower()
        if normalized_status and normalized_status != "all":
            where_parts.append("lower(status) = lower(%s)")
            params.append(normalized_status)

        normalized_lookup_type = str(lookup_type or "").strip().lower()
        if normalized_lookup_type:
            where_parts.append("lower(lookup_type) = lower(%s)")
            params.append(normalized_lookup_type)

        frame = self._query_or_empty(
            (
                "SELECT " + ", ".join(IMPORT_LOOKUP_CANDIDATE_FIELDS)
                + f" FROM {self._table(IMPORT_LOOKUP_CANDIDATE_TABLE)} "
                + f"WHERE {' AND '.join(where_parts)} "
                + "ORDER BY created_at DESC, row_index ASC, lookup_type ASC, option_code ASC"
            ),
            params=tuple(params),
            columns=list(IMPORT_LOOKUP_CANDIDATE_FIELDS),
        )
        if frame.empty:
            return []

        out: list[dict[str, Any]] = []
        for row in frame.to_dict("records"):
            out.append(
                {
                    "candidate_id": str(row.get("candidate_id") or "").strip(),
                    "import_job_id": str(row.get("import_job_id") or "").strip(),
                    "area_key": str(row.get("area_key") or "").strip().lower(),
                    "row_index": int(row.get("row_index") or 0),
                    "lookup_type": str(row.get("lookup_type") or "").strip().lower(),
                    "option_code": str(row.get("option_code") or "").strip(),
                    "option_label": str(row.get("option_label") or "").strip(),
                    "status": str(row.get("status") or "").strip().lower(),
                    "review_note": str(row.get("review_note") or "").strip(),
                    "reviewed_by": str(row.get("reviewed_by") or "").strip(),
                    "reviewed_at": str(row.get("reviewed_at") or "").strip(),
                    "created_at": str(row.get("created_at") or "").strip(),
                    "created_by": str(row.get("created_by") or "").strip(),
                }
            )
        return out

    def count_import_lookup_candidates(
        self,
        *,
        import_job_id: str = "",
        status: str = "all",
    ) -> int:
        return int(
            len(
                self.list_import_lookup_candidates(
                    import_job_id=import_job_id,
                    status=status,
                )
            )
        )

    def clear_import_lookup_candidates(
        self,
        *,
        import_job_id: str,
    ) -> int:
        if not self._import_lookup_candidate_table_available():
            return 0
        job_id = str(import_job_id or "").strip()
        if not job_id:
            return 0
        self.client.execute(
            f"DELETE FROM {self._table(IMPORT_LOOKUP_CANDIDATE_TABLE)} WHERE import_job_id = %s",
            (job_id,),
        )
        self._cache_clear()
        return 1

    def upsert_import_lookup_candidate(
        self,
        *,
        import_job_id: str,
        area_key: str,
        row_index: int,
        lookup_type: str,
        option_code: str,
        option_label: str,
        actor_user_principal: str,
        status: str = "pending",
    ) -> str:
        if not self._import_lookup_candidate_table_available():
            return ""

        job_id = str(import_job_id or "").strip()
        lookup_key = str(lookup_type or "").strip().lower()
        code = str(option_code or "").strip()
        if not job_id or not lookup_key or not code:
            return ""
        normalized_status = str(status or "pending").strip().lower() or "pending"
        now = self._now().isoformat()
        actor_ref = str(actor_user_principal or "").strip() or "system"
        cleaned_label = str(option_label or "").strip() or code
        normalized_area = str(area_key or "").strip().lower() or None
        normalized_row_index = int(row_index or 0) or None

        existing = self._query_or_empty(
            (
                "SELECT candidate_id FROM "
                + self._table(IMPORT_LOOKUP_CANDIDATE_TABLE)
                + " WHERE import_job_id = %s AND lower(lookup_type) = lower(%s) AND lower(option_code) = lower(%s)"
            ),
            params=(job_id, lookup_key, code),
            columns=["candidate_id"],
        )
        if existing.empty:
            candidate_id = f"imcand-{uuid.uuid4()}"
            self.client.execute(
                (
                    f"INSERT INTO {self._table(IMPORT_LOOKUP_CANDIDATE_TABLE)} ("
                    "candidate_id, import_job_id, area_key, row_index, lookup_type, option_code, option_label, "
                    "status, review_note, reviewed_by, reviewed_at, created_at, created_by"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                ),
                (
                    candidate_id,
                    job_id,
                    normalized_area,
                    normalized_row_index,
                    lookup_key,
                    code,
                    cleaned_label,
                    normalized_status,
                    None,
                    None,
                    None,
                    now,
                    actor_ref,
                ),
            )
        else:
            candidate_id = str(existing.iloc[0].to_dict().get("candidate_id") or "").strip()
            if not candidate_id:
                return ""
            self.client.execute(
                (
                    f"UPDATE {self._table(IMPORT_LOOKUP_CANDIDATE_TABLE)} "
                    "SET area_key = %s, row_index = %s, option_label = %s, status = %s, "
                    "review_note = NULL, reviewed_by = NULL, reviewed_at = NULL "
                    "WHERE candidate_id = %s"
                ),
                (
                    normalized_area,
                    normalized_row_index,
                    cleaned_label,
                    normalized_status,
                    candidate_id,
                ),
            )
        self._cache_clear()
        return candidate_id

    def review_import_lookup_candidate(
        self,
        *,
        candidate_id: str,
        decision: str,
        review_note: str,
        actor_user_principal: str,
        create_lookup_option_on_approve: bool = True,
    ) -> dict[str, Any] | None:
        if not self._import_lookup_candidate_table_available():
            return None

        target_id = str(candidate_id or "").strip()
        if not target_id:
            return None
        current_rows = self.list_import_lookup_candidates()
        current = next((row for row in current_rows if str(row.get("candidate_id") or "") == target_id), None)
        if current is None:
            return None

        normalized_decision = str(decision or "").strip().lower()
        if normalized_decision not in {"pending", "approved", "rejected"}:
            normalized_decision = "pending"
        note_value = str(review_note or "").strip() or None
        actor_ref = str(actor_user_principal or "").strip() or "system"
        reviewed_at = self._now().isoformat()

        if normalized_decision == "approved" and create_lookup_option_on_approve and hasattr(self, "list_lookup_options"):
            lookup_type = str(current.get("lookup_type") or "").strip().lower()
            option_code = str(current.get("option_code") or "").strip()
            option_label = str(current.get("option_label") or "").strip()
            if lookup_type and option_code and hasattr(self, "save_lookup_option"):
                try:
                    existing = self.list_lookup_options(lookup_type, active_only=False)
                except Exception:
                    existing = pd.DataFrame(columns=["option_code", "sort_order"])
                code_exists = False
                if existing is not None and not existing.empty:
                    existing_codes = {
                        str(item).strip().lower()
                        for item in existing.get("option_code", pd.Series(dtype="object")).tolist()
                        if str(item).strip()
                    }
                    code_exists = option_code.lower() in existing_codes
                if not code_exists:
                    next_sort = 100
                    if existing is not None and not existing.empty and "sort_order" in existing.columns:
                        try:
                            sort_values = pd.to_numeric(existing["sort_order"], errors="coerce").dropna().astype(int)
                            if not sort_values.empty:
                                next_sort = int(sort_values.max()) + 10
                        except Exception:
                            next_sort = 100
                    self.save_lookup_option(
                        option_id=None,
                        lookup_type=lookup_type,
                        option_code=option_code,
                        option_label=option_label or option_code,
                        sort_order=max(1, int(next_sort)),
                        valid_from_ts=self._now(),
                        valid_to_ts=None,
                        updated_by=actor_ref,
                    )

        self.client.execute(
            (
                f"UPDATE {self._table(IMPORT_LOOKUP_CANDIDATE_TABLE)} "
                "SET status = %s, review_note = %s, reviewed_by = %s, reviewed_at = %s "
                "WHERE candidate_id = %s"
            ),
            (
                normalized_decision,
                note_value,
                actor_ref,
                reviewed_at,
                target_id,
            ),
        )
        self._cache_clear()
        refreshed = self.list_import_lookup_candidates()
        return next((row for row in refreshed if str(row.get("candidate_id") or "") == target_id), None)

    def create_import_stage_job(
        self,
        *,
        layout_key: str,
        source_system: str,
        source_object: str | None,
        file_name: str | None,
        file_type: str | None,
        detected_format: str | None,
        parser_config: dict[str, Any] | None,
        row_count: int,
        actor_user_principal: str,
    ) -> str:
        import_job_id = f"imjob-{uuid.uuid4()}"
        now = self._now().isoformat()
        self._execute_file(
            "inserts/create_import_stage_job.sql",
            params=(
                import_job_id,
                str(layout_key or "").strip().lower(),
                str(source_system or "").strip().lower() or "unknown",
                (str(source_object or "").strip() or None),
                (str(file_name or "").strip() or None),
                (str(file_type or "").strip().lower() or None),
                (str(detected_format or "").strip().lower() or None),
                (json.dumps(parser_config or {}, default=str) if parser_config else None),
                None,
                None,
                json.dumps({}, default=str),
                int(row_count or 0),
                "staged",
                0,
                0,
                0,
                0,
                None,
                now,
                str(actor_user_principal or "").strip() or "system",
                None,
                None,
            ),
            app_import_job=self._table("app_import_job"),
        )
        return import_job_id

    def create_import_stage_rows(
        self,
        *,
        import_job_id: str,
        preview_rows: list[dict[str, Any]],
    ) -> int:
        if not import_job_id or not preview_rows:
            return 0

        statement = self._sql(
            "inserts/create_import_stage_row.sql",
            app_import_stage_row=self._table("app_import_stage_row"),
        )
        now = self._now().isoformat()
        staged_count = 0
        for row in preview_rows:
            row_index = int(row.get("row_index") or 0)
            if row_index <= 0:
                continue
            staged_count += 1
            stage_row_id = f"imrow-{uuid.uuid4()}"
            payload = {
                "line_number": str(row.get("line_number") or ""),
                "row_data": dict(row.get("row_data") or {}),
                "notes": list(row.get("notes") or []),
                "errors": list(row.get("errors") or []),
                "row_status": str(row.get("row_status") or ""),
                "source_row_raw": copy.deepcopy(dict(row.get("source_row_raw") or {})),
                "unmapped_source_fields": copy.deepcopy(dict(row.get("unmapped_source_fields") or {})),
                "mapping_profile_id": str(row.get("mapping_profile_id") or ""),
                "resolved_record_selector": str(row.get("resolved_record_selector") or ""),
            }
            self.client.execute(
                statement,
                (
                    stage_row_id,
                    import_job_id,
                    row_index,
                    str(row.get("line_number") or None) if row.get("line_number") else None,
                    str(row.get("area_key") or "").strip().lower() or None,
                    str(row.get("source_group_key") or "").strip() or None,
                    json.dumps(payload, default=str),
                    str(row.get("suggested_action") or "").strip().lower() or None,
                    str(row.get("suggested_target_id") or "").strip() or None,
                    str(row.get("decision_action") or "").strip().lower() or None,
                    str(row.get("decision_target_id") or "").strip() or None,
                    json.dumps(dict(row.get("decision_payload") or {}), default=str)
                    if dict(row.get("decision_payload") or {})
                    else None,
                    str(row.get("decision_updated_at") or None) if row.get("decision_updated_at") else None,
                    str(row.get("decision_updated_by") or "").strip() or None,
                    now,
                ),
            )
        self._cache_clear()
        return staged_count

    def finalize_import_stage_job(
        self,
        *,
        import_job_id: str,
        created_count: int,
        merged_count: int,
        skipped_count: int,
        failed_count: int,
        actor_user_principal: str,
        error_message: str | None = None,
    ) -> None:
        if not import_job_id:
            return
        final_status = "applied" if int(failed_count or 0) == 0 else "applied_with_errors"
        self._execute_file(
            "updates/finalize_import_stage_job.sql",
            params=(
                final_status,
                int(created_count or 0),
                int(merged_count or 0),
                int(skipped_count or 0),
                int(failed_count or 0),
                (str(error_message or "").strip() or None),
                self._now().isoformat(),
                str(actor_user_principal or "").strip() or "system",
                import_job_id,
            ),
            app_import_job=self._table("app_import_job"),
        )

    def create_import_stage_area_rows(
        self,
        *,
        import_job_id: str,
        stage_area_rows: dict[str, list[dict[str, Any]]],
    ) -> int:
        if not import_job_id or not stage_area_rows:
            return 0
        staged_count = 0
        now = self._now().isoformat()
        for area_key, rows in dict(stage_area_rows or {}).items():
            area = str(area_key or "").strip().lower()
            table_name = str(IMPORT_STAGE_AREA_TABLES.get(area) or "").strip()
            if not table_name:
                continue
            statement = self._sql(
                "inserts/create_import_stage_area_row.sql",
                area_stage_table=self._table(table_name),
            )
            for row in list(rows or []):
                payload = dict(row.get("payload") or {})
                if not payload:
                    continue
                source_group_key = str(row.get("source_group_key") or "__static__").strip() or "__static__"
                if "__source_group_key" not in payload:
                    payload["__source_group_key"] = source_group_key
                try:
                    self.client.execute(
                        statement,
                        (
                            f"imarea-{uuid.uuid4()}",
                            import_job_id,
                            int(row.get("row_index") or 0),
                            str(row.get("line_number") or None) if row.get("line_number") else None,
                            json.dumps(payload, default=str),
                            now,
                        ),
                    )
                    staged_count += 1
                except Exception:
                    # Area staging should not block core import stage behavior.
                    continue
        if staged_count:
            self._cache_clear()
        return staged_count
