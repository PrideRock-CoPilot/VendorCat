from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.admin.common import (
    ADMIN_SECTION_DEFAULTS,
    LOOKUP_CODE_PATTERN,
    LOOKUP_TYPE_LABELS,
    _admin_redirect_url,
    _normalize_as_of_date,
    _normalize_lookup_status,
    _normalize_lookup_type,
    _slug_lookup_code,
)

router = APIRouter(prefix="/admin")


@router.post("/lookup/save")
async def save_lookup_option(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    lookup_type = _normalize_lookup_type(form.get("lookup_type"))
    lookup_status = _normalize_lookup_status(form.get("lookup_status"))
    as_of = _normalize_as_of_date(form.get("as_of"))
    redirect_url = _admin_redirect_url(
        section=ADMIN_SECTION_DEFAULTS,
        lookup_type=lookup_type,
        lookup_status=lookup_status,
        as_of=as_of,
    )
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=redirect_url, status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    option_code = str(form.get("option_code", "")).strip().lower()
    option_id = str(form.get("option_id", "")).strip() or None
    option_label = str(form.get("option_label", "")).strip()
    sort_order_raw = str(form.get("sort_order", "100")).strip()
    valid_from = str(form.get("valid_from_ts", "")).strip() or as_of
    valid_to = str(form.get("valid_to_ts", "")).strip() or "9999-12-31"

    if lookup_type not in LOOKUP_TYPE_LABELS:
        add_flash(request, "Lookup type is invalid.", "error")
        return RedirectResponse(url=redirect_url, status_code=303)
    if not option_code:
        option_code = _slug_lookup_code(option_label)
        if not option_code:
            add_flash(request, "Label is required for new options.", "error")
            return RedirectResponse(url=redirect_url, status_code=303)

    if not LOOKUP_CODE_PATTERN.match(option_code):
        add_flash(
            request,
            "Lookup code must be 2-64 chars and use lowercase letters, numbers, _ or -.",
            "error",
        )
        return RedirectResponse(url=redirect_url, status_code=303)
    try:
        sort_order = max(0, int(sort_order_raw or "0"))
    except Exception:
        add_flash(request, "Sort order must be a valid number.", "error")
        return RedirectResponse(url=redirect_url, status_code=303)

    try:
        repo.save_lookup_option(
            option_id=option_id,
            lookup_type=lookup_type,
            option_code=option_code,
            option_label=option_label or None,
            sort_order=sort_order,
            valid_from_ts=valid_from,
            valid_to_ts=valid_to,
            updated_by=user.user_principal,
        )
    except Exception as exc:
        add_flash(request, f"Could not save lookup option: {exc}", "error")
        return RedirectResponse(url=redirect_url, status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="save_lookup_option",
        payload={
            "lookup_type": lookup_type,
            "option_code": option_code,
            "valid_from_ts": valid_from,
            "valid_to_ts": valid_to,
        },
    )
    add_flash(request, f"Lookup option saved: {lookup_type}/{option_code}", "success")
    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/lookup/delete")
async def delete_lookup_option(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    lookup_type = _normalize_lookup_type(form.get("lookup_type"))
    lookup_status = _normalize_lookup_status(form.get("lookup_status"))
    as_of = _normalize_as_of_date(form.get("as_of"))
    redirect_url = _admin_redirect_url(
        section=ADMIN_SECTION_DEFAULTS,
        lookup_type=lookup_type,
        lookup_status=lookup_status,
        as_of=as_of,
    )
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=redirect_url, status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    option_id = str(form.get("option_id", "")).strip()
    if lookup_type not in LOOKUP_TYPE_LABELS:
        add_flash(request, "Lookup type is invalid.", "error")
        return RedirectResponse(url=redirect_url, status_code=303)
    if not option_id:
        add_flash(request, "Lookup option id is required.", "error")
        return RedirectResponse(url=redirect_url, status_code=303)

    try:
        repo.delete_lookup_option(
            lookup_type=lookup_type,
            option_id=option_id,
            updated_by=user.user_principal,
        )
    except Exception as exc:
        add_flash(request, f"Could not delete lookup option: {exc}", "error")
        return RedirectResponse(url=redirect_url, status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="delete_lookup_option",
        payload={"lookup_type": lookup_type, "option_id": option_id},
    )
    add_flash(request, "Lookup option removed.", "success")
    return RedirectResponse(url=redirect_url, status_code=303)

