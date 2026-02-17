"""Admin and RBAC repository helpers."""

from __future__ import annotations

import uuid
from typing import Any

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
        """List LOB scope grants assigned to users."""
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

    def list_owner_reassignment_assignments(self, source_user_principal: str) -> list[dict[str, Any]]:
        source_candidate = str(source_user_principal or "").strip()
        if not source_candidate:
            raise ValueError("Source owner is required.")

        source_login = self.resolve_user_login_identifier(source_candidate)
        source_ref = self.resolve_user_id(source_candidate, allow_create=False)

        rows = self._query_file(
            "reporting/list_owner_reassignment_assignments.sql",
            columns=[
                "assignment_type",
                "assignment_id",
                "entity_type",
                "entity_id",
                "entity_name",
                "vendor_id",
                "vendor_display_name",
                "owner_role",
                "owner_user_principal",
                "owner_principal",
            ],
            core_vendor_business_owner=self._table("core_vendor_business_owner"),
            core_vendor=self._table("core_vendor"),
            core_offering_business_owner=self._table("core_offering_business_owner"),
            core_vendor_offering=self._table("core_vendor_offering"),
            app_project=self._table("app_project"),
            app_user_directory=self._table("app_user_directory"),
        )
        if rows.empty:
            return []

        source_login_lower = str(source_login or "").strip().lower()
        source_ref_lower = str(source_ref or "").strip().lower()
        source_candidate_lower = source_candidate.lower()
        owner_login = rows.get("owner_principal", "").fillna("").astype(str).str.strip().str.lower()
        owner_raw = rows.get("owner_user_principal", "").fillna("").astype(str).str.strip().str.lower()
        source_mask = pd.Series(False, index=rows.index)
        if source_candidate_lower:
            source_mask = source_mask | (owner_login == source_candidate_lower) | (owner_raw == source_candidate_lower)
        if source_login_lower:
            source_mask = source_mask | (owner_login == source_login_lower) | (owner_raw == source_login_lower)
        if source_ref_lower:
            source_mask = source_mask | (owner_raw == source_ref_lower)
        rows = rows[source_mask].copy()
        if rows.empty:
            return []

        rows["assignment_key"] = rows.apply(
            lambda row: f"{str(row.get('assignment_type') or '').strip()}::{str(row.get('assignment_id') or '').strip()}",
            axis=1,
        )
        rows = rows.sort_values(["entity_type", "vendor_display_name", "entity_name", "owner_role"])
        return rows.to_dict("records")

    def bulk_reassign_owner_assignments(
        self,
        *,
        source_user_principal: str,
        assignments: list[dict[str, str]],
        actor_user_principal: str,
    ) -> dict[str, int]:
        source_candidate = str(source_user_principal or "").strip()
        if not source_candidate:
            raise ValueError("Source owner is required.")
        if not assignments:
            raise ValueError("At least one assignment must be selected.")

        current_rows = self.list_owner_reassignment_assignments(source_candidate)
        by_key = {
            f"{str(row.get('assignment_type') or '').strip()}::{str(row.get('assignment_id') or '').strip()}": row
            for row in current_rows
        }
        if not by_key:
            return {"updated_count": 0, "skipped_count": len(assignments)}

        source_ref = self.resolve_user_id(source_candidate, allow_create=False)
        source_login = self.resolve_user_login_identifier(source_candidate)
        source_values = {source_candidate.lower()}
        if source_ref:
            source_values.add(str(source_ref).strip().lower())
        if source_login:
            source_values.add(str(source_login).strip().lower())

        actor_ref = self._actor_ref(actor_user_principal)
        now = self._now()
        updated_count = 0
        skipped_count = 0

        for item in assignments:
            assignment_type = str(item.get("assignment_type") or "").strip().lower()
            assignment_id = str(item.get("assignment_id") or "").strip()
            target_candidate = str(item.get("target_owner") or "").strip()
            if not assignment_type or not assignment_id or not target_candidate:
                skipped_count += 1
                continue

            key = f"{assignment_type}::{assignment_id}"
            before_json = by_key.get(key)
            if not before_json:
                skipped_count += 1
                continue

            target_ref = self.resolve_user_id(target_candidate, allow_create=False)
            if not target_ref:
                raise ValueError(f"Replacement owner '{target_candidate}' must exist in the employee directory.")

            target_status = self.get_employee_directory_status_map([target_candidate])
            status_row = target_status.get(str(target_candidate).strip().lower())
            if not status_row:
                target_login = self.resolve_user_login_identifier(target_candidate)
                if target_login:
                    status_row = self.get_employee_directory_status_map([target_login]).get(target_login.lower())
            if not status_row or not bool(status_row.get("active")):
                raise ValueError(f"Replacement owner '{target_candidate}' must be active in the employee directory.")

            target_login = self.resolve_user_login_identifier(target_candidate) or target_candidate
            target_values = {
                str(target_candidate).strip().lower(),
                str(target_ref).strip().lower(),
                str(target_login).strip().lower(),
            }
            if source_values & target_values:
                skipped_count += 1
                continue

            if assignment_type == "vendor_owner":
                self._execute_file(
                    "updates/reassign_vendor_owner_assignment.sql",
                    params=(target_ref, now, actor_ref, assignment_id),
                    core_vendor_business_owner=self._table("core_vendor_business_owner"),
                )
                entity_name = "core_vendor_business_owner"
            elif assignment_type == "offering_owner":
                self._execute_file(
                    "updates/reassign_offering_owner_assignment.sql",
                    params=(target_ref, now, actor_ref, assignment_id),
                    core_offering_business_owner=self._table("core_offering_business_owner"),
                )
                entity_name = "core_offering_business_owner"
            elif assignment_type == "project_owner":
                self._execute_file(
                    "updates/reassign_project_owner_assignment.sql",
                    params=(target_ref, now, actor_ref, assignment_id),
                    app_project=self._table("app_project"),
                )
                entity_name = "app_project"
            else:
                skipped_count += 1
                continue

            after_json = dict(before_json)
            after_json["owner_user_principal"] = target_ref
            after_json["owner_principal"] = target_login
            self._write_audit_entity_change(
                entity_name=entity_name,
                entity_id=assignment_id,
                action_type="update",
                actor_user_principal=actor_user_principal,
                before_json=before_json,
                after_json=after_json,
                request_id=None,
            )
            updated_count += 1

        return {"updated_count": updated_count, "skipped_count": skipped_count}

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

    def _revoke_all_user_role_grants(
        self,
        *,
        target_user_ref: str,
        revoked_at,
    ) -> None:
        self._execute_file(
            "updates/revoke_all_user_role_grants.sql",
            params=(False, revoked_at, target_user_ref),
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
        # Enforce one active direct role per user.
        self._revoke_all_user_role_grants(target_user_ref=target_ref, revoked_at=now)
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
        # Enforce one active direct role per user.
        self._revoke_all_user_role_grants(target_user_ref=target_ref, revoked_at=now)
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
        """Grant LOB scope to a user and write an access audit event."""
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
            notes=f"LOB scope granted: {org_id} ({scope_level}).",
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
            raise ValueError("Line of business and scope level are required.")

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
            notes=f"LOB scope revoked: {org_key} ({scope_key}).",
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
