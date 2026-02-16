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
    if not target_user or not role_code:
        add_flash(request, "User and role are required.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    target_user = repo.resolve_user_login_identifier(target_user) or target_user
    if role_code not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, f"Role `{role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    try:
        repo.revoke_role_grant(
            target_user_principal=target_user,
            role_code=role_code,
            revoked_by=user.user_principal,
        )
    except Exception as exc:
        add_flash(request, f"Could not revoke role: {exc}", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="revoke_role",
        payload={"target_user": target_user, "role_code": role_code},
    )
    add_flash(request, "Role revoked.", "success")
    return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)


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
    target_group = str(form.get("target_group", "")).strip()
    role_code = str(form.get("role_code", "")).strip().lower()
    if not target_group or not role_code:
        add_flash(request, "Group and role are required.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if role_code not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, f"Role `{role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    normalized_group = repo.normalize_group_principal(target_group)
    if not normalized_group:
        add_flash(request, "Group principal is invalid. Use a valid group identifier.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    try:
        repo.grant_group_role(group_principal=normalized_group, role_code=role_code, granted_by=user.user_principal)
    except Exception as exc:
        add_flash(request, f"Could not grant group role: {exc}", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="grant_group_role",
        payload={"target_group": normalized_group, "role_code": role_code},
    )
    add_flash(request, "Group role grant recorded.", "success")
    return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)


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
    target_group = str(form.get("target_group", "")).strip()
    current_role_code = str(form.get("current_role_code", "")).strip().lower()
    new_role_code = str(form.get("new_role_code", "")).strip().lower()
    if not target_group or not current_role_code or not new_role_code:
        add_flash(request, "Group, current role, and new role are required.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if new_role_code not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, f"Role `{new_role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    normalized_group = repo.normalize_group_principal(target_group)
    if not normalized_group:
        add_flash(request, "Group principal is invalid. Use a valid group identifier.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if current_role_code == new_role_code:
        add_flash(request, "Group role is already set to that value.", "success")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    try:
        repo.change_group_role_grant(
            group_principal=normalized_group,
            current_role_code=current_role_code,
            new_role_code=new_role_code,
            granted_by=user.user_principal,
        )
    except Exception as exc:
        add_flash(request, f"Could not change group role: {exc}", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

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
    return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)


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
    target_group = str(form.get("target_group", "")).strip()
    role_code = str(form.get("role_code", "")).strip().lower()
    if not target_group or not role_code:
        add_flash(request, "Group and role are required.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if role_code not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, f"Role `{role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    normalized_group = repo.normalize_group_principal(target_group)
    if not normalized_group:
        add_flash(request, "Group principal is invalid. Use a valid group identifier.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    try:
        repo.revoke_group_role_grant(
            group_principal=normalized_group,
            role_code=role_code,
            revoked_by=user.user_principal,
        )
    except Exception as exc:
        add_flash(request, f"Could not revoke group role: {exc}", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="revoke_group_role",
        payload={"target_group": normalized_group, "role_code": role_code},
    )
    add_flash(request, "Group role revoked.", "success")
    return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)


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

