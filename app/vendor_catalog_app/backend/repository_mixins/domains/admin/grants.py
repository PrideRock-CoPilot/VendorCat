"""Admin and RBAC repository helpers."""

from __future__ import annotations

import uuid

import pandas as pd

# pylint: disable=too-many-locals,too-many-branches,too-many-statements
# pylint: disable=too-many-arguments,too-many-positional-arguments



class RepositoryAdminGrantMixin:
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

    def revoke_role_grant(
        self,
        *,
        target_user_principal: str,
        role_code: str,
        revoked_by: str,
    ) -> None:
        target_ref = self.resolve_user_id(target_user_principal, allow_create=True)
        revoked_by_ref = self.resolve_user_id(revoked_by, allow_create=True)
        role_key = str(role_code or "").strip().lower()
        if not target_ref or not revoked_by_ref:
            raise ValueError("Target user and revoke actor must resolve to directory users.")
        if not role_key:
            raise ValueError("Role code is required.")

        now = self._now()
        self._execute_file(
            "updates/revoke_role_grant.sql",
            params=(False, now, target_ref, role_key),
            sec_user_role_map=self._table("sec_user_role_map"),
        )
        self.bump_security_policy_version(updated_by=revoked_by)
        self._audit_access(
            actor_user_principal=revoked_by_ref,
            action_type="revoke_role",
            target_user_principal=target_ref,
            target_role=role_key,
            notes=f"Role {role_key} revoked through admin UI.",
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

    def revoke_org_scope(
        self,
        *,
        target_user_principal: str,
        org_id: str,
        scope_level: str,
        revoked_by: str,
    ) -> None:
        target_ref = self.resolve_user_id(target_user_principal, allow_create=True)
        revoked_by_ref = self.resolve_user_id(revoked_by, allow_create=True)
        org_key = str(org_id or "").strip()
        scope_key = str(scope_level or "").strip().lower()
        if not target_ref or not revoked_by_ref:
            raise ValueError("Target user and revoke actor must resolve to directory users.")
        if not org_key or not scope_key:
            raise ValueError("Org and scope level are required.")

        self._execute_file(
            "updates/revoke_org_scope_grant.sql",
            params=(False, target_ref, org_key, scope_key),
            sec_user_org_scope=self._table("sec_user_org_scope"),
        )
        self.bump_security_policy_version(updated_by=revoked_by)
        self._audit_access(
            actor_user_principal=revoked_by_ref,
            action_type="revoke_scope",
            target_user_principal=target_ref,
            target_role=None,
            notes=f"Org scope revoked: {org_key} ({scope_key}).",
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

