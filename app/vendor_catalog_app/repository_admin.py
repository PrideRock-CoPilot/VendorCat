"""Admin and RBAC repository helpers."""

from __future__ import annotations

import re
import uuid
from typing import Any

import pandas as pd

from .security import (
    CHANGE_APPROVAL_LEVELS,
    MAX_APPROVAL_LEVEL,
    MIN_APPROVAL_LEVEL,
    MIN_CHANGE_APPROVAL_LEVEL,
    ROLE_ADMIN,
    ROLE_APPROVER,
    ROLE_STEWARD,
    ROLE_SYSTEM_ADMIN,
    ROLE_VIEWER,
)
# pylint: disable=too-many-locals,too-many-branches,too-many-statements
# pylint: disable=too-many-arguments,too-many-positional-arguments


class RepositoryAdminMixin:
    """Role, scope, and admin audit data access methods."""
    SECURITY_POLICY_VERSION_SETTING_KEY = "security_policy_version"
    SECURITY_POLICY_VERSION_ACTOR = "system:security-policy"
    GROUP_PRINCIPAL_PREFIX = "group:"
    GROUP_PRINCIPAL_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:@/-]{1,190}$")

    @classmethod
    def normalize_group_principal(cls, raw_group_principal: str) -> str:
        text = str(raw_group_principal or "").strip().lower()
        if not text:
            return ""
        if text.startswith(cls.GROUP_PRINCIPAL_PREFIX):
            text = text[len(cls.GROUP_PRINCIPAL_PREFIX) :]
        text = re.sub(r"\s+", "_", text)
        text = re.sub(r"[^a-z0-9._:@/-]", "_", text)
        text = re.sub(r"_+", "_", text).strip("._:/-")
        if not text or not cls.GROUP_PRINCIPAL_PATTERN.match(text):
            return ""
        return f"{cls.GROUP_PRINCIPAL_PREFIX}{text}"

    def get_security_policy_version(self) -> int:
        """Return the current security policy version used for session invalidation."""
        cache_key = ("security_policy_version",)

        def _load() -> int:
            payload = self.get_user_setting(
                self.SECURITY_POLICY_VERSION_ACTOR,
                self.SECURITY_POLICY_VERSION_SETTING_KEY,
            )
            try:
                version = int(payload.get("version", 1)) if isinstance(payload, dict) else 1
            except Exception:
                version = 1
            return max(1, version)

        return int(self._cached(cache_key, _load, ttl_seconds=30))

    def bump_security_policy_version(self, *, updated_by: str | None = None) -> int:
        """Bump security policy version so session-cached policies can refresh quickly."""
        next_version = max(1, self.get_security_policy_version() + 1)
        actor = str(updated_by or self.SECURITY_POLICY_VERSION_ACTOR).strip() or self.SECURITY_POLICY_VERSION_ACTOR
        self.save_user_setting(
            user_principal=self.SECURITY_POLICY_VERSION_ACTOR,
            setting_key=self.SECURITY_POLICY_VERSION_SETTING_KEY,
            setting_value={"version": next_version, "updated_by": actor, "updated_at": self._now().isoformat()},
        )
        self._cache_clear()
        return next_version

    def list_role_definitions(self) -> pd.DataFrame:
        """Return role definitions merged with built-in defaults."""
        cache_key = ("role_definitions",)

        def _load() -> pd.DataFrame:
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

        return self._cached(cache_key, _load, ttl_seconds=300)

    def list_role_permissions(self) -> pd.DataFrame:
        """Return active role permissions, with defaults when table is empty."""
        cache_key = ("role_permissions",)

        def _load() -> pd.DataFrame:
            columns = ["role_code", "object_name", "action_code", "active_flag", "updated_at"]
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

        return self._cached(cache_key, _load, ttl_seconds=300)

    def list_known_roles(self) -> list[str]:
        """Return the set of roles visible to the app."""
        cache_key = ("known_roles",)

        def _load() -> list[str]:
            roles = set(self._default_role_definition_rows().keys())
            role_defs = self.list_role_definitions()
            if not role_defs.empty and "role_code" in role_defs.columns:
                roles.update(role_defs["role_code"].dropna().astype(str).tolist())

            grants = self._query_file(
                "reporting/list_role_grants.sql",
                columns=["role_code"],
                sec_user_role_map=self._table("sec_user_role_map"),
                app_user_directory=self._table("app_user_directory"),
            )
            if not grants.empty and "role_code" in grants.columns:
                roles.update(grants["role_code"].dropna().astype(str).tolist())
            group_grants = self._query_file(
                "reporting/list_group_role_grants.sql",
                columns=["role_code"],
                sec_group_role_map=self._table("sec_group_role_map"),
                app_user_directory=self._table("app_user_directory"),
            )
            if not group_grants.empty and "role_code" in group_grants.columns:
                roles.update(group_grants["role_code"].dropna().astype(str).tolist())
            return sorted(role for role in roles if role)

        return self._cached(cache_key, _load, ttl_seconds=300)

    def resolve_role_policy(self, user_roles: set[str]) -> dict[str, Any]:
        """Resolve effective capabilities for the supplied role set."""
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
        can_direct_apply = any(
            self._as_bool(item.get("can_direct_apply"))
            for item in selected_defs
        )
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
            approval_level = max(approval_level, MAX_APPROVAL_LEVEL)
            allowed_actions = set(CHANGE_APPROVAL_LEVELS.keys())

        if ROLE_SYSTEM_ADMIN in active_roles and ROLE_ADMIN not in active_roles:
            can_edit = False
            can_direct_apply = False
            can_submit_requests = False
            can_approve_requests = False
            approval_level = 0

        if not allowed_actions:
            allowed_actions = {
                action
                for action, required in CHANGE_APPROVAL_LEVELS.items()
                if int(required) <= int(max(MIN_CHANGE_APPROVAL_LEVEL, approval_level))
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
        """Insert or update a role definition."""
        role_key = str(role_code or "").strip().lower()
        if not role_key:
            raise ValueError("Role code is required.")
        now = self._now()
        existing = self._query_file(
            "ingestion/select_role_definition_by_code.sql",
            params=(role_key,),
            columns=["role_code"],
            sec_role_definition=self._table("sec_role_definition"),
        )
        payload = (
            str(role_name or role_key).strip() or role_key,
            str(description or "").strip() or None,
            max(MIN_APPROVAL_LEVEL, min(int(approval_level or 0), MAX_APPROVAL_LEVEL)),
            bool(can_edit),
            bool(can_report),
            bool(can_direct_apply),
            True,
            now,
            updated_by,
        )
        if existing.empty:
            self._execute_file(
                "inserts/create_role_definition.sql",
                params=(role_key, *payload),
                sec_role_definition=self._table("sec_role_definition"),
            )
            self.bump_security_policy_version(updated_by=updated_by)
            return
        self._execute_file(
            "updates/update_role_definition.sql",
            params=(*payload, role_key),
            sec_role_definition=self._table("sec_role_definition"),
        )
        self.bump_security_policy_version(updated_by=updated_by)

    def replace_role_permissions(
        self,
        *,
        role_code: str,
        action_codes: set[str],
        updated_by: str,
    ) -> None:
        """Replace all permissions granted to a role."""
        role_key = str(role_code or "").strip().lower()
        if not role_key:
            raise ValueError("Role code is required.")
        _ = updated_by
        normalized_actions = {
            str(action).strip().lower()
            for action in (action_codes or set())
            if str(action).strip().lower() in CHANGE_APPROVAL_LEVELS
        }
        self._execute_file(
            "updates/deactivate_role_permissions_by_role.sql",
            params=(self._now(), role_key),
            sec_role_permission=self._table("sec_role_permission"),
        )
        now = self._now()
        for action_code in sorted(normalized_actions):
            self._execute_file(
                "inserts/create_role_permission.sql",
                params=(role_key, "change_action", action_code, True, now),
                sec_role_permission=self._table("sec_role_permission"),
            )
        self.bump_security_policy_version(updated_by=updated_by)

    def list_role_grants(self) -> pd.DataFrame:
        """List role grants assigned to users."""
        columns = [
            "user_principal",
            "role_code",
            "active_flag",
            "granted_by",
            "granted_at",
            "revoked_at",
        ]
        return self._query_file(
            "reporting/list_role_grants.sql",
            columns=columns,
            sec_user_role_map=self._table("sec_user_role_map"),
            app_user_directory=self._table("app_user_directory"),
        )

    def list_scope_grants(self) -> pd.DataFrame:
        """List org scope grants assigned to users."""
        return self._query_file(
            "reporting/list_scope_grants.sql",
            columns=["user_principal", "org_id", "scope_level", "active_flag", "granted_at"],
            sec_user_org_scope=self._table("sec_user_org_scope"),
            app_user_directory=self._table("app_user_directory"),
        )

    def list_group_role_grants(self) -> pd.DataFrame:
        """List role grants assigned to groups."""
        columns = [
            "group_principal",
            "role_code",
            "active_flag",
            "granted_by",
            "granted_at",
            "revoked_at",
        ]
        return self._query_file(
            "reporting/list_group_role_grants.sql",
            columns=columns,
            sec_group_role_map=self._table("sec_group_role_map"),
            app_user_directory=self._table("app_user_directory"),
        )

    def _insert_role_grant(
        self,
        *,
        target_user_ref: str,
        role_code: str,
        granted_by_ref: str,
        granted_at,
    ) -> None:
        role_key = str(role_code or "").strip().lower()
        if not role_key:
            raise ValueError("Role code is required.")
        self._execute_file(
            "inserts/grant_role.sql",
            params=(target_user_ref, role_key, True, granted_by_ref, granted_at, None),
            sec_user_role_map=self._table("sec_user_role_map"),
        )

    def _insert_group_role_grant(
        self,
        *,
        group_principal: str,
        role_code: str,
        granted_by_ref: str,
        granted_at,
    ) -> None:
        group_key = self.normalize_group_principal(group_principal)
        role_key = str(role_code or "").strip().lower()
        if not group_key:
            raise ValueError("Group principal is required.")
        if not role_key:
            raise ValueError("Role code is required.")
        self._execute_file(
            "inserts/grant_group_role.sql",
            params=(group_key, role_key, True, granted_by_ref, granted_at, None),
            sec_group_role_map=self._table("sec_group_role_map"),
        )

    def grant_role(self, target_user_principal: str, role_code: str, granted_by: str) -> None:
        """Grant a role to a user and write an access audit event."""
        target_ref = self.resolve_user_id(target_user_principal, allow_create=True)
        granted_by_ref = self.resolve_user_id(granted_by, allow_create=True)
        if not target_ref or not granted_by_ref:
            raise ValueError("Target user and grant actor must resolve to directory users.")
        role_key = str(role_code or "").strip().lower()
        now = self._now()
        self._insert_role_grant(
            target_user_ref=target_ref,
            role_code=role_key,
            granted_by_ref=granted_by_ref,
            granted_at=now,
        )
        self.bump_security_policy_version(updated_by=granted_by)
        self._audit_access(
            actor_user_principal=granted_by_ref,
            action_type="grant_role",
            target_user_principal=target_ref,
            target_role=role_key,
            notes="Role granted through admin UI.",
        )

    def change_role_grant(
        self,
        *,
        target_user_principal: str,
        current_role_code: str,
        new_role_code: str,
        granted_by: str,
    ) -> None:
        target_ref = self.resolve_user_id(target_user_principal, allow_create=True)
        granted_by_ref = self.resolve_user_id(granted_by, allow_create=True)
        if not target_ref or not granted_by_ref:
            raise ValueError("Target user and grant actor must resolve to directory users.")
        current_role = str(current_role_code or "").strip().lower()
        new_role = str(new_role_code or "").strip().lower()
        if not current_role or not new_role:
            raise ValueError("Current role and new role are required.")
        if current_role == new_role:
            return

        now = self._now()
        self._execute_file(
            "updates/revoke_role_grant.sql",
            params=(False, now, target_ref, current_role),
            sec_user_role_map=self._table("sec_user_role_map"),
        )
        self._insert_role_grant(
            target_user_ref=target_ref,
            role_code=new_role,
            granted_by_ref=granted_by_ref,
            granted_at=now,
        )
        self.bump_security_policy_version(updated_by=granted_by)
        self._audit_access(
            actor_user_principal=granted_by_ref,
            action_type="change_role",
            target_user_principal=target_ref,
            target_role=new_role,
            notes=f"Role changed from {current_role} to {new_role} through admin UI.",
        )

    def grant_group_role(self, group_principal: str, role_code: str, granted_by: str) -> None:
        group_key = self.normalize_group_principal(group_principal)
        role_key = str(role_code or "").strip().lower()
        granted_by_ref = self.resolve_user_id(granted_by, allow_create=True)
        if not group_key:
            raise ValueError("Group principal is required.")
        if not role_key:
            raise ValueError("Role code is required.")
        if not granted_by_ref:
            raise ValueError("Grant actor must resolve to a directory user.")

        now = self._now()
        self._insert_group_role_grant(
            group_principal=group_key,
            role_code=role_key,
            granted_by_ref=granted_by_ref,
            granted_at=now,
        )
        self.bump_security_policy_version(updated_by=granted_by)
        self._audit_access(
            actor_user_principal=granted_by_ref,
            action_type="grant_group_role",
            target_user_principal=None,
            target_role=role_key,
            notes=f"Role granted to group {group_key} through admin UI.",
        )

    def change_group_role_grant(
        self,
        *,
        group_principal: str,
        current_role_code: str,
        new_role_code: str,
        granted_by: str,
    ) -> None:
        group_key = self.normalize_group_principal(group_principal)
        current_role = str(current_role_code or "").strip().lower()
        new_role = str(new_role_code or "").strip().lower()
        granted_by_ref = self.resolve_user_id(granted_by, allow_create=True)
        if not group_key:
            raise ValueError("Group principal is required.")
        if not current_role or not new_role:
            raise ValueError("Current role and new role are required.")
        if not granted_by_ref:
            raise ValueError("Grant actor must resolve to a directory user.")
        if current_role == new_role:
            return

        now = self._now()
        self._execute_file(
            "updates/revoke_group_role_grant.sql",
            params=(False, now, group_key, current_role),
            sec_group_role_map=self._table("sec_group_role_map"),
        )
        self._insert_group_role_grant(
            group_principal=group_key,
            role_code=new_role,
            granted_by_ref=granted_by_ref,
            granted_at=now,
        )
        self.bump_security_policy_version(updated_by=granted_by)
        self._audit_access(
            actor_user_principal=granted_by_ref,
            action_type="change_group_role",
            target_user_principal=None,
            target_role=new_role,
            notes=f"Role changed for group {group_key}: {current_role} -> {new_role} through admin UI.",
        )

    def revoke_group_role_grant(
        self,
        *,
        group_principal: str,
        role_code: str,
        revoked_by: str,
    ) -> None:
        group_key = self.normalize_group_principal(group_principal)
        role_key = str(role_code or "").strip().lower()
        revoked_by_ref = self.resolve_user_id(revoked_by, allow_create=True)
        if not group_key:
            raise ValueError("Group principal is required.")
        if not role_key:
            raise ValueError("Role code is required.")
        if not revoked_by_ref:
            raise ValueError("Grant actor must resolve to a directory user.")

        now = self._now()
        self._execute_file(
            "updates/revoke_group_role_grant.sql",
            params=(False, now, group_key, role_key),
            sec_group_role_map=self._table("sec_group_role_map"),
        )
        self.bump_security_policy_version(updated_by=revoked_by)
        self._audit_access(
            actor_user_principal=revoked_by_ref,
            action_type="revoke_group_role",
            target_user_principal=None,
            target_role=role_key,
            notes=f"Role {role_key} revoked for group {group_key} through admin UI.",
        )

    def grant_org_scope(
        self, target_user_principal: str, org_id: str, scope_level: str, granted_by: str
    ) -> None:
        """Grant org scope to a user and write an access audit event."""
        target_ref = self.resolve_user_id(target_user_principal, allow_create=True)
        granted_by_ref = self.resolve_user_id(granted_by, allow_create=True)
        if not target_ref or not granted_by_ref:
            raise ValueError("Target user and grant actor must resolve to directory users.")
        now = self._now()
        self._execute_file(
            "inserts/grant_org_scope.sql",
            params=(target_ref, org_id, scope_level, True, now),
            sec_user_org_scope=self._table("sec_user_org_scope"),
        )
        self.bump_security_policy_version(updated_by=granted_by)
        self._audit_access(
            actor_user_principal=granted_by_ref,
            action_type="grant_scope",
            target_user_principal=target_ref,
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
        """Write admin/security access audit records."""
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
