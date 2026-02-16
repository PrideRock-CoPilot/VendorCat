from __future__ import annotations

from fastapi import APIRouter

from vendor_catalog_app.web.routers.reports.common import *
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter()
@router.post("/reports/email")
@require_permission("report_email")
async def reports_email_request(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url="/reports", status_code=303)
    if not _can_use_reports(user):
        add_flash(request, "You do not have permission to request emailed extracts.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    report_type = _safe_report_type(str(form.get("report_type", "vendor_inventory")))
    search = str(form.get("search", "")).strip()
    vendor = str(form.get("vendor", "all")).strip() or "all"
    lifecycle_state = str(form.get("lifecycle_state", "all")).strip() or "all"
    project_status = str(form.get("project_status", "all")).strip() or "all"
    outcome = str(form.get("outcome", "all")).strip() or "all"
    owner_principal = str(form.get("owner_principal", "")).strip()
    org = str(form.get("org", "all")).strip() or "all"
    cols = str(form.get("cols", "")).strip()
    view_mode = _safe_view_mode(str(form.get("view_mode", "both")))
    chart_kind = _safe_chart_kind(str(form.get("chart_kind", "bar")))
    chart_x = str(form.get("chart_x", "")).strip()
    chart_y = str(form.get("chart_y", "")).strip()
    dbx_report = _safe_report_key(str(form.get("dbx_report", "")).strip(), "")

    email_to = str(form.get("email_to", "")).strip()
    email_subject = str(form.get("email_subject", "")).strip()
    limit_text = str(form.get("limit", "500")).strip()
    horizon_text = str(form.get("horizon_days", "180")).strip()

    try:
        limit = int(limit_text)
    except ValueError:
        limit = 500
    try:
        horizon_days = int(horizon_text)
    except ValueError:
        horizon_days = 180

    if lifecycle_state not in VENDOR_LIFECYCLE_STATES:
        lifecycle_state = "all"
    if project_status not in PROJECT_STATUSES:
        project_status = "all"
    if outcome not in DEMO_OUTCOMES:
        outcome = "all"
    if limit not in ROW_LIMITS:
        limit = 500

    orgs = repo.available_orgs()
    if org not in orgs:
        org = "all"
    horizon_days = max(30, min(horizon_days, 730))

    if not email_to or "@" not in email_to:
        add_flash(request, "Provide a valid email recipient.", "error")
    else:
        frame = _build_report_frame(
            repo,
            report_type=report_type,
            search=search,
            vendor=vendor,
            lifecycle_state=lifecycle_state,
            project_status=project_status,
            outcome=outcome,
            owner_principal=owner_principal,
            org=org,
            horizon_days=horizon_days,
            limit=limit,
        )
        selected_cols = _resolve_selected_columns(frame, cols)
        if selected_cols:
            frame = frame[selected_cols]

        payload = {
            "report_type": report_type,
            "to": email_to,
            "subject": email_subject or f"{REPORT_TYPES[report_type]['label']} Extract",
            "row_count": int(len(frame)),
            "columns": list(frame.columns),
            "view_mode": view_mode,
            "chart": {"kind": chart_kind, "x": chart_x, "y": chart_y},
            "filters": {
                "search": search,
                "vendor": vendor,
                "lifecycle_state": lifecycle_state,
                "project_status": project_status,
                "outcome": outcome,
                "owner_principal": owner_principal,
                "org": org,
                "horizon_days": horizon_days,
                "limit": limit,
            },
        }
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="reports",
            event_type="report_email_request",
            payload=payload,
        )
        add_flash(
            request,
            "Email extract request queued. Delivery integration can process these queued requests from usage logs.",
            "success",
        )

    redirect_payload = _report_query_payload(
        report_type=report_type,
        search=search,
        vendor=vendor,
        lifecycle_state=lifecycle_state,
        project_status=project_status,
        outcome=outcome,
        owner_principal=owner_principal,
        org=org,
        horizon_days=horizon_days,
        limit=limit,
        cols=cols,
        view_mode=view_mode,
        chart_kind=chart_kind,
        chart_x=chart_x,
        chart_y=chart_y,
        run=1,
    )
    if dbx_report:
        redirect_payload[DATABRICKS_SELECTED_REPORT_PARAM] = dbx_report
    query = _safe_query_params(redirect_payload)
    return RedirectResponse(url=f"/reports?{query}", status_code=303)
