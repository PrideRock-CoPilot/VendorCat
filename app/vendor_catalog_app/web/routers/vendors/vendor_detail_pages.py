from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.core.defaults import (
    DEFAULT_PROJECT_STATUS_ACTIVE,
    DEFAULT_VENDOR_SUMMARY_MONTHS,
)
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.vendors.common import (
    _safe_return_to,
    _vendor_base_context,
    _write_blocked,
)
from vendor_catalog_app.web.routers.vendors.constants import VENDOR_DEFAULT_RETURN_TO
from vendor_catalog_app.web.routers.vendors.pages import (
    _build_line_chart_points,
    _series_with_bar_pct,
)
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/vendors")

@router.get("/{vendor_id}")
def vendor_default(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    return RedirectResponse(
        url=f"/vendors/{vendor_id}/summary?return_to={quote(_safe_return_to(return_to), safe='')}",
        status_code=302,
    )


@router.get("/{vendor_id}/summary")
def vendor_summary_page(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "summary", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    profile_row = base["profile_row"]
    contacts = repo.get_vendor_contacts(vendor_id).to_dict("records")
    top_contacts = contacts[:3]
    top_offerings = repo.get_vendor_offerings(vendor_id).head(5).to_dict("records")
    for row in top_offerings:
        row["_offering_link"] = (
            f"/vendors/{vendor_id}/offerings/{row.get('offering_id')}?return_to={quote(base['return_to'], safe='')}"
        )
    projects_df = repo.list_projects(vendor_id)
    if "status" in projects_df.columns:
        active_projects = projects_df[projects_df["status"].astype(str).str.lower() == DEFAULT_PROJECT_STATUS_ACTIVE]
        projects_preview = (active_projects if not active_projects.empty else projects_df).head(5).to_dict("records")
    else:
        projects_preview = projects_df.head(5).to_dict("records")
    for row in projects_preview:
        row["_project_link"] = (
            f"/vendors/{vendor_id}/projects/{row.get('project_id')}?return_to={quote(base['return_to'], safe='')}"
        )
    docs_preview = repo.list_docs("vendor", vendor_id).head(5).to_dict("records")

    spend_category = _series_with_bar_pct(
        repo.vendor_spend_by_category(vendor_id, months=DEFAULT_VENDOR_SUMMARY_MONTHS).to_dict("records"),
        "total_spend",
    )
    spend_trend_rows = repo.vendor_monthly_spend_trend(vendor_id, months=DEFAULT_VENDOR_SUMMARY_MONTHS).to_dict("records")
    trend_points, spend_trend_plot_rows = _build_line_chart_points(spend_trend_rows, "month", "total_spend")
    raw_fields = [{"field": key, "value": value} for key, value in profile_row.items()]

    key_facts = {
        "legal_name": profile_row.get("legal_name"),
        "display_name": profile_row.get("display_name"),
        "vendor_id": profile_row.get("vendor_id"),
        "owner_org_id": profile_row.get("owner_org_id"),
        "source_system": profile_row.get("source_system"),
        "active_lobs": ", ".join(base["summary"].get("active_lob_values") or []) or "-",
        "active_service_types": ", ".join(base["summary"].get("active_service_type_values") or []) or "-",
        "updated_at": profile_row.get("updated_at"),
    }

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Summary",
        active_nav="vendors",
        extra={
            "section": "summary",
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "summary": base["summary"],
            "key_facts": key_facts,
            "top_contacts": top_contacts,
            "top_offerings": top_offerings,
            "offerings_page_link": f"/vendors/{vendor_id}/offerings?return_to={quote(base['return_to'], safe='')}",
            "projects_preview": projects_preview,
            "projects_page_link": f"/vendors/{vendor_id}/projects?return_to={quote(base['return_to'], safe='')}",
            "docs_preview": docs_preview,
            "doc_source_options": repo.list_doc_source_options(),
            "spend_category": spend_category,
            "spend_trend_points": trend_points,
            "spend_trend_plot_rows": spend_trend_plot_rows,
            "raw_fields": raw_fields,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_section.html", context)


@router.get("/{vendor_id}/ownership")
def vendor_ownership_page(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "ownership", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Ownership",
        active_nav="vendors",
        extra={
            "section": "ownership",
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "summary": base["summary"],
            "owners": repo.get_vendor_business_owners(vendor_id).to_dict("records"),
            "org_assignments": repo.get_vendor_org_assignments(vendor_id).to_dict("records"),
            "contacts": repo.get_vendor_contacts(vendor_id).to_dict("records"),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_section.html", context)


@router.post("/{vendor_id}/owners/add")
async def add_vendor_owner_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/ownership")))
    owner_user_principal = str(form.get("owner_user_principal", "")).strip()
    owner_role = str(form.get("owner_role", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {
            "owner_user_principal": owner_user_principal,
            "owner_role": owner_role,
            "reason": reason,
        }
        if user.can_apply_change("add_vendor_owner"):
            owner_id = repo.add_vendor_owner(
                vendor_id=vendor_id,
                owner_user_principal=owner_user_principal,
                owner_role=owner_role,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Vendor owner added: {owner_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_vendor_owner",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_ownership",
            event_type="add_vendor_owner",
            payload={"vendor_id": vendor_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not add vendor owner: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/org-assignments/add")
async def add_vendor_org_assignment_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/ownership")))
    org_id = str(form.get("org_id", "")).strip()
    assignment_type = str(form.get("assignment_type", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {"org_id": org_id, "assignment_type": assignment_type, "reason": reason}
        if user.can_apply_change("add_vendor_org_assignment"):
            assignment_id = repo.add_vendor_org_assignment(
                vendor_id=vendor_id,
                org_id=org_id,
                assignment_type=assignment_type,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Org assignment added: {assignment_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_vendor_org_assignment",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_ownership",
            event_type="add_vendor_org_assignment",
            payload={"vendor_id": vendor_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not add org assignment: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/contacts/add")
@require_permission("vendor_contact_create")
async def add_vendor_contact_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/ownership")))
    full_name = str(form.get("full_name", "")).strip()
    contact_type = str(form.get("contact_type", "")).strip()
    email = str(form.get("email", "")).strip()
    phone = str(form.get("phone", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {
            "full_name": full_name,
            "contact_type": contact_type,
            "email": email or None,
            "phone": phone or None,
            "reason": reason,
        }
        if user.can_apply_change("add_vendor_contact"):
            contact_id = repo.add_vendor_contact(
                vendor_id=vendor_id,
                full_name=full_name,
                contact_type=contact_type,
                email=email or None,
                phone=phone or None,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Vendor contact added: {contact_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_vendor_contact",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_ownership",
            event_type="add_vendor_contact",
            payload={"vendor_id": vendor_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not add vendor contact: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.get("/{vendor_id}/portfolio")
def vendor_portfolio_compat(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings?return_to={quote(_safe_return_to(return_to), safe='')}",
        status_code=302,
    )





