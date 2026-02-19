from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.core.activity import ensure_session_started, log_page_view
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
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
    lob: str = "all",
    org: str | None = None,
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
    selected_lob = str(org if org is not None and str(org).strip() else lob).strip() or "all"
    if selected_lob not in orgs:
        selected_lob = "all"

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
    ready_report_cards: list[dict[str, object]] = []
    for key, info in REPORT_TYPES.items():
        preset = CHART_PRESETS.get(key, {})
        preset_kind = _safe_chart_kind(str(preset.get("kind") or "bar"))
        preset_x = str(preset.get("x") or ROW_INDEX_DIMENSION)
        preset_y = str(preset.get("y") or ROW_COUNT_METRIC)
        ready_payload = _report_query_payload(
            report_type=key,
            search="",
            vendor="all",
            lifecycle_state="all",
            project_status="all",
            outcome="all",
            owner_principal="",
            lob="all",
            horizon_days=180,
            limit=500,
            cols="",
            view_mode="both",
            chart_kind=preset_kind,
            chart_x=preset_x,
            chart_y=preset_y,
            run=1,
        )
        ready_report_cards.append(
            {
                "key": key,
                "label": str(info.get("label") or key),
                "description": str(info.get("description") or ""),
                "open_url": f"/reports?{_safe_query_params(ready_payload)}",
                "is_selected": key == report_type,
            }
        )

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
            lob=selected_lob,
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
            lob=selected_lob,
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
                    "lob": selected_lob,
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
        lob=selected_lob,
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
                "lob": selected_lob,
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
            "ready_report_cards": ready_report_cards,
            "databricks_reports": databricks_report_items,
            "selected_databricks_report": selected_databricks_report,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "reports.html", context)


