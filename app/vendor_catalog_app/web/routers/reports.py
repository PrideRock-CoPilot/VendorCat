from __future__ import annotations

import io
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from vendor_catalog_app.web.flash import add_flash
from vendor_catalog_app.web.services import (
    base_template_context,
    ensure_session_started,
    get_repo,
    get_user_context,
    log_page_view,
)


router = APIRouter()

REPORT_TYPES = {
    "vendor_inventory": {
        "label": "Vendor Inventory",
        "description": "Vendor profile, ownership, and count metrics across offerings, contracts, and projects.",
    },
    "project_portfolio": {
        "label": "Project Portfolio",
        "description": "Cross-vendor project view with linked entities and activity depth.",
    },
    "contract_renewals": {
        "label": "Contract Renewals",
        "description": "Renewal pipeline, value, status, and risk for upcoming contracts.",
    },
    "demo_outcomes": {
        "label": "Demo Outcomes",
        "description": "Demo scoring and outcomes for selected vs not-selected decisions.",
    },
    "owner_coverage": {
        "label": "Owner Coverage",
        "description": "Owner-to-entity matrix for vendor, offering, and project ownership workloads.",
    },
}

VENDOR_LIFECYCLE_STATES = ["all", "draft", "submitted", "in_review", "approved", "active", "suspended", "retired"]
PROJECT_STATUSES = ["all", "draft", "active", "blocked", "complete", "cancelled"]
DEMO_OUTCOMES = ["all", "selected", "not_selected", "deferred", "follow_up", "unknown"]
ROW_LIMITS = [100, 250, 500, 1000, 2500]


def _can_use_reports(user) -> bool:
    return bool(getattr(user, "can_report", False))


def _safe_report_type(report_type: str) -> str:
    cleaned = (report_type or "").strip().lower()
    if cleaned in REPORT_TYPES:
        return cleaned
    return "vendor_inventory"


def _safe_query_params(params: dict[str, str | int]) -> str:
    safe = {k: v for k, v in params.items() if v not in (None, "", [])}
    return urlencode(safe)


def _vendor_options(repo) -> list[dict[str, str]]:
    vendor_df = repo.search_vendors(search_text="", lifecycle_state="all")
    options = [{"vendor_id": "all", "label": "all"}]
    for row in vendor_df.to_dict("records"):
        vendor_id = str(row.get("vendor_id") or "")
        label = str(row.get("display_name") or row.get("legal_name") or vendor_id)
        if vendor_id:
            options.append({"vendor_id": vendor_id, "label": f"{label} ({vendor_id})"})
    return options


def _build_report_frame(
    repo,
    *,
    report_type: str,
    search: str,
    vendor: str,
    lifecycle_state: str,
    project_status: str,
    outcome: str,
    owner_principal: str,
    org: str,
    horizon_days: int,
    limit: int,
):
    if report_type == "vendor_inventory":
        frame = repo.report_vendor_inventory(
            search_text=search,
            lifecycle_state=lifecycle_state,
            owner_principal=owner_principal,
            limit=limit,
        )
    elif report_type == "project_portfolio":
        frame = repo.report_project_portfolio(
            search_text=search,
            status=project_status,
            vendor_id=vendor,
            owner_principal=owner_principal,
            limit=limit,
        )
    elif report_type == "contract_renewals":
        frame = repo.report_contract_renewals(
            search_text=search,
            vendor_id=vendor,
            org_id=org,
            horizon_days=horizon_days,
            limit=limit,
        )
    elif report_type == "demo_outcomes":
        frame = repo.report_demo_outcomes(
            search_text=search,
            vendor_id=vendor,
            outcome=outcome,
            limit=limit,
        )
    else:
        frame = repo.report_owner_coverage(
            search_text=search,
            owner_principal=owner_principal,
            vendor_id=vendor,
            limit=limit,
        )
    return frame


