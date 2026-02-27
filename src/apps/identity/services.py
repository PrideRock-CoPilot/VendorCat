from __future__ import annotations

# pyright: reportAttributeAccessIssue=false

from typing import Any

from apps.core.contracts.identity import IdentityContext
from apps.core.contracts.policy import PolicySnapshot
from apps.identity.models import AccessRequest, GroupRoleAssignment, RoleAssignment, ScopeGrant, TermsAcceptance, UserDirectory


def normalize_group_principal(raw_group: str) -> str:
    cleaned = str(raw_group or "").strip().lower()
    if not cleaned:
        return ""
    if cleaned.startswith("group:"):
        return cleaned
    return f"group:{cleaned}"


def build_policy_snapshot(identity: IdentityContext) -> PolicySnapshot:
    roles = list(identity.groups)
    roles.append("anonymous" if identity.is_anonymous else "authenticated")

    persisted_roles = tuple(
        RoleAssignment.objects.filter(user_principal=identity.user_principal)
        .values_list("role", flat=True)
        .order_by("role")
    )
    roles.extend(persisted_roles)

    group_principals = [normalize_group_principal(group) for group in identity.groups]
    group_principals = [group for group in group_principals if group]
    if group_principals:
        group_roles = tuple(
            GroupRoleAssignment.objects.filter(group_principal__in=group_principals)
            .values_list("role", flat=True)
            .order_by("role")
        )
        roles.extend(group_roles)

    scopes = tuple(
        ScopeGrant.objects.filter(user_principal=identity.user_principal)
        .values_list("org_id", "scope_level")
        .order_by("org_id", "scope_level")
    )
    serialized_scopes = tuple(f"{org_id}:{scope_level}" for org_id, scope_level in scopes)

    deduped_roles = tuple(dict.fromkeys(roles))
    return PolicySnapshot(user_principal=identity.user_principal, roles=deduped_roles, scopes=serialized_scopes)


def sync_user_directory(identity: IdentityContext) -> dict[str, Any]:
    record, _ = UserDirectory.objects.update_or_create(
        user_principal=identity.user_principal,
        defaults={
            "display_name": identity.display_name,
            "email": identity.email,
            "active_flag": True,
        },
    )
    return {
        "user_id": str(record.id),
        "user_principal": record.user_principal,
        "display_name": record.display_name,
        "email": record.email,
        "active_flag": record.active_flag,
    }


def create_access_request(identity: IdentityContext, requested_role: str, justification: str) -> dict[str, Any]:
    if not requested_role:
        raise ValueError("requested_role is required")

    record = AccessRequest.objects.create(
        requested_by_principal=identity.user_principal,
        requested_role=requested_role,
        justification=justification,
        status="pending",
    )
    return {
        "access_request_id": str(record.id),
        "requested_by_principal": record.requested_by_principal,
        "requested_role": record.requested_role,
        "status": record.status,
    }


def list_access_requests(*, pending_only: bool) -> list[dict[str, Any]]:
    queryset = AccessRequest.objects.all().order_by("-id")
    if pending_only:
        queryset = queryset.filter(status="pending")

    return [
        {
            "access_request_id": str(record.id),
            "requested_by_principal": record.requested_by_principal,
            "requested_role": record.requested_role,
            "justification": record.justification,
            "status": record.status,
            "reviewed_by_principal": record.reviewed_by_principal,
        }
        for record in queryset
    ]


def review_access_request(identity: IdentityContext, request_id: int, decision: str, note: str) -> dict[str, Any]:
    action = decision.strip().lower()
    if action not in {"approved", "rejected"}:
        raise ValueError("decision must be approved or rejected")

    try:
        record = AccessRequest.objects.get(id=request_id)
    except AccessRequest.DoesNotExist as exc:
        raise LookupError(f"access request {request_id} not found") from exc

    if record.status != "pending":
        raise ValueError("only pending access requests can be reviewed")

    record.status = action
    record.reviewed_by_principal = identity.user_principal
    if note.strip():
        record.justification = f"{record.justification}\n\nreview_note: {note.strip()}".strip()
    record.save(update_fields=["status", "reviewed_by_principal", "justification", "updated_at"])

    assignment_id = ""
    if action == "approved":
        assignment, _ = RoleAssignment.objects.get_or_create(
            user_principal=record.requested_by_principal,
            role=record.requested_role,
            defaults={"granted_by_principal": identity.user_principal},
        )
        assignment_id = str(assignment.id)

    return {
        "access_request_id": str(record.id),
        "status": record.status,
        "reviewed_by_principal": record.reviewed_by_principal,
        "assignment_id": assignment_id,
    }