@router.get("/reports/workspace")
def reports_workspace(request: Request, board: str = ""):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Reports Workspace")

    if not _can_use_reports(user):
        add_flash(request, "You do not have permission to access Reports Workspace.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    report_cards: list[dict[str, str]] = []
    report_type_options: list[dict[str, str]] = []
    for key, info in REPORT_TYPES.items():
        preset = CHART_PRESETS.get(key, {})
        preset_kind = _safe_chart_kind(str(preset.get("kind") or "bar"))
        preset_x = str(preset.get("x") or ROW_INDEX_DIMENSION)
        preset_y = str(preset.get("y") or ROW_COUNT_METRIC)

        report_type_options.append(
            {
                "key": key,
                "label": str(info.get("label") or key),
                "description": str(info.get("description") or ""),
                "preset_kind": preset_kind,
                "preset_x": preset_x,
                "preset_y": preset_y,
            }
        )

        query_payload = _report_query_payload(
            report_type=key,
            search="",
            vendor="all",
            lifecycle_state="all",
            project_status="all",
            outcome="all",
            owner_principal="",
            lob="all",
            horizon_days=180,
            limit=500,
            cols="",
            view_mode="both",
            chart_kind=preset_kind,
            chart_x=preset_x,
            chart_y=preset_y,
            run=1,
        )
        query = _safe_query_params(query_payload)
        report_cards.append(
            {
                "key": key,
                "label": str(info.get("label") or key),
                "description": str(info.get("description") or ""),
                "open_url": f"/reports?{query}",
            }
        )

    databricks_reports = _databricks_report_options(user.config)
    saved_boards = _workspace_load_boards(repo, user.user_principal)
    selected_board_id = _safe_report_key(board, "") if board else ""
    selected_board: dict[str, object] | None = None
    if selected_board_id:
        for candidate in saved_boards:
            if str(candidate.get("board_id") or "") == selected_board_id:
                selected_board = candidate
                break
    context = base_template_context(
        request=request,
        context=user,
        title="Reports Workspace",
        active_nav="reports",
        extra={
            "report_cards": report_cards,
            "report_type_options": report_type_options,
            "view_modes": VIEW_MODES,
            "chart_kinds": CHART_KINDS,
            "row_limits": ROW_LIMITS,
            "vendor_options": _vendor_options(repo),
            "databricks_reports": databricks_reports,
            "saved_boards": saved_boards,
            "selected_board": selected_board,
            "selected_board_id": selected_board_id,
            "designer_defaults": {
                "report_type": "vendor_inventory",
                "view_mode": "chart",
                "chart_kind": "bar",
                "chart_x": "display_name",
                "chart_y": "total_contract_value",
                "vendor": "all",
                "search": "",
                "limit": 500,
            },
        },
    )
    return request.app.state.templates.TemplateResponse(request, "reports_workspace.html", context)


@router.get("/reports/workspace/present")
def reports_workspace_present(request: Request, board: str = ""):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Reports Workspace Presentation")

    if not _can_use_reports(user):
        add_flash(request, "You do not have permission to access Reports Workspace.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    board_id = _safe_report_key(board, "")
    if not board_id:
        add_flash(request, "Select a board to present.", "error")
        return RedirectResponse(url="/reports/workspace", status_code=303)

    boards = _workspace_load_boards(repo, user.user_principal)
    selected_board: dict[str, object] | None = None
    for item in boards:
        if str(item.get("board_id") or "") == board_id:
            selected_board = item
            break
    if selected_board is None:
        add_flash(request, "Saved board was not found.", "error")
        return RedirectResponse(url="/reports/workspace", status_code=303)

    widget_views: list[dict[str, object]] = []
    raw_widgets = selected_board.get("widgets")
    widgets = raw_widgets if isinstance(raw_widgets, list) else []
    for index, raw_widget in enumerate(widgets):
        widget = _workspace_normalize_widget(raw_widget, index)
        payload = _workspace_widget_query_payload(widget)
        report_type = _safe_report_type(str(payload.get("report_type") or "vendor_inventory"))
        search = str(payload.get("search") or "").strip()
        vendor = str(payload.get("vendor") or "all").strip() or "all"
        try:
            limit = int(payload.get("limit", 500))
        except (TypeError, ValueError):
            limit = 500
        if limit not in ROW_LIMITS:
            limit = 500
        view_mode = _safe_view_mode(str(payload.get("view_mode") or "both"))
        chart_kind = _safe_chart_kind(str(payload.get("chart_kind") or "bar"))
        chart_x = str(payload.get("chart_x") or "").strip() or ROW_INDEX_DIMENSION
        chart_y = str(payload.get("chart_y") or "").strip() or ROW_COUNT_METRIC

        frame = _build_report_frame(
            repo,
            report_type=report_type,
            search=search,
            vendor=vendor,
            lifecycle_state="all",
            project_status="all",
            outcome="all",
            owner_principal="",
            lob="all",
            horizon_days=180,
            limit=limit,
        )
        preview = frame.head(12).fillna("")
        preview_rows = preview.to_dict("records")
        preview_columns = [str(column) for column in preview.columns.tolist()]

        dimension_columns, metric_columns = _chart_column_options(frame)
        chart_kind, chart_x, chart_y, _, _ = _resolve_chart_selection(
            report_type=report_type,
            chart_kind=chart_kind,
            chart_x=chart_x,
            chart_y=chart_y,
            dimension_columns=dimension_columns,
            metric_columns=metric_columns,
        )
        chart_data = _build_chart_dataset(
            frame,
            chart_kind=chart_kind,
            chart_x=chart_x,
            chart_y=chart_y,
        )
        chart_rows = chart_data["rows"]
        chart_line_points = chart_data["line_points"]
        chart_line_path = str(chart_data["line_path"])

        query = _safe_query_params(payload)
        widget_views.append(
            {
                "index": index,
                "title": str(widget.get("title") or f"Widget {index + 1}"),
                "widget_type": str(widget.get("widget_type") or "chart"),
                "report_type": report_type,
                "report_label": str(REPORT_TYPES[report_type]["label"]),
                "view_mode": view_mode,
                "chart_kind": chart_kind,
                "chart_x": chart_x,
                "chart_y": chart_y,
                "row_count": int(len(frame)),
                "preview_rows": preview_rows,
                "preview_columns": preview_columns,
                "chart_rows": chart_rows,
                "chart_line_points": chart_line_points,
                "chart_line_path": chart_line_path,
                "show_chart": view_mode in {"chart", "both"},
                "show_table": view_mode in {"table", "both"},
                "run_url": f"/reports?{query}",
            }
        )

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="reports_workspace",
        event_type="workspace_board_present",
        payload={
            "board_id": board_id,
            "board_name": selected_board.get("board_name"),
            "widget_count": len(widget_views),
        },
    )
    context = base_template_context(
        request=request,
        context=user,
        title=f"Reports Presentation - {selected_board.get('board_name')}",
        active_nav="reports",
        extra={
            "board": selected_board,
            "widget_views": widget_views,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "reports_workspace_present.html", context)


