from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

import pandas as pd

from vendor_catalog_app.infrastructure.db import DataConnectionError, DataExecutionError, DataQueryError
from vendor_catalog_app.core.repository_constants import UNKNOWN_USER_PRINCIPAL
from vendor_catalog_app.core.repository_errors import SchemaBootstrapRequiredError

LOGGER = logging.getLogger(__name__)

class RepositoryIdentityMixin:
    def ensure_runtime_tables(self) -> None:
        if self._runtime_tables_ensured:
            return
        if self.config.use_local_db:
            self._local_table_columns("core_vendor")
            self._local_table_columns("sec_user_role_map")
            self._local_table_columns("app_user_settings")
            self._local_table_columns("app_user_directory")
            self._ensure_local_lookup_option_table()
            self._ensure_local_offering_columns()
            self._ensure_local_offering_extension_tables()
            self._runtime_tables_ensured = True
            return

        try:
            self._probe_file("health/select_connectivity_check.sql")
        except Exception as exc:
            raise SchemaBootstrapRequiredError(
                "Databricks connection failed before schema validation. "
                "Verify DATABRICKS_SERVER_HOSTNAME (or DATABRICKS_HOST), DATABRICKS_HTTP_PATH "
                "(or DATABRICKS_WAREHOUSE_ID), OAuth credentials "
                "(DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET) or DATABRICKS_TOKEN, "
                "and SQL warehouse/network access. "
                f"Configured schema: {self.config.fq_schema}. "
                f"Connection error: {exc}"
            ) from exc

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
                self._probe_file(
                    "health/select_runtime_table_probe.sql",
                    table_name=self._table(table_name),
                )
            except (DataQueryError, DataConnectionError):
                missing_or_blocked.append(self._table(table_name))

        try:
            self._probe_file(
                "health/select_runtime_offering_columns_probe.sql",
                core_vendor_offering=self._table("core_vendor_offering"),
            )
        except (DataQueryError, DataConnectionError):
            missing_or_blocked.append(f"{self._table('core_vendor_offering')}.lob")
            missing_or_blocked.append(f"{self._table('core_vendor_offering')}.service_type")
        try:
            self._probe_file(
                "health/select_runtime_lookup_scd_probe.sql",
                app_lookup_option=self._table("app_lookup_option"),
            )
        except (DataQueryError, DataConnectionError):
            missing_or_blocked.append(f"{self._table('app_lookup_option')}.valid_from_ts")
            missing_or_blocked.append(f"{self._table('app_lookup_option')}.valid_to_ts")
            missing_or_blocked.append(f"{self._table('app_lookup_option')}.is_current")
            missing_or_blocked.append(f"{self._table('app_lookup_option')}.deleted_flag")
        try:
            self._probe_file(
                "health/select_runtime_employee_directory_probe.sql",
                employee_directory_view=self._employee_directory_view(),
            )
        except (DataQueryError, DataConnectionError):
            missing_or_blocked.append(self._employee_directory_view())

        if missing_or_blocked:
            raise SchemaBootstrapRequiredError(
                "Databricks schema is not initialized or access is blocked. "
                "Run the bootstrap SQL manually before starting the app: "
                f"{self.config.schema_bootstrap_sql_path}. "
                f"Configured schema: {self.config.fq_schema}. "
                f"Missing/inaccessible objects: {', '.join(missing_or_blocked)}"
            )

        self._runtime_tables_ensured = True

    def bootstrap_user_access(self, user_principal: str, group_principals: set[str] | None = None) -> set[str]:
        self._ensure_user_directory_entry(user_principal)
        roles = self.get_user_roles(user_principal, group_principals=group_principals)
        return roles

    def ensure_user_record(self, user_principal: str) -> None:
        user_ref = self.resolve_user_id(user_principal, allow_create=True)
        if not user_ref:
            return

        current = self._query_file(
            "ingestion/select_user_role_presence.sql",
            params=(user_ref,),
            columns=["has_role"],
            sec_user_role_map=self._table("sec_user_role_map"),
        )
        if not current.empty:
            return

        now = self._now()
        try:
            self._execute_file(
                "inserts/grant_role.sql",
                params=(user_ref, "vendor_viewer", True, "system:auto-bootstrap", now, None),
                sec_user_role_map=self._table("sec_user_role_map"),
            )
            self._audit_access(
                actor_user_principal="system:auto-bootstrap",
                action_type="auto_provision_viewer",
                target_user_principal=user_ref,
                target_role="vendor_viewer",
                notes="User auto-provisioned with basic view rights.",
            )
        except (DataExecutionError, DataConnectionError):
            # If role table is unavailable or write is blocked, app still falls back to view-only in UI.
            LOGGER.warning(
                "Failed to auto-provision '%s' with vendor_viewer role.",
                user_principal,
                exc_info=True,
            )

    def get_user_setting(self, user_principal: str, setting_key: str) -> dict[str, Any]:
        user_ref = self.resolve_user_id(user_principal, allow_create=True) or user_principal

        def _load() -> dict[str, Any]:
            df = self._query_file(
                "ingestion/select_user_setting_latest.sql",
                params=(user_ref, setting_key),
                columns=["setting_value_json"],
                app_user_settings=self._table("app_user_settings"),
            )
            if df.empty:
                return {}
            try:
                return json.loads(str(df.iloc[0]["setting_value_json"]))
            except (json.JSONDecodeError, TypeError, ValueError):
                return {}

        return self._cached(
            ("user_setting", str(user_ref), str(setting_key)),
            _load,
            ttl_seconds=300,
        )

    def save_user_setting(self, user_principal: str, setting_key: str, setting_value: dict[str, Any]) -> None:
        user_ref = self.resolve_user_id(user_principal, allow_create=True) or user_principal
        now = self._now()
        payload = self._serialize_payload(setting_value)
        try:
            self._execute_file(
                "inserts/save_user_setting.sql",
                params=(str(uuid.uuid4()), user_ref, setting_key, payload, now, user_ref),
                app_user_settings=self._table("app_user_settings"),
            )
        except (DataExecutionError, DataConnectionError):
            LOGGER.debug("Failed to save user setting '%s' for '%s'.", setting_key, user_principal, exc_info=True)

    def log_usage_event(
        self, user_principal: str, page_name: str, event_type: str, payload: dict[str, Any] | None = None
    ) -> None:
        raw_enabled = os.getenv("TVENDOR_USAGE_LOG_ENABLED")
        if raw_enabled is None or not str(raw_enabled).strip():
            enabled = self.config.is_dev_env
        else:
            enabled = str(raw_enabled).strip().lower() in {"1", "true", "yes", "y", "on"}
        if not enabled:
            return
        if not self._allow_usage_event(
            user_principal=user_principal,
            page_name=page_name,
            event_type=event_type,
        ):
            return
        actor_ref = self._actor_ref(user_principal)
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
        except (DataExecutionError, DataConnectionError):
            LOGGER.debug("Failed to write usage event '%s' for '%s'.", event_type, user_principal, exc_info=True)

    def get_current_user(self) -> str:
        if self.config.use_local_db:
            return os.getenv("TVENDOR_TEST_USER", UNKNOWN_USER_PRINCIPAL)
        df = self._query_file(
            "ingestion/select_current_user.sql",
            columns=["user_principal"],
        )
        if df.empty:
            return UNKNOWN_USER_PRINCIPAL
        return str(df.iloc[0]["user_principal"])

    def _normalize_group_principals(self, group_principals: set[str] | None) -> set[str]:
        normalized: set[str] = set()
        normalize_group = getattr(self, "normalize_group_principal", None)
        for raw_value in group_principals or set():
            raw = str(raw_value or "").strip()
            if not raw:
                continue
            candidate = ""
            if callable(normalize_group):
                try:
                    candidate = str(normalize_group(raw) or "").strip()
                except Exception:
                    candidate = ""
            if not candidate:
                candidate = raw.lower()
            if candidate:
                normalized.add(candidate.lower())
        return normalized

    def _get_group_roles(self, group_principals: set[str]) -> set[str]:
        normalized_groups = self._normalize_group_principals(group_principals)
        if not normalized_groups:
            return set()
        placeholders = ", ".join(["?"] * len(normalized_groups))
        statement = self._sql(
            "ingestion/select_group_roles.sql",
            sec_group_role_map=self._table("sec_group_role_map"),
            group_placeholders=placeholders,
        )
        params = tuple(sorted(normalized_groups))
        df = self._query_or_empty(statement, params=params, columns=["role_code"])
        if df.empty:
            return set()
        return {str(role).strip() for role in df["role_code"].dropna().astype(str).tolist() if str(role).strip()}

    def get_user_roles(self, user_principal: str, group_principals: set[str] | None = None) -> set[str]:
        user_ref = self.resolve_user_id(user_principal, allow_create=True) or str(user_principal or "").strip()
        normalized_groups = self._normalize_group_principals(group_principals)

        def _load() -> set[str]:
            df = self._query_file(
                "ingestion/select_user_roles.sql",
                params=(user_ref,),
                columns=["role_code"],
                sec_user_role_map=self._table("sec_user_role_map"),
            )
            if df.empty and user_ref and user_ref != str(user_principal or "").strip():
                df = self._query_file(
                    "ingestion/select_user_roles.sql",
                    params=(str(user_principal or "").strip(),),
                    columns=["role_code"],
                    sec_user_role_map=self._table("sec_user_role_map"),
                )
            roles = set(df["role_code"].tolist()) if not df.empty else set()
            roles.update(self._get_group_roles(normalized_groups))
            return roles

        return self._cached(
            ("user_roles", str(user_ref).lower(), tuple(sorted(normalized_groups))),
            _load,
            ttl_seconds=120,
        )

    def get_user_display_name(self, user_principal: str) -> str:
        raw = str(user_principal or "").strip()
        if not raw:
            return "Unknown User"
        user_ref = self.resolve_user_id(raw, allow_create=False)
        if not user_ref and not raw.lower().startswith("usr-"):
            user_ref = self._ensure_user_directory_entry(raw)
        lookup = self._user_display_lookup()
        return lookup.get(user_ref) or lookup.get(raw) or lookup.get(raw.lower()) or self._principal_to_display_name(raw)

    def search_user_directory(self, q: str = "", limit: int = 20) -> pd.DataFrame:
        normalized_limit = max(1, min(int(limit or 20), 250))
        columns = ["user_id", "login_identifier", "display_name", "label"]
        cleaned_q = (q or "").strip()
        like_pattern = f"%{cleaned_q.lower()}%" if cleaned_q else ""
        df = self._query_file(
            "ingestion/select_employee_directory_search.sql",
            params=(
                cleaned_q.lower(),
                like_pattern,
                like_pattern,
                like_pattern,
                like_pattern,
                like_pattern,
                like_pattern,
                like_pattern,
                like_pattern,
            ),
            columns=[
                "login_identifier",
                "display_name",
                "email",
                "network_id",
                "employee_id",
                "manager_id",
                "first_name",
                "last_name",
            ],
            employee_directory_view=self._employee_directory_view(),
            limit=normalized_limit,
        )

        if df.empty:
            return pd.DataFrame(columns=columns)

        for field in (
            "login_identifier",
            "display_name",
            "email",
            "network_id",
            "employee_id",
            "manager_id",
            "first_name",
            "last_name",
        ):
            if field not in df.columns:
                df[field] = ""
            df[field] = df[field].fillna("").astype(str).str.strip()

        df = df[df["login_identifier"] != ""].copy()
        if df.empty:
            return pd.DataFrame(columns=columns)

        df = df.sort_values(["display_name", "login_identifier"], ascending=[True, True])
        df = df.drop_duplicates(subset=["login_identifier"], keep="first")
        df["user_id"] = ""
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

    def get_employee_directory_status_map(self, principals: list[str]) -> dict[str, dict[str, Any]]:
        status_map: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        for raw_principal in principals or []:
            principal = str(raw_principal or "").strip()
            if not principal:
                continue
            normalized = principal.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            status_map[normalized] = {
                "principal": principal,
                "status": "missing",
                "active": False,
                "login_identifier": None,
                "display_name": None,
            }
            try:
                df = self._query_file(
                    "ingestion/select_employee_directory_status_by_identity.sql",
                    params=(principal, principal, principal, principal),
                    columns=[
                        "login_identifier",
                        "email",
                        "network_id",
                        "employee_id",
                        "manager_id",
                        "first_name",
                        "last_name",
                        "display_name",
                        "active_flag",
                    ],
                    employee_directory_view=self._employee_directory_view(),
                )
            except Exception:
                continue
            if df.empty:
                continue
            row = df.iloc[0].to_dict()
            login_identifier = str(row.get("login_identifier") or "").strip() or None
            display_name = str(row.get("display_name") or "").strip() or None
            active_text = str(row.get("active_flag", "")).strip().lower()
            active = active_text not in {"0", "false", "no", "n"}
            status_map[normalized] = {
                "principal": principal,
                "status": "active" if active else "inactive",
                "active": active,
                "login_identifier": login_identifier,
                "display_name": display_name,
            }
        return status_map

    def resolve_user_login_identifier(self, user_value: str) -> str | None:
        cleaned = str(user_value or "").strip()
        if not cleaned:
            return None

        employee_match = self._lookup_employee_directory_identity(cleaned)
        if employee_match is not None:
            return str(employee_match.get("login_identifier") or "").strip() or None

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

    def get_user_directory_profile(self, user_value: str | None) -> dict[str, Any] | None:
        cleaned = str(user_value or "").strip()
        if not cleaned:
            return None
        if cleaned.lower().startswith("usr-"):
            df = self._query_file(
                "ingestion/select_user_directory_by_user_id.sql",
                params=(cleaned,),
                columns=[
                    "user_id",
                    "login_identifier",
                    "email",
                    "network_id",
                    "employee_id",
                    "manager_id",
                    "first_name",
                    "last_name",
                    "display_name",
                    "active_flag",
                    "last_seen_at",
                ],
                app_user_directory=self._table("app_user_directory"),
            )
        else:
            df = self._query_file(
                "ingestion/select_user_directory_by_login.sql",
                params=(cleaned,),
                columns=[
                    "user_id",
                    "login_identifier",
                    "email",
                    "network_id",
                    "employee_id",
                    "manager_id",
                    "first_name",
                    "last_name",
                    "display_name",
                    "active_flag",
                    "last_seen_at",
                ],
                app_user_directory=self._table("app_user_directory"),
            )
        if df.empty:
            return None
        return df.iloc[0].to_dict()

    def resolve_user_id(self, user_value: str | None, *, allow_create: bool = False) -> str | None:
        cleaned = str(user_value or "").strip()
        if not cleaned:
            return None
        if cleaned.lower().startswith("usr-"):
            return cleaned

        exact = self._query_file(
            "ingestion/select_user_directory_by_login.sql",
            params=(cleaned,),
            columns=["user_id"],
            app_user_directory=self._table("app_user_directory"),
        )
        if not exact.empty:
            return str(exact.iloc[0]["user_id"]).strip()

        employee_match = self._lookup_employee_directory_identity(cleaned)
        resolved_login = (
            str(employee_match.get("login_identifier") or "").strip()
            if employee_match is not None
            else self.resolve_user_login_identifier(cleaned)
        )
        if resolved_login:
            if allow_create or employee_match is not None:
                return self._ensure_user_directory_entry(resolved_login)
            resolved = self._query_file(
                "ingestion/select_user_directory_by_login.sql",
                params=(resolved_login,),
                columns=["user_id"],
                app_user_directory=self._table("app_user_directory"),
            )
            if not resolved.empty:
                return str(resolved.iloc[0]["user_id"]).strip()

        if allow_create:
            return self._ensure_user_directory_entry(cleaned)
        return None

