from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.core.security import ROLE_CHOICES
from vendor_catalog_app.web.core.runtime import get_repo, testing_role_override_enabled
from vendor_catalog_app.web.core.user_context_service import (
    ADMIN_ROLE_OVERRIDE_SESSION_KEY,
    get_user_context,
)
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/admin")


@router.post("/testing-role")
@require_permission("admin_testing_role")
async def set_testing_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if not testing_role_override_enabled(user.config):
        add_flash(request, "Testing role override is disabled in this environment.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)
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