@router.get("/reports")
def reports_home(
    request: Request,
    run: int = 0,
    report_type: str = "vendor_inventory",
    search: str = "",
    vendor: str = "all",
    lifecycle_state: str = "all",
    project_status: str = "all",
    outcome: str = "all",
    owner_principal: str = "",
    org: str = "all",
    horizon_days: int = 180,
    limit: int = 500,
    cols: str = "",
):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Reports")

    if not _can_use_reports(user):
        add_flash(request, "You do not have permission to access Reports.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    report_type = _safe_report_type(report_type)
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
    vendor_options = _vendor_options(repo)
    valid_vendor_ids = {row["vendor_id"] for row in vendor_options}
    if vendor not in valid_vendor_ids:
        vendor = "all"
    horizon_days = max(30, min(horizon_days, 730))

    rows: list[dict] = []
    columns: list[str] = []
    selected_columns: list[str] = []
    row_count = 0
    preview_count = 0
    download_url = ""
    selected_report = REPORT_TYPES[report_type]

    if run == 1:
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
        row_count = int(len(frame))
        columns = [str(c) for c in frame.columns.tolist()]
        requested_cols = [x.strip() for x in cols.split(",") if x.strip()]
        if requested_cols:
            selected_columns = [c for c in columns if c in requested_cols]
        if not selected_columns:
            selected_columns = columns
        preview = frame[selected_columns].head(200).fillna("")
        rows = preview.to_dict("records")
        preview_count = int(len(preview))

        query = _safe_query_params(
            {
                "report_type": report_type,
                "search": search,
                "vendor": vendor,
                "lifecycle_state": lifecycle_state,
                "project_status": project_status,
                "outcome": outcome,
                "owner_principal": owner_principal,
                "org": org,
                "horizon_days": horizon_days,
                "limit": limit,
                "cols": ",".join(selected_columns),
            }
        )
        download_url = f"/reports/download?{query}"
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="reports",
            event_type="report_run",
            payload={
                "report_type": report_type,
                "row_count": row_count,
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
            },
        )

    context = base_template_context(
        request=request,
        context=user,
        title="Reports",
        active_nav="reports",
        extra={
            "filters": {
                "run": run,
                "report_type": report_type,
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
            "report_types": REPORT_TYPES,
            "vendor_lifecycle_states": VENDOR_LIFECYCLE_STATES,
            "project_statuses": PROJECT_STATUSES,
            "demo_outcomes": DEMO_OUTCOMES,
            "row_limits": ROW_LIMITS,
            "vendor_options": vendor_options,
            "orgs": orgs,
            "selected_report": selected_report,
            "rows": rows,
            "columns": columns,
            "selected_columns": selected_columns,
            "row_count": row_count,
            "preview_count": preview_count,
            "download_url": download_url,
        },
    )
    return request.app.state.templates.TemplateResponse("reports.html", context)


@router.get("/reports/download")
def reports_download(
    request: Request,
    report_type: str = "vendor_inventory",
    search: str = "",
    vendor: str = "all",
    lifecycle_state: str = "all",
    project_status: str = "all",
    outcome: str = "all",
    owner_principal: str = "",
    org: str = "all",
    horizon_days: int = 180,
    limit: int = 500,
    cols: str = "",
):
    repo = get_repo()
    user = get_user_context(request)
    if not _can_use_reports(user):
        add_flash(request, "You do not have permission to download reports.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    report_type = _safe_report_type(report_type)
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
    if frame.empty:
        add_flash(request, "No rows available for download with the selected filters.", "info")
        query = _safe_query_params(
            {
                "run": 1,
                "report_type": report_type,
                "search": search,
                "vendor": vendor,
                "lifecycle_state": lifecycle_state,
                "project_status": project_status,
                "outcome": outcome,
                "owner_principal": owner_principal,
                "org": org,
                "horizon_days": horizon_days,
                "limit": limit,
            }
        )
        return RedirectResponse(url=f"/reports?{query}", status_code=303)

    selected_cols = [x.strip() for x in cols.split(",") if x.strip()]
    if selected_cols:
        selected_cols = [c for c in frame.columns.tolist() if c in selected_cols]
    if selected_cols:
        frame = frame[selected_cols]

    stream = io.StringIO()
    frame.to_csv(stream, index=False)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{report_type}_{stamp}.csv"
    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="reports",
        event_type="report_download",
        payload={"report_type": report_type, "row_count": int(len(frame)), "columns": list(frame.columns)},
    )
    return Response(
        content=stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/reports/email")
async def reports_email_request(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
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
    email_to = str(form.get("email_to", "")).strip()
    email_subject = str(form.get("email_subject", "")).strip()
    limit_text = str(form.get("limit", "500")).strip()
    horizon_text = str(form.get("horizon_days", "180")).strip()
    try:
        limit = int(limit_text)
    except Exception:
        limit = 500
    try:
        horizon_days = int(horizon_text)
    except Exception:
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
        selected_cols = [x.strip() for x in cols.split(",") if x.strip()]
        if selected_cols:
            selected_cols = [c for c in frame.columns.tolist() if c in selected_cols]
        if selected_cols:
            frame = frame[selected_cols]

        payload = {
            "report_type": report_type,
            "to": email_to,
            "subject": email_subject or f"{REPORT_TYPES[report_type]['label']} Extract",
            "row_count": int(len(frame)),
            "columns": list(frame.columns),
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

    query = _safe_query_params(
        {
            "run": 1,
            "report_type": report_type,
            "search": search,
            "vendor": vendor,
            "lifecycle_state": lifecycle_state,
            "project_status": project_status,
            "outcome": outcome,
            "owner_principal": owner_principal,
            "org": org,
            "horizon_days": horizon_days,
            "limit": limit,
            "cols": cols,
        }
    )
    return RedirectResponse(url=f"/reports?{query}", status_code=303)
