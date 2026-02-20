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
    _normalize_contact_identity,
    _resolve_directory_user_principal,
    _safe_return_to,
    _vendor_base_context,
    _write_blocked,
)
from vendor_catalog_app.web.routers.vendors.constants import VENDOR_DEFAULT_RETURN_TO
from vendor_catalog_app.web.routers.vendors.constants import (
    CONTACT_ADD_REASON_OPTIONS,
    VENDOR_WARNING_CATEGORY_OPTIONS,
    VENDOR_WARNING_SEVERITY_OPTIONS,
    VENDOR_WARNING_STATUS_OPTIONS,
    ORG_ASSIGNMENT_REASON_OPTIONS,
    OWNER_ADD_REASON_OPTIONS,
)
from vendor_catalog_app.web.routers.vendors.pages import (
    _build_line_chart_points,
    _offering_lob_options,
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
    if isinstance(base, RedirectResponse):
        return base
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


@router.get("/{vendor_id}/warnings")
def vendor_warnings_page(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "warnings", return_to)
    if isinstance(base, RedirectResponse):
        return base
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    warnings_rows = repo.list_vendor_warnings(vendor_id, status="all").to_dict("records")
    open_statuses = {"open", "monitoring"}
    open_warning_count = sum(1 for row in warnings_rows if str(row.get("warning_status") or "").strip().lower() in open_statuses)

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Warnings",
        active_nav="vendors",
        extra={
            "section": "warnings",
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "summary": base["summary"],
            "warning_rows": warnings_rows,
            "warning_count": len(warnings_rows),
            "open_warning_count": open_warning_count,
            "warning_category_options": VENDOR_WARNING_CATEGORY_OPTIONS,
            "warning_severity_options": VENDOR_WARNING_SEVERITY_OPTIONS,
            "warning_status_options": VENDOR_WARNING_STATUS_OPTIONS,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_section.html", context)


@router.get("/{vendor_id}/ownership")
def vendor_ownership_page(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "ownership", return_to)
    if isinstance(base, RedirectResponse):
        return base
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    current_owner_org_id = str(base["profile_row"].get("owner_org_id") or "").strip()
    org_assignments_rows = repo.get_vendor_org_assignments(vendor_id).to_dict("records")
    ownership_active_lobs: list[str] = []
    for row in org_assignments_rows:
        active_flag = row.get("active_flag")
        is_active = str(active_flag).strip().lower() not in {"0", "false", "no", "n"}
        if not is_active:
            continue
        lob_value = str(row.get("org_id") or "").strip()
        if lob_value and lob_value not in ownership_active_lobs:
            ownership_active_lobs.append(lob_value)
    if current_owner_org_id and current_owner_org_id not in ownership_active_lobs:
        ownership_active_lobs.insert(0, current_owner_org_id)
    ownership_lob_items: list[dict[str, str | bool]] = []
    for lob_value in ownership_active_lobs:
        ownership_lob_items.append(
            {
                "lob": lob_value,
                "is_primary": bool(current_owner_org_id and lob_value == current_owner_org_id),
            }
        )
    ownership_lob_items.sort(key=lambda row: (not bool(row.get("is_primary")), str(row.get("lob") or "").lower()))

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
            "current_owner_org_id": current_owner_org_id,
            "ownership_active_lobs": ownership_active_lobs,
            "ownership_lob_items": ownership_lob_items,
            "ownership_lob_options": _offering_lob_options(repo),
            "owners": repo.get_vendor_business_owners(vendor_id).to_dict("records"),
            "org_assignments": org_assignments_rows,
            "contacts": repo.get_vendor_contacts(vendor_id).to_dict("records"),
            "owner_add_reason_options": OWNER_ADD_REASON_OPTIONS,
            "org_assignment_reason_options": ORG_ASSIGNMENT_REASON_OPTIONS,
            "contact_add_reason_options": CONTACT_ADD_REASON_OPTIONS,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_section.html", context)


@router.post("/{vendor_id}/ownership/lob/update")
@require_permission("vendor_edit")
async def update_vendor_ownership_lob_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/ownership")))
    selected_lobs = [str(item).strip() for item in form.getlist("lobs") if str(item).strip()]
    submitted_multi_lobs = bool(selected_lobs)
    legacy_lob = str(form.get("lob", "")).strip()
    if legacy_lob and legacy_lob not in selected_lobs:
        selected_lobs.insert(0, legacy_lob)
    primary_lob = str(form.get("primary_lob", "")).strip()
    if not primary_lob and legacy_lob and not submitted_multi_lobs:
        primary_lob = legacy_lob
    reason_code = str(form.get("reason_code", "")).strip().lower() or "ownership_alignment"
    if reason_code not in set(ORG_ASSIGNMENT_REASON_OPTIONS):
        reason_code = "ownership_alignment"
    reason_other_detail = str(form.get("reason_other_detail", "")).strip()
    if reason_code == "other":
        if not reason_other_detail:
            add_flash(request, "Enter a reason when 'Other' is selected.", "error")
            return RedirectResponse(url=return_to, status_code=303)
        reason = f"other: {reason_other_detail}"
    else:
        reason = reason_code

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    allowed_lobs = _offering_lob_options(repo)
    canonical_by_lower = {str(item).lower(): str(item) for item in allowed_lobs}
    normalized_lobs: list[str] = []
    for candidate in selected_lobs:
        canonical = canonical_by_lower.get(candidate.lower())
        if canonical and canonical not in normalized_lobs:
            normalized_lobs.append(canonical)
    normalized_primary_lob = ""
    if primary_lob:
        normalized_primary_lob = canonical_by_lower.get(primary_lob.lower(), "")
        if not normalized_primary_lob:
            add_flash(request, "Primary line of business must be selected from the admin-managed list.", "error")
            return RedirectResponse(url=return_to, status_code=303)
        if normalized_primary_lob not in normalized_lobs:
            add_flash(request, "Primary line of business must be one of the selected lines of business.", "error")
            return RedirectResponse(url=return_to, status_code=303)
    if not normalized_lobs and normalized_primary_lob:
        add_flash(request, "Primary line of business must be one of the selected lines of business.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload_updates = {"owner_org_id": normalized_primary_lob or ""}
        if user.can_apply_change("update_vendor_profile"):
            result = repo.apply_vendor_profile_update(
                vendor_id=vendor_id,
                actor_user_principal=user.user_principal,
                updates=payload_updates,
                reason=reason,
            )
            existing_assignments = repo.get_vendor_org_assignments(vendor_id)
            existing_lobs: set[str] = set()
            if not existing_assignments.empty:
                active_rows = existing_assignments[
                    ~existing_assignments["active_flag"].astype(str).str.strip().str.lower().isin({"0", "false", "no", "n"})
                ]
                existing_lobs = {str(item).strip() for item in active_rows["org_id"].tolist() if str(item).strip()}
            for lob_value in normalized_lobs:
                if lob_value in existing_lobs:
                    continue
                repo.add_vendor_org_assignment(
                    vendor_id=vendor_id,
                    org_id=lob_value,
                    assignment_type="consumer",
                    actor_user_principal=user.user_principal,
                )
            add_flash(
                request,
                f"Line of Business updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_vendor_profile",
                payload={"updates": payload_updates, "lobs": normalized_lobs, "reason": reason},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_ownership",
            event_type="update_vendor_ownership_lob",
            payload={
                "vendor_id": vendor_id,
                "lob": normalized_primary_lob,
                "lobs": normalized_lobs,
                "reason_code": reason_code,
                "reason_other_detail": reason_other_detail,
            },
        )
    except Exception as exc:
        add_flash(request, f"Could not update Line of Business: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/warnings/add")
@require_permission("vendor_edit")
async def add_vendor_warning_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/warnings")))

    warning_category = str(form.get("warning_category", "")).strip().lower()
    severity = str(form.get("severity", "")).strip().lower()
    warning_title = str(form.get("warning_title", "")).strip()
    warning_detail = str(form.get("warning_detail", "")).strip()
    source_table = str(form.get("source_table", "")).strip()
    source_version = str(form.get("source_version", "")).strip()
    file_name = str(form.get("file_name", "")).strip()
    detected_at = str(form.get("detected_at", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    if warning_category not in set(VENDOR_WARNING_CATEGORY_OPTIONS):
        add_flash(request, "Warning category is invalid.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if severity not in set(VENDOR_WARNING_SEVERITY_OPTIONS):
        add_flash(request, "Warning severity is invalid.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not warning_title:
        add_flash(request, "Warning title is required.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        warning_id = repo.create_vendor_warning(
            vendor_id=vendor_id,
            actor_user_principal=user.user_principal,
            warning_category=warning_category,
            severity=severity,
            warning_title=warning_title,
            warning_detail=warning_detail,
            source_table=source_table,
            source_version=source_version,
            file_name=file_name,
            detected_at=detected_at,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_warnings",
            event_type="add_vendor_warning",
            payload={
                "vendor_id": vendor_id,
                "warning_id": warning_id,
                "warning_category": warning_category,
                "severity": severity,
            },
        )
        add_flash(request, f"Warning added: {warning_id}", "success")
    except Exception as exc:
        add_flash(request, f"Could not add warning: {exc}", "error")

    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/warnings/{warning_id}/resolve")
@require_permission("vendor_edit")
async def resolve_vendor_warning_submit(request: Request, vendor_id: str, warning_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/warnings")))
    warning_status = str(form.get("warning_status", "resolved")).strip().lower() or "resolved"

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if warning_status not in set(VENDOR_WARNING_STATUS_OPTIONS):
        add_flash(request, "Warning status is invalid.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        repo.resolve_vendor_warning(
            vendor_id=vendor_id,
            warning_id=warning_id,
            actor_user_principal=user.user_principal,
            new_status=warning_status,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_warnings",
            event_type="resolve_vendor_warning",
            payload={
                "vendor_id": vendor_id,
                "warning_id": warning_id,
                "warning_status": warning_status,
            },
        )
        add_flash(request, "Warning status updated.", "success")
    except Exception as exc:
        add_flash(request, f"Could not update warning: {exc}", "error")

    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/owners/add")
@require_permission("vendor_owner_create")
async def add_vendor_owner_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/ownership")))
    owner_user_principal = str(form.get("owner_user_principal", "")).strip()
    owner_user_display_name = str(form.get("owner_user_principal_display_name", "")).strip()
    owner_role = str(form.get("owner_role", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        owner_user_principal = _resolve_directory_user_principal(
            repo,
            principal_value=owner_user_principal,
            display_name_value=owner_user_display_name,
            error_message="Owner must exist in the app user directory.",
        )
    except Exception as exc:
        add_flash(request, str(exc), "error")
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
@router.post("/{vendor_id}/lob-assignments/add")
@require_permission("vendor_org_assignment_create")
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
            add_flash(request, f"LOB assignment added: {assignment_id}", "success")
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
        add_flash(request, f"Could not add LOB assignment: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/contacts/add")
@require_permission("vendor_contact_create")
async def add_vendor_contact_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/ownership")))
    full_name = str(form.get("full_name", "")).strip()
    full_name_display = str(form.get("full_name_display_name", "")).strip()
    contact_type = str(form.get("contact_type", "")).strip()
    email = str(form.get("email", "")).strip()
    phone = str(form.get("phone", "")).strip()
    reason = str(form.get("reason", "")).strip()
    full_name = _normalize_contact_identity(
        full_name=full_name,
        full_name_display=full_name_display,
        email=email,
    )

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





