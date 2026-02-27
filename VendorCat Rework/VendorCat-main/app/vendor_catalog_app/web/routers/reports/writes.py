from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.reports.common import (
    DATABRICKS_SELECTED_REPORT_PARAM,
    REPORT_TYPES,
    _build_report_frame,
    _can_use_reports,
    _normalize_report_filters,
    _report_query_payload,
    _resolve_selected_columns,
    _safe_query_params,
    _safe_report_key,
    _workspace_delete_board,
    _workspace_upsert_board,
)
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

    report_type = str(form.get("report_type", "vendor_inventory"))
    search = str(form.get("search", "")).strip()
    vendor = str(form.get("vendor", "all")).strip() or "all"
    lifecycle_state = str(form.get("lifecycle_state", "all")).strip() or "all"
    project_status = str(form.get("project_status", "all")).strip() or "all"
    outcome = str(form.get("outcome", "all")).strip() or "all"
    owner_principal = str(form.get("owner_principal", "")).strip()
    business_unit = str(form.get("business_unit", "")).strip()
    legacy_org = str(form.get("org", "")).strip()
    selected_business_unit = business_unit or legacy_org or "all"
    cols = str(form.get("cols", "")).strip()
    view_mode = str(form.get("view_mode", "both")).strip()
    chart_kind = str(form.get("chart_kind", "bar")).strip()
    chart_x = str(form.get("chart_x", "")).strip()
    chart_y = str(form.get("chart_y", "")).strip()
    dbx_report = _safe_report_key(str(form.get("dbx_report", "")).strip(), "")

    email_to = str(form.get("email_to", "")).strip()
    email_subject = str(form.get("email_subject", "")).strip()
    normalized = _normalize_report_filters(
        repo,
        report_type=report_type,
        search=search,
        vendor=vendor,
        lifecycle_state=lifecycle_state,
        project_status=project_status,
        outcome=outcome,
        owner_principal=owner_principal,
        business_unit=selected_business_unit,
        org=None,
        horizon_days=str(form.get("horizon_days", "180")).strip(),
        limit=str(form.get("limit", "500")).strip(),
        view_mode=view_mode,
        chart_kind=chart_kind,
    )
    report_type = str(normalized["report_type"])
    search = str(normalized["search"])
    vendor = str(normalized["vendor"])
    lifecycle_state = str(normalized["lifecycle_state"])
    project_status = str(normalized["project_status"])
    outcome = str(normalized["outcome"])
    owner_principal = str(normalized["owner_principal"])
    selected_business_unit = str(normalized["business_unit"])
    horizon_days = int(normalized["horizon_days"])
    limit = int(normalized["limit"])
    view_mode = str(normalized["view_mode"])
    chart_kind = str(normalized["chart_kind"])

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
            business_unit=selected_business_unit,
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
                "business_unit": selected_business_unit,
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
        business_unit=selected_business_unit,
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


@router.post("/reports/workspace/boards/save")
@require_permission("report_submit")
async def reports_workspace_save_board(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url="/reports/workspace", status_code=303)
    if not _can_use_reports(user):
        add_flash(request, "You do not have permission to save report boards.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    board_name = str(form.get("board_name", "")).strip()
    board_json = str(form.get("board_json", "")).strip()
    board_id = str(form.get("board_id", "")).strip()
    safe_board_id = _safe_report_key(board_id, "")

    try:
        board = _workspace_upsert_board(
            repo,
            user_principal=user.user_principal,
            board_name=board_name,
            board_json=board_json,
            board_id=safe_board_id,
        )
    except ValueError as exc:
        add_flash(request, str(exc), "error")
        if safe_board_id:
            return RedirectResponse(url=f"/reports/workspace?board={safe_board_id}", status_code=303)
        return RedirectResponse(url="/reports/workspace", status_code=303)

    board_payload = {
        "board_id": board.get("board_id"),
        "board_name": board.get("board_name"),
        "widget_count": board.get("widget_count"),
    }
    try:
        parsed_payload = json.loads(board_json) if board_json else {}
    except json.JSONDecodeError:
        parsed_payload = {}
    if isinstance(parsed_payload, dict):
        source_version = parsed_payload.get("version")
        if source_version is not None:
            board_payload["source_version"] = source_version

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="reports_workspace",
        event_type="workspace_board_save",
        payload=board_payload,
    )
    add_flash(request, f"Saved report board '{board.get('board_name')}'.", "success")
    return RedirectResponse(url=f"/reports/workspace?board={board.get('board_id')}", status_code=303)


@router.post("/reports/workspace/boards/delete")
@require_permission("report_submit")
async def reports_workspace_delete_board(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url="/reports/workspace", status_code=303)
    if not _can_use_reports(user):
        add_flash(request, "You do not have permission to delete report boards.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    board_id = _safe_report_key(str(form.get("board_id", "")).strip(), "")
    if not board_id:
        add_flash(request, "Select a board to remove.", "error")
        return RedirectResponse(url="/reports/workspace", status_code=303)

    removed = _workspace_delete_board(repo, user_principal=user.user_principal, board_id=board_id)
    if not removed:
        add_flash(request, "Board was not found or already removed.", "info")
        return RedirectResponse(url="/reports/workspace", status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="reports_workspace",
        event_type="workspace_board_delete",
        payload={"board_id": board_id},
    )
    add_flash(request, "Report board removed.", "success")
    return RedirectResponse(url="/reports/workspace", status_code=303)

