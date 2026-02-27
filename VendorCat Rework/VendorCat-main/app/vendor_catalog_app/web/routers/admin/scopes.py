from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.admin.common import (
    ADMIN_SECTION_ACCESS,
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


@router.post("/grant-scope")
@require_permission("admin_scope_manage")
async def grant_scope(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    selected_tab = str(form.get("tab", "business_unit")).strip().lower()
    target_user = str(form.get("target_user", "")).strip()
    business_unit_id = str(form.get("business_unit_id", "")).strip() or str(form.get("org_id", "")).strip()
    scope_level = str(form.get("scope_level", "")).strip()
    if not target_user or not business_unit_id or not scope_level:
        add_flash(request, "User, business unit, and scope level are required.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    repo.grant_org_scope(
        target_user_principal=target_user,
        org_id=business_unit_id,
        scope_level=scope_level,
        granted_by=user.user_principal,
    )
    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="grant_scope",
        payload={"target_user": target_user, "business_unit_id": business_unit_id, "scope_level": scope_level},
    )
    add_flash(request, "Business Unit scope grant recorded.", "success")
    return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)


@router.post("/revoke-scope")
@require_permission("admin_scope_manage")
async def revoke_scope(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    selected_tab = str(form.get("tab", "business_unit")).strip().lower()
    target_user = str(form.get("target_user", "")).strip()
    business_unit_id = str(form.get("business_unit_id", "")).strip() or str(form.get("org_id", "")).strip()
    scope_level = str(form.get("scope_level", "")).strip().lower()
    if not target_user or not business_unit_id or not scope_level:
        add_flash(request, "User, business unit, and scope level are required.", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)
    target_user = repo.resolve_user_login_identifier(target_user) or target_user

    try:
        repo.revoke_org_scope(
            target_user_principal=target_user,
            org_id=business_unit_id,
            scope_level=scope_level,
            revoked_by=user.user_principal,
        )
    except Exception as exc:
        add_flash(request, f"Could not revoke Business Unit scope: {exc}", "error")
        return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="revoke_scope",
        payload={"target_user": target_user, "business_unit_id": business_unit_id, "scope_level": scope_level},
    )
    add_flash(request, "Business Unit scope revoked.", "success")
    return RedirectResponse(url=_access_tab_redirect(selected_tab), status_code=303)


