from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.core.security import (
    MAX_APPROVAL_LEVEL,
    MIN_APPROVAL_LEVEL,
    ROLE_CHOICES,
    change_action_choices,
)
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.admin.common import (
    ADMIN_SECTION_ACCESS,
    ROLE_CODE_PATTERN,
    _admin_redirect_url,
)
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/admin")


def _access_tab_redirect(tab_value: str | None = None) -> str:
    tab = str(tab_value or "").strip().lower()
    base = _admin_redirect_url(section=ADMIN_SECTION_ACCESS)
    if tab in {"users", "groups", "business_unit", "roles"}:
        return f"{base}?tab={tab}"
    return base


@router.post("/grant-role")
@require_permission("admin_role_manage")
async def grant_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    target_user = str(form.get("target_user", "")).strip()
    role_code = str(form.get("role_code", "")).strip().lower()
    if not target_user or not role_code:
        add_flash(request, "User and role are required.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    target_user = repo.resolve_user_login_identifier(target_user) or target_user
    if role_code not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, f"Role `{role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    try:
        repo.grant_role(target_user_principal=target_user, role_code=role_code, granted_by=user.user_principal)
    except Exception as exc:
        add_flash(request, f"Could not grant role: {exc}", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="grant_role",
        payload={"target_user": target_user, "role_code": role_code},
    )
    add_flash(request, "Role grant recorded.", "success")
    return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)


@router.post("/change-role")
@require_permission("admin_role_manage")
async def change_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    target_user = str(form.get("target_user", "")).strip()
    current_role_code = str(form.get("current_role_code", "")).strip().lower()
    new_role_code = str(form.get("new_role_code", "")).strip().lower()
    if not target_user or not current_role_code or not new_role_code:
        add_flash(request, "User, current role, and new role are required.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    target_user = repo.resolve_user_login_identifier(target_user) or target_user
    if new_role_code not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, f"Role `{new_role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if current_role_code == new_role_code:
        add_flash(request, "Role is already set to that value.", "success")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    try:
        repo.change_role_grant(
            target_user_principal=target_user,
            current_role_code=current_role_code,
            new_role_code=new_role_code,
            granted_by=user.user_principal,
        )
    except Exception as exc:
        add_flash(request, f"Could not change role: {exc}", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="change_role",
        payload={
            "target_user": target_user,
            "current_role_code": current_role_code,
            "new_role_code": new_role_code,
        },
    )
    add_flash(request, "Role updated.", "success")
    return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)


