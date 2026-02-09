from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.security import (
    ROLE_ADMIN,
    ROLE_AUDITOR,
    ROLE_EDITOR,
    ROLE_STEWARD,
    ROLE_VIEWER,
)
from vendor_catalog_app.web.flash import add_flash
from vendor_catalog_app.web.services import (
    base_template_context,
    ensure_session_started,
    get_repo,
    get_user_context,
    log_page_view,
)


router = APIRouter(prefix="/admin")


@router.get("")
def admin(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Admin Permissions")

    if not user.is_admin:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    context = base_template_context(
        request=request,
        context=user,
        title="Admin Permissions",
        active_nav="admin",
        extra={
            "roles": [ROLE_ADMIN, ROLE_STEWARD, ROLE_EDITOR, ROLE_VIEWER, ROLE_AUDITOR],
            "role_rows": repo.list_role_grants().to_dict("records"),
            "scope_rows": repo.list_scope_grants().to_dict("records"),
        },
    )
    return request.app.state.templates.TemplateResponse("admin.html", context)


@router.post("/grant-role")
async def grant_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if not user.is_admin:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    target_user = str(form.get("target_user", "")).strip()
    role_code = str(form.get("role_code", "")).strip()
    if not target_user or not role_code:
        add_flash(request, "User and role are required.", "error")
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
    if not user.is_admin:
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

