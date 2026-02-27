from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.terms import save_terms_document
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.admin.common import ADMIN_SECTION_TERMS, _admin_redirect_url
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/admin")


@router.post("/terms/save")
@require_permission("admin_lookup_manage")
async def save_terms(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    redirect_url = _admin_redirect_url(section=ADMIN_SECTION_TERMS)

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=redirect_url, status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    title = str(form.get("title") or "").strip()
    effective_date = str(form.get("effective_date") or "").strip()
    document_text = str(form.get("document_text") or "").strip()

    try:
        saved = save_terms_document(
            repo=repo,
            title=title,
            effective_date=effective_date,
            document_text=document_text,
            updated_by=user.user_principal,
        )
    except Exception as exc:
        add_flash(request, f"Could not update user agreement: {exc}", "error")
        return RedirectResponse(url=redirect_url, status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="save_terms_document",
        payload={
            "title": str(saved.get("title") or ""),
            "effective_date": str(saved.get("effective_date") or ""),
        },
    )
    add_flash(request, "User agreement updated.", "success")
    return RedirectResponse(url=redirect_url, status_code=303)