@router.post("/revoke-role")
@require_permission("admin_role_manage")
async def revoke_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    target_user = str(form.get("target_user", "")).strip()
    role_code = str(form.get("role_code", "")).strip().lower()
    reason = str(form.get("reason", "")).strip()
    require_reason = str(form.get("require_reason", "")).strip().lower() in {"1", "true", "yes", "y", "on"}
    selected_tab = str(form.get("tab", "")).strip().lower()
    if not target_user or not role_code:
        add_flash(request, "User and role are required.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)
    if require_reason and not reason:
        add_flash(request, "Revoke reason is required.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)
    target_user = repo.resolve_user_login_identifier(target_user) or target_user
    if role_code not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, f"Role `{role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    try:
        repo.revoke_role_grant(
            target_user_principal=target_user,
            role_code=role_code,
            revoked_by=user.user_principal,
            reason=(reason or None),
        )
    except Exception as exc:
        add_flash(request, f"Could not revoke role: {exc}", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="revoke_role",
        payload={"target_user": target_user, "role_code": role_code, "reason": reason},
    )
    add_flash(request, "Role revoked.", "success")
    return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)


@router.post("/users/save-access")
@require_permission("admin_role_manage")
async def save_user_access(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_access_tab_redirect("users"), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    selected_tab = str(form.get("tab", "users")).strip().lower()
    target_user = str(form.get("target_user", "")).strip()
    role_code = str(form.get("role_code", "")).strip().lower()
    scope_level = str(form.get("scope_level", "edit")).strip().lower()
    raw_business_unit_ids = list(form.getlist("business_unit_ids"))

    if not target_user:
        add_flash(request, "User selection is required.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)
    if not role_code:
        add_flash(request, "Role selection is required.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)
    if scope_level not in {"none", "read", "edit", "full"}:
        add_flash(request, "Invalid access level selected.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    target_user = repo.resolve_user_login_identifier(target_user) or target_user
    known_roles = set(repo.list_known_roles() or ROLE_CHOICES)
    if role_code not in known_roles:
        add_flash(request, f"Role `{role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    desired_business_units = sorted(
        {
            str(item).strip()
            for item in raw_business_unit_ids
            if str(item).strip() and str(item).strip().lower() != "all"
        }
    )
    desired_scope_orgs = set(desired_business_units) if scope_level != "none" else set()

    role_changed = False
    granted_scopes = 0
    revoked_scopes = 0
    try:
        role_rows = repo.list_role_grants(user_principal=target_user, limit=250, offset=0).to_dict("records")
        active_roles = [
            str(row.get("role_code") or "").strip().lower()
            for row in role_rows
            if str(row.get("active_flag") or "").strip().lower() in {"1", "true", "yes", "y"}
            and str(row.get("role_code") or "").strip()
        ]
        current_role = active_roles[0] if active_roles else ""
        if current_role != role_code:
            repo.grant_role(
                target_user_principal=target_user,
                role_code=role_code,
                granted_by=user.user_principal,
            )
            role_changed = True

        scope_rows = repo.list_scope_grants(user_principal=target_user, limit=500, offset=0).to_dict("records")
        active_scope_levels: dict[str, set[str]] = {}
        for row in scope_rows:
            if str(row.get("active_flag") or "").strip().lower() not in {"1", "true", "yes", "y"}:
                continue
            org_id = str(row.get("org_id") or "").strip()
            current_scope_level = str(row.get("scope_level") or "").strip().lower()
            if not org_id or not current_scope_level:
                continue
            active_scope_levels.setdefault(org_id, set()).add(current_scope_level)

        scope_changes_requested = bool(active_scope_levels) or bool(desired_scope_orgs)
        if scope_changes_requested and not user.can_apply_change("admin_scope_manage"):
            add_flash(request, "You do not have permission to manage Business Unit access.", "error")
            return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

        for org_id, levels in active_scope_levels.items():
            for current_scope_level in levels:
                if org_id not in desired_scope_orgs or current_scope_level != scope_level:
                    repo.revoke_org_scope(
                        target_user_principal=target_user,
                        org_id=org_id,
                        scope_level=current_scope_level,
                        revoked_by=user.user_principal,
                    )
                    revoked_scopes += 1

        for org_id in sorted(desired_scope_orgs):
            current_levels = active_scope_levels.get(org_id, set())
            if scope_level in current_levels:
                continue
            repo.grant_org_scope(
                target_user_principal=target_user,
                org_id=org_id,
                scope_level=scope_level,
                granted_by=user.user_principal,
            )
            granted_scopes += 1
    except Exception as exc:
        add_flash(request, f"Could not save user access: {exc}", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="save_user_access",
        payload={
            "target_user": target_user,
            "role_code": role_code,
            "role_changed": role_changed,
            "scope_level": scope_level,
            "business_unit_count": len(desired_scope_orgs),
            "scopes_granted": granted_scopes,
            "scopes_revoked": revoked_scopes,
        },
    )
    add_flash(
        request,
        (
            f"Access saved for {target_user}: role `{role_code}` "
            f"({len(desired_scope_orgs)} Business Units selected, +{granted_scopes} / -{revoked_scopes} scope changes)."
        ),
        "success",
    )
    return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)


@router.post("/grant-group-role")
@require_permission("admin_role_manage")
async def grant_group_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    selected_tab = str(form.get("tab", "groups")).strip().lower()
    target_group = str(form.get("target_group", "")).strip()
    role_code = str(form.get("role_code", "")).strip().lower()
    if not target_group or not role_code:
        add_flash(request, "Group and role are required.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)
    if role_code not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, f"Role `{role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)
    normalized_group = repo.normalize_group_principal(target_group)
    if not normalized_group:
        add_flash(request, "Group principal is invalid. Use a valid group identifier.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    try:
        repo.grant_group_role(group_principal=normalized_group, role_code=role_code, granted_by=user.user_principal)
    except Exception as exc:
        add_flash(request, f"Could not grant group role: {exc}", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="grant_group_role",
        payload={"target_group": normalized_group, "role_code": role_code},
    )
    add_flash(request, "Group role grant recorded.", "success")
    return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)


@router.post("/change-group-role")
@require_permission("admin_role_manage")
async def change_group_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    selected_tab = str(form.get("tab", "groups")).strip().lower()
    target_group = str(form.get("target_group", "")).strip()
    current_role_code = str(form.get("current_role_code", "")).strip().lower()
    new_role_code = str(form.get("new_role_code", "")).strip().lower()
    if not target_group or not current_role_code or not new_role_code:
        add_flash(request, "Group, current role, and new role are required.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)
    if new_role_code not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, f"Role `{new_role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)
    normalized_group = repo.normalize_group_principal(target_group)
    if not normalized_group:
        add_flash(request, "Group principal is invalid. Use a valid group identifier.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)
    if current_role_code == new_role_code:
        add_flash(request, "Group role is already set to that value.", "success")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    try:
        repo.change_group_role_grant(
            group_principal=normalized_group,
            current_role_code=current_role_code,
            new_role_code=new_role_code,
            granted_by=user.user_principal,
        )
    except Exception as exc:
        add_flash(request, f"Could not change group role: {exc}", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="change_group_role",
        payload={
            "target_group": normalized_group,
            "current_role_code": current_role_code,
            "new_role_code": new_role_code,
        },
    )
    add_flash(request, "Group role updated.", "success")
    return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)


@router.post("/revoke-group-role")
@require_permission("admin_role_manage")
async def revoke_group_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    selected_tab = str(form.get("tab", "groups")).strip().lower()
    target_group = str(form.get("target_group", "")).strip()
    role_code = str(form.get("role_code", "")).strip().lower()
    reason = str(form.get("reason", "")).strip()
    if not target_group or not role_code:
        add_flash(request, "Group and role are required.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)
    if role_code not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, f"Role `{role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)
    normalized_group = repo.normalize_group_principal(target_group)
    if not normalized_group:
        add_flash(request, "Group principal is invalid. Use a valid group identifier.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    try:
        repo.revoke_group_role_grant(
            group_principal=normalized_group,
            role_code=role_code,
            revoked_by=user.user_principal,
        )
    except Exception as exc:
        add_flash(request, f"Could not revoke group role: {exc}", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="revoke_group_role",
        payload={"target_group": normalized_group, "role_code": role_code, "reason": reason},
    )
    add_flash(request, "Group role revoked.", "success")
    return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)


@router.post("/groups/save-access")
@require_permission("admin_role_manage")
async def save_group_access(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_access_tab_redirect("groups"), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    selected_tab = str(form.get("tab", "groups")).strip().lower()
    target_group = str(form.get("target_group", "")).strip()
    role_code = str(form.get("role_code", "")).strip().lower()
    if not target_group:
        add_flash(request, "Group selection is required.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)
    if not role_code:
        add_flash(request, "Role selection is required.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)
    if role_code not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, f"Role `{role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    normalized_group = repo.normalize_group_principal(target_group)
    if not normalized_group:
        add_flash(request, "Group principal is invalid. Use a valid group identifier.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    revoked_count = 0
    granted = False
    try:
        existing = repo.list_group_role_grants(group_principal=normalized_group, limit=250, offset=0).to_dict("records")
        active_roles = {
            str(item.get("role_code") or "").strip().lower()
            for item in existing
            if str(item.get("active_flag") or "").strip().lower() in {"1", "true", "yes", "y"}
            and str(item.get("role_code") or "").strip()
        }
        for existing_role in sorted(active_roles):
            if existing_role == role_code:
                continue
            repo.revoke_group_role_grant(
                group_principal=normalized_group,
                role_code=existing_role,
                revoked_by=user.user_principal,
            )
            revoked_count += 1

        if role_code not in active_roles:
            repo.grant_group_role(
                group_principal=normalized_group,
                role_code=role_code,
                granted_by=user.user_principal,
            )
            granted = True
    except Exception as exc:
        add_flash(request, f"Could not save group access: {exc}", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="save_group_access",
        payload={
            "target_group": normalized_group,
            "role_code": role_code,
            "granted": granted,
            "roles_revoked": revoked_count,
        },
    )
    add_flash(request, f"Access saved for {normalized_group}: role `{role_code}`.", "success")
    return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)


@router.post("/roles/save")
@require_permission("admin_role_manage")
async def save_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    role_code = str(form.get("role_code", "")).strip().lower()
    role_name = str(form.get("role_name", "")).strip()
    description = str(form.get("description", "")).strip()
    approval_level_raw = str(form.get("approval_level", "0")).strip()

    if not ROLE_CODE_PATTERN.match(role_code):
        add_flash(
            request,
            "Role code must be 3-64 chars and use lowercase letters, numbers, _ or - (start with letter/number/_).",
            "error",
        )
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not role_name:
        add_flash(request, "Role name is required.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    try:
        approval_level = max(MIN_APPROVAL_LEVEL, min(int(approval_level_raw), MAX_APPROVAL_LEVEL))
    except Exception:
        add_flash(
            request,
            f"Approval level must be a number between {MIN_APPROVAL_LEVEL} and {MAX_APPROVAL_LEVEL}.",
            "error",
        )
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    can_edit = str(form.get("can_edit", "")).strip().lower() == "on"
    can_report = str(form.get("can_report", "")).strip().lower() == "on"
    can_direct_apply = str(form.get("can_direct_apply", "")).strip().lower() == "on"

    action_choices = list(change_action_choices())
    selected_actions = {
        action for action in action_choices if str(form.get(f"perm_{action}", "")).strip().lower() == "on"
    }

    try:
        repo.save_role_definition(
            role_code=role_code,
            role_name=role_name,
            description=description or None,
            approval_level=approval_level,
            can_edit=can_edit,
            can_report=can_report,
            can_direct_apply=can_direct_apply,
            updated_by=user.user_principal,
        )
        repo.replace_role_permissions(role_code=role_code, action_codes=selected_actions, updated_by=user.user_principal)
    except Exception as exc:
        add_flash(request, f"Could not save role definition: {exc}", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="save_role_definition",
        payload={
            "role_code": role_code,
            "approval_level": approval_level,
            "can_edit": can_edit,
            "can_report": can_report,
            "can_direct_apply": can_direct_apply,
            "permission_count": len(selected_actions),
        },
    )
    add_flash(request, f"Role `{role_code}` saved.", "success")
    return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)


