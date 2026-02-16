from __future__ import annotations

from fastapi import APIRouter

from vendor_catalog_app.web.routers.reports.common import *

router = APIRouter()
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
    view_mode: str = "both",
    chart_kind: str = "",
    chart_x: str = "",
    chart_y: str = "",
    dbx_report: str = "",
):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Reports")

    if not _can_use_reports(user):
        add_flash(request, "You do not have permission to access Reports.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    report_type = _safe_report_type(report_type)
    view_mode = _safe_view_mode(view_mode)
    preset = CHART_PRESETS.get(report_type, {})
    preset_kind = _safe_chart_kind(str(preset.get("kind") or "bar"))
    chart_kind = _safe_chart_kind(chart_kind or preset_kind)
    preset_x = str(preset.get("x") or ROW_INDEX_DIMENSION)
    preset_y = str(preset.get("y") or ROW_COUNT_METRIC)

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
    powerbi_download_url = ""

    chart_rows: list[dict[str, object]] = []
    chart_line_points: list[dict[str, object]] = []
    chart_line_path = ""
    chart_total_value = 0.0
    chart_max_value = 0.0
    chart_empty_message = "Run a report to build a graph."

    dimension_seed = [ROW_INDEX_DIMENSION]
    if preset_x and preset_x not in dimension_seed:
        dimension_seed.append(preset_x)
    metric_seed = [ROW_COUNT_METRIC]
    if preset_y and preset_y not in metric_seed:
        metric_seed.append(preset_y)
    chart_dimension_options = _chart_dimension_items(dimension_seed)
    chart_metric_options = _chart_metric_items(metric_seed)
    selected_chart_x = (chart_x or "").strip() or preset_x
    selected_chart_y = (chart_y or "").strip() or preset_y

    selected_report = REPORT_TYPES[report_type]
    databricks_reports = _databricks_report_options(user.config)
    selected_databricks_report: dict[str, object] | None = None

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
        selected_columns = _resolve_selected_columns(frame, cols)
        preview = frame[selected_columns].head(200).fillna("") if selected_columns else frame.head(200).fillna("")
        rows = preview.to_dict("records")
        preview_count = int(len(preview))

        dimension_columns, metric_columns = _chart_column_options(frame)
        (
            chart_kind,
            selected_chart_x,
            selected_chart_y,
            dimension_option_keys,
            metric_option_keys,
        ) = _resolve_chart_selection(
            report_type=report_type,
            chart_kind=chart_kind,
            chart_x=selected_chart_x,
            chart_y=selected_chart_y,
            dimension_columns=dimension_columns,
            metric_columns=metric_columns,
        )
        chart_dimension_options = _chart_dimension_items(dimension_option_keys)
        chart_metric_options = _chart_metric_items(metric_option_keys)

        chart_data = _build_chart_dataset(
            frame,
            chart_kind=chart_kind,
            chart_x=selected_chart_x,
            chart_y=selected_chart_y,
        )
        chart_rows = chart_data["rows"]
        chart_line_points = chart_data["line_points"]
        chart_line_path = str(chart_data["line_path"])
        chart_max_value = float(chart_data["max_value"])
        chart_total_value = float(chart_data["total_value"])
        if not chart_rows:
            chart_empty_message = "No chartable rows with the selected visualization settings."

        report_query = _report_query_payload(
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
            cols=",".join(selected_columns),
            view_mode=view_mode,
            chart_kind=chart_kind,
            chart_x=selected_chart_x,
            chart_y=selected_chart_y,
        )
        query = _safe_query_params(report_query)
        download_url = f"/reports/download?{query}"
        powerbi_download_url = f"/reports/download/powerbi?{query}"

        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="reports",
            event_type="report_run",
            payload={
                "report_type": report_type,
                "row_count": row_count,
                "view_mode": view_mode,
                "chart": {
                    "kind": chart_kind,
                    "x": selected_chart_x,
                    "y": selected_chart_y,
                    "points": len(chart_rows),
                },
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

    selected_key = _safe_report_key(dbx_report, "") if dbx_report else ""
    base_query_payload = _report_query_payload(
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
        cols=",".join(selected_columns) if selected_columns else cols,
        view_mode=view_mode,
        chart_kind=chart_kind,
        chart_x=selected_chart_x,
        chart_y=selected_chart_y,
        run=run,
    )
    databricks_report_items: list[dict[str, object]] = []
    for report in databricks_reports:
        key = str(report.get("key") or "").strip()
        if not key:
            continue
        link_payload = dict(base_query_payload)
        link_payload[DATABRICKS_SELECTED_REPORT_PARAM] = key
        item = dict(report)
        item["embed_link"] = f"/reports?{_safe_query_params(link_payload)}"
        item["is_selected"] = key == selected_key
        databricks_report_items.append(item)
        if item["is_selected"] and bool(item.get("can_embed")):
            selected_databricks_report = item

    chart_dimension_label = "Row Order" if selected_chart_x == ROW_INDEX_DIMENSION else selected_chart_x
    chart_metric_label = "Row Count" if selected_chart_y == ROW_COUNT_METRIC else selected_chart_y

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
                "view_mode": view_mode,
                "chart_kind": chart_kind,
                "chart_x": selected_chart_x,
                "chart_y": selected_chart_y,
                "dbx_report": selected_key,
            },
            "report_types": REPORT_TYPES,
            "vendor_lifecycle_states": VENDOR_LIFECYCLE_STATES,
            "project_statuses": PROJECT_STATUSES,
            "demo_outcomes": DEMO_OUTCOMES,
            "row_limits": ROW_LIMITS,
            "view_modes": VIEW_MODES,
            "chart_kinds": CHART_KINDS,
            "vendor_options": vendor_options,
            "orgs": orgs,
            "selected_report": selected_report,
            "rows": rows,
            "columns": columns,
            "selected_columns": selected_columns,
            "row_count": row_count,
            "preview_count": preview_count,
            "download_url": download_url,
            "powerbi_download_url": powerbi_download_url,
            "show_table": view_mode in {"table", "both"},
            "show_chart": view_mode in {"chart", "both"},
            "chart_rows": chart_rows,
            "chart_line_points": chart_line_points,
            "chart_line_path": chart_line_path,
            "chart_max_value": chart_max_value,
            "chart_total_value": chart_total_value,
            "chart_empty_message": chart_empty_message,
            "chart_dimension_options": chart_dimension_options,
            "chart_metric_options": chart_metric_options,
            "chart_dimension_label": chart_dimension_label,
            "chart_metric_label": chart_metric_label,
            "databricks_reports": databricks_report_items,
            "selected_databricks_report": selected_databricks_report,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "reports.html", context)


