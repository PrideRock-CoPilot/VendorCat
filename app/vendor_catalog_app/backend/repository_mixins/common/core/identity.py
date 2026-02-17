from __future__ import annotations

import logging
import re
import uuid
from typing import Any

import pandas as pd

from vendor_catalog_app.core.env import TVENDOR_USER_DIRECTORY_TOUCH_TTL_SEC, get_env
from vendor_catalog_app.core.repository_constants import UNKNOWN_USER_PRINCIPAL
from vendor_catalog_app.infrastructure.db import DataConnectionError, DataExecutionError

LOGGER = logging.getLogger(__name__)


class RepositoryCoreIdentityMixin:
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
                "employee_id": None,
                "manager_id": None,
                "first_name": None,
                "last_name": None,
                "display_name": "Unknown User",
            }

        email: str | None = None
        network_id: str | None = None
        if "@" in login_identifier:
            email = login_identifier
            network_id = login_identifier.split("@", 1)[0].strip() or None
        if "\\" in login_identifier or "/" in login_identifier:
            parsed_network = login_identifier.split("\\")[-1].split("/")[-1].strip()
            if parsed_network:
                network_id = parsed_network
        elif network_id is None and login_identifier and not login_identifier.lower().startswith("usr-"):
            network_id = login_identifier

        display_name = RepositoryCoreIdentityMixin._principal_to_display_name(login_identifier)
        parts = [part for part in display_name.split(" ") if part and part.lower() != "user"]
        first_name = parts[0] if parts else None
        last_name = " ".join(parts[1:]) if len(parts) > 1 else None

        return {
            "login_identifier": login_identifier,
            "email": email,
            "network_id": network_id,
            "employee_id": None,
            "manager_id": None,
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
        for key in (
            "email",
            "network_id",
            "employee_id",
            "manager_id",
            "first_name",
            "last_name",
            "display_name",
        ):
            if key not in overrides:
                continue
            raw = overrides.get(key)
            value = str(raw or "").strip()
            if value:
                merged[key] = value
        return merged

    @staticmethod
    def _is_system_login_identifier(login_identifier: str) -> bool:
        normalized = str(login_identifier or "").strip().lower()
        return (
            not normalized
            or normalized == UNKNOWN_USER_PRINCIPAL.lower()
            or normalized.startswith("system:")
        )

    def _lookup_employee_directory_identity(self, user_value: str) -> dict[str, str | None] | None:
        cleaned = str(user_value or "").strip()
        if not cleaned:
            return None
        try:
            directory = self._query_file(
                "ingestion/select_employee_directory_by_identity.sql",
                params=(cleaned, cleaned, cleaned, cleaned),
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
        except (DataExecutionError, DataConnectionError):
            LOGGER.warning(
                "Failed employee directory lookup for '%s'.",
                cleaned,
                exc_info=True,
            )
            return None
        if directory.empty:
            return None

        row = directory.iloc[0].to_dict()
        login_identifier = str(row.get("login_identifier") or "").strip()
        if not login_identifier:
            return None
        active_flag = str(row.get("active_flag", "")).strip().lower()
        if active_flag in {"0", "false", "no", "n"}:
            return None

        display_name = (
            str(row.get("display_name") or "").strip()
            or self._principal_to_display_name(login_identifier)
        )
        return {
            "login_identifier": login_identifier,
            "email": str(row.get("email") or "").strip() or None,
            "network_id": str(row.get("network_id") or "").strip() or None,
            "employee_id": str(row.get("employee_id") or "").strip() or None,
            "manager_id": str(row.get("manager_id") or "").strip() or None,
            "first_name": str(row.get("first_name") or "").strip() or None,
            "last_name": str(row.get("last_name") or "").strip() or None,
            "display_name": display_name,
        }

    def sync_user_directory_identity(
        self,
        *,
        login_identifier: str,
        email: str | None = None,
        network_id: str | None = None,
        employee_id: str | None = None,
        manager_id: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        display_name: str | None = None,
    ) -> str:
        return self._ensure_user_directory_entry(
            login_identifier,
            identity_overrides={
                "email": email,
                "network_id": network_id,
                "employee_id": employee_id,
                "manager_id": manager_id,
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
        directory_identity = self._lookup_employee_directory_identity(login_identifier)
        if directory_identity is not None:
            login_identifier = str(directory_identity.get("login_identifier") or "").strip() or login_identifier
            identity = self._merge_user_identity(identity, directory_identity)
        require_employee_directory = not self._is_system_login_identifier(login_identifier)
        if (
            require_employee_directory
            and getattr(self.config, "use_local_db", False)
            and getattr(self.config, "is_dev_env", False)
            and getattr(self.config, "dev_allow_all_access", False)
        ):
            # Dev launcher convenience mode: local-only runs can bootstrap ad-hoc users.
            require_employee_directory = False
        if require_employee_directory and directory_identity is None:
            raise ValueError(
                "User must exist in vw_employee_directory before being used in the application."
            )

        now = self._now()
        existing = self._query_file(
            "ingestion/select_user_directory_by_login.sql",
            params=(login_identifier,),
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
                "employee_id": str(identity.get("employee_id") or "").strip()
                or str(existing_row.get("employee_id") or "").strip()
                or None,
                "manager_id": str(identity.get("manager_id") or "").strip()
                or str(existing_row.get("manager_id") or "").strip()
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
            field_changed = any(
                str(merged_identity.get(field) or "").strip() != str(existing_row.get(field) or "").strip()
                for field in (
                    "email",
                    "network_id",
                    "employee_id",
                    "manager_id",
                    "first_name",
                    "last_name",
                    "display_name",
                )
            )
            raw_touch_ttl = get_env(TVENDOR_USER_DIRECTORY_TOUCH_TTL_SEC, "300")
            try:
                touch_ttl_sec = max(0, int(str(raw_touch_ttl).strip() or "300"))
            except Exception:
                touch_ttl_sec = 300
            should_touch_last_seen = True
            if touch_ttl_sec > 0:
                last_seen_at = self._parse_lookup_ts(existing_row.get("last_seen_at"), fallback=now)
                should_touch_last_seen = (now - last_seen_at).total_seconds() >= float(touch_ttl_sec)

            if not field_changed and not should_touch_last_seen:
                return user_id
            try:
                self._execute_file(
                    "updates/update_user_directory_profile.sql",
                    params=(
                        merged_identity["email"],
                        merged_identity["network_id"],
                        merged_identity["employee_id"],
                        merged_identity["manager_id"],
                        merged_identity["first_name"],
                        merged_identity["last_name"],
                        merged_identity["display_name"],
                        now,
                        now,
                        user_id,
                    ),
                    app_user_directory=self._table("app_user_directory"),
                )
            except (DataExecutionError, DataConnectionError) as exc:
                LOGGER.warning("Failed to update user directory profile for '%s'.", login_identifier, exc_info=True)
                if require_employee_directory:
                    raise RuntimeError("Could not update app user directory profile.") from exc
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
                    identity["employee_id"],
                    identity["manager_id"],
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
        except (DataExecutionError, DataConnectionError) as exc:
            LOGGER.warning("Failed to create user directory record for '%s'.", login_identifier, exc_info=True)
            if require_employee_directory:
                raise RuntimeError("Could not create app user directory record.") from exc
            return login_identifier

    def _actor_ref(self, user_principal: str) -> str:
        return self.resolve_user_id(user_principal, allow_create=True) or UNKNOWN_USER_PRINCIPAL

    def _user_display_lookup(self) -> dict[str, str]:
        def _load() -> dict[str, str]:
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

        return self._cached(("user_display_lookup",), _load, ttl_seconds=120)

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