def accept_terms(identity: IdentityContext, terms_version: str, ip_address: str) -> dict[str, Any]:
    if not terms_version:
        raise ValueError("terms_version is required")

    record, created = TermsAcceptance.objects.get_or_create(
        user_principal=identity.user_principal,
        terms_version=terms_version,
        defaults={"ip_address": ip_address},
    )
    return {
        "terms_acceptance_id": str(record.id),
        "user_principal": record.user_principal,
        "terms_version": record.terms_version,
        "created": created,
    }


def bootstrap_first_admin(identity: IdentityContext) -> dict[str, Any]:
    existing_admin_exists = RoleAssignment.objects.filter(role="vendor_admin").exists()
    if existing_admin_exists:
        raise PermissionError("first-admin bootstrap is closed once an admin exists")

    assignment, _ = RoleAssignment.objects.get_or_create(
        user_principal=identity.user_principal,
        role="vendor_admin",
        defaults={"granted_by_principal": identity.user_principal},
    )
    return {
        "assignment_id": str(assignment.id),
        "user_principal": assignment.user_principal,
        "role": assignment.role,
    }


def grant_user_role(identity: IdentityContext, target_user: str, role: str) -> dict[str, Any]:
    user_principal = str(target_user or "").strip().lower()
    role_code = str(role or "").strip()
    if not user_principal:
        raise ValueError("target_user is required")
    if not role_code:
        raise ValueError("role is required")

    assignment, created = RoleAssignment.objects.get_or_create(
        user_principal=user_principal,
        role=role_code,
        defaults={"granted_by_principal": identity.user_principal},
    )
    if not created and not assignment.granted_by_principal:
        assignment.granted_by_principal = identity.user_principal
        assignment.save(update_fields=["granted_by_principal"])

    return {
        "assignment_id": str(assignment.id),
        "user_principal": assignment.user_principal,
        "role": assignment.role,
        "created": created,
    }


def revoke_user_role(target_user: str, role: str) -> dict[str, Any]:
    user_principal = str(target_user or "").strip().lower()
    role_code = str(role or "").strip()
    if not user_principal:
        raise ValueError("target_user is required")
    if not role_code:
        raise ValueError("role is required")

    deleted_count, _ = RoleAssignment.objects.filter(user_principal=user_principal, role=role_code).delete()
    return {
        "user_principal": user_principal,
        "role": role_code,
        "deleted": deleted_count > 0,
    }


def grant_group_role(identity: IdentityContext, target_group: str, role: str) -> dict[str, Any]:
    group_principal = normalize_group_principal(target_group)
    role_code = str(role or "").strip()
    if not group_principal:
        raise ValueError("target_group is required")
    if not role_code:
        raise ValueError("role is required")

    assignment, created = GroupRoleAssignment.objects.get_or_create(
        group_principal=group_principal,
        role=role_code,
        defaults={"granted_by_principal": identity.user_principal},
    )
    if not created and not assignment.granted_by_principal:
        assignment.granted_by_principal = identity.user_principal
        assignment.save(update_fields=["granted_by_principal"])

    return {
        "group_role_assignment_id": str(assignment.id),
        "group_principal": assignment.group_principal,
        "role": assignment.role,
        "created": created,
    }


def revoke_group_role(target_group: str, role: str) -> dict[str, Any]:
    group_principal = normalize_group_principal(target_group)
    role_code = str(role or "").strip()
    if not group_principal:
        raise ValueError("target_group is required")
    if not role_code:
        raise ValueError("role is required")

    deleted_count, _ = GroupRoleAssignment.objects.filter(group_principal=group_principal, role=role_code).delete()
    return {
        "group_principal": group_principal,
        "role": role_code,
        "deleted": deleted_count > 0,
    }


