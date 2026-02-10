from __future__ import annotations

import re

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.security import (
    CHANGE_APPROVAL_LEVELS,
    ROLE_CHOICES,
    change_action_choices,
)
from vendor_catalog_app.web.flash import add_flash
from vendor_catalog_app.web.services import (
    ADMIN_ROLE_OVERRIDE_SESSION_KEY,
    base_template_context,
    ensure_session_started,
    get_repo,
    get_user_context,
    log_page_view,
)


router = APIRouter(prefix="/admin")
ROLE_CODE_PATTERN = re.compile(r"^[a-z0-9_][a-z0-9_-]{2,63}$")


@router.get("")
def admin(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Admin Permissions")

    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    role_definitions = repo.list_role_definitions()
    role_permissions = repo.list_role_permissions()
    permission_map: dict[str, list[str]] = {}
    for row in role_permissions.to_dict("records"):
        role_code = str(row.get("role_code") or "").strip()
        action_code = str(row.get("action_code") or "").strip().lower()
        if not role_code or action_code not in CHANGE_APPROVAL_LEVELS:
            continue
        if not bool(row.get("active_flag", True)):
            continue
        permission_map.setdefault(role_code, []).append(action_code)

    role_def_rows = []
    for row in role_definitions.to_dict("records"):
        role_code = str(row.get("role_code") or "").strip()
        if not role_code:
            continue
        actions = sorted(set(permission_map.get(role_code, [])))
        role_def_rows.append(
            {
                "role_code": role_code,
                "role_name": str(row.get("role_name") or role_code),
                "description": str(row.get("description") or ""),
                "approval_level": int(row.get("approval_level") or 0),
                "can_edit": bool(row.get("can_edit")),
                "can_report": bool(row.get("can_report")),
                "can_direct_apply": bool(row.get("can_direct_apply")),
                "active_flag": bool(row.get("active_flag", True)),
                "actions": actions,
                "actions_summary": ", ".join(actions) if actions else "(none)",
            }
        )

    known_roles = repo.list_known_roles() or list(ROLE_CHOICES)

    context = base_template_context(
        request=request,
        context=user,
        title="Admin Permissions",
        active_nav="admin",
        extra={
            "grantable_roles": known_roles,
            "role_rows": repo.list_role_grants().to_dict("records"),
            "scope_rows": repo.list_scope_grants().to_dict("records"),
            "role_definitions": role_def_rows,
            "role_code_options": known_roles,
            "change_actions": list(change_action_choices()),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "admin.html", context)


@router.post("/grant-role")
async def grant_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url="/admin", status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    target_user = str(form.get("target_user", "")).strip()
    role_code = str(form.get("role_code", "")).strip().lower()
    if not target_user or not role_code:
        add_flash(request, "User and role are required.", "error")
        return RedirectResponse(url="/admin", status_code=303)
    if role_code not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, f"Role `{role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url="/admin", status_code=303)

    repo.grant_role(target_user_principal=target_user, role_code=role_code, granted_by=user.user_principal)
    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="grant_role",
        payload={"target_user": target_user, "role_code": role_code},
    )
    add_flash(request, "Role grant recorded.", "success")
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/grant-scope")
async def grant_scope(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url="/admin", status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    target_user = str(form.get("target_user", "")).strip()
    org_id = str(form.get("org_id", "")).strip()
    scope_level = str(form.get("scope_level", "")).strip()
    if not target_user or not org_id or not scope_level:
        add_flash(request, "User, org, and scope level are required.", "error")
        return RedirectResponse(url="/admin", status_code=303)

    repo.grant_org_scope(
        target_user_principal=target_user,
        org_id=org_id,
        scope_level=scope_level,
        granted_by=user.user_principal,
    )
    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="grant_scope",
        payload={"target_user": target_user, "org_id": org_id, "scope_level": scope_level},
    )
    add_flash(request, "Org scope grant recorded.", "success")
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/roles/save")
async def save_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url="/admin", status_code=303)
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
        return RedirectResponse(url="/admin", status_code=303)
    if not role_name:
        add_flash(request, "Role name is required.", "error")
        return RedirectResponse(url="/admin", status_code=303)

    try:
        approval_level = max(0, min(int(approval_level_raw), 3))
    except Exception:
        add_flash(request, "Approval level must be a number between 0 and 3.", "error")
        return RedirectResponse(url="/admin", status_code=303)

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
        return RedirectResponse(url="/admin", status_code=303)
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
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/testing-role")
async def set_testing_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    return_to = str(form.get("return_to", "/dashboard"))
    safe_return_to = "/dashboard"
    if return_to.startswith("/"):
        safe_return_to = return_to
    selected = str(form.get("role_override", "")).strip()

    if selected and selected not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, "Invalid testing role override selected.", "error")
        return RedirectResponse(url=f"{safe_return_to}", status_code=303)

    if selected:
        request.session[ADMIN_ROLE_OVERRIDE_SESSION_KEY] = selected
        add_flash(request, f"Testing role override set to {selected}.", "success")
    else:
        request.session.pop(ADMIN_ROLE_OVERRIDE_SESSION_KEY, None)
        add_flash(request, "Testing role override cleared.", "success")
    return RedirectResponse(url=f"{safe_return_to}", status_code=303)