def grant_scope(identity: IdentityContext, target_user: str, org_id: str, scope_level: str) -> dict[str, Any]:
    user_principal = str(target_user or "").strip().lower()
    org = str(org_id or "").strip()
    scope = str(scope_level or "").strip().lower()
    if not user_principal:
        raise ValueError("target_user is required")
    if not org:
        raise ValueError("org_id is required")
    if not scope:
        raise ValueError("scope_level is required")

    grant, created = ScopeGrant.objects.get_or_create(
        user_principal=user_principal,
        org_id=org,
        scope_level=scope,
        defaults={"granted_by_principal": identity.user_principal},
    )
    if not created and not grant.granted_by_principal:
        grant.granted_by_principal = identity.user_principal
        grant.save(update_fields=["granted_by_principal"])

    return {
        "scope_grant_id": str(grant.id),
        "user_principal": grant.user_principal,
        "org_id": grant.org_id,
        "scope_level": grant.scope_level,
        "created": created,
    }


def revoke_scope(target_user: str, org_id: str, scope_level: str) -> dict[str, Any]:
    user_principal = str(target_user or "").strip().lower()
    org = str(org_id or "").strip()
    scope = str(scope_level or "").strip().lower()
    if not user_principal:
        raise ValueError("target_user is required")
    if not org:
        raise ValueError("org_id is required")
    if not scope:
        raise ValueError("scope_level is required")

    deleted_count, _ = ScopeGrant.objects.filter(user_principal=user_principal, org_id=org, scope_level=scope).delete()
    return {
        "user_principal": user_principal,
        "org_id": org,
        "scope_level": scope,
        "deleted": deleted_count > 0,
    }


def list_role_assignments() -> list[dict[str, Any]]:
    return [
        {
            "assignment_id": str(row.id),
            "user_principal": row.user_principal,
            "role": row.role,
            "granted_by_principal": row.granted_by_principal,
        }
        for row in RoleAssignment.objects.all().order_by("user_principal", "role")
    ]


def list_group_role_assignments() -> list[dict[str, Any]]:
    return [
        {
            "group_role_assignment_id": str(row.id),
            "group_principal": row.group_principal,
            "role": row.role,
            "granted_by_principal": row.granted_by_principal,
        }
        for row in GroupRoleAssignment.objects.all().order_by("group_principal", "role")
    ]


def list_scope_grants(*, user_principal: str | None = None) -> list[dict[str, Any]]:
    queryset = ScopeGrant.objects.all().order_by("user_principal", "org_id", "scope_level")
    if user_principal:
        queryset = queryset.filter(user_principal=str(user_principal).strip().lower())

    return [
        {
            "scope_grant_id": str(row.id),
            "user_principal": row.user_principal,
            "org_id": row.org_id,
            "scope_level": row.scope_level,
            "granted_by_principal": row.granted_by_principal,
        }
        for row in queryset
    ]


def list_pending_approvals(*, requested_role: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    queryset = AccessRequest.objects.filter(status="pending").order_by("created_at", "id")
    if requested_role:
        queryset = queryset.filter(requested_role=str(requested_role).strip())

    return [
        {
            "access_request_id": str(record.id),
            "requested_by_principal": record.requested_by_principal,
            "requested_role": record.requested_role,
            "justification": record.justification,
            "status": record.status,
        }
        for record in queryset[: max(1, min(limit, 200))]
    ]


def open_next_pending_approval(*, requested_role: str | None = None) -> dict[str, Any] | None:
    queryset = AccessRequest.objects.filter(status="pending").order_by("created_at", "id")
    if requested_role:
        queryset = queryset.filter(requested_role=str(requested_role).strip())

    record = queryset.first()
    if not record:
        return None

    return {
        "access_request_id": str(record.id),
        "requested_by_principal": record.requested_by_principal,
        "requested_role": record.requested_role,
        "justification": record.justification,
        "status": record.status,
    }
