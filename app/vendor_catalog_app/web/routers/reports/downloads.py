from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.reports.common import *

router = APIRouter()


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
    lob: str = "all",
    org: str | None = None,
    horizon_days: int = 180,
    limit: int = 500,
    cols: str = "",
    view_mode: str = "both",
    chart_kind: str = "bar",
    chart_x: str = "",
    chart_y: str = "",
):
    repo = get_repo()
    user = get_user_context(request)
    if not _can_use_reports(user):
        add_flash(request, "You do not have permission to download reports.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    report_type = _safe_report_type(report_type)
    view_mode = _safe_view_mode(view_mode)
    chart_kind = _safe_chart_kind(chart_kind)

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
        lob=selected_lob,
        horizon_days=horizon_days,
        limit=limit,
    )
    if frame.empty:
        add_flash(request, "No rows available for download with the selected filters.", "info")
        query = _safe_query_params(
            _report_query_payload(
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
                cols=cols,
                view_mode=view_mode,
                chart_kind=chart_kind,
                chart_x=chart_x,
                chart_y=chart_y,
                run=1,
            )
        )
        return RedirectResponse(url=f"/reports?{query}", status_code=303)

    selected_cols = _resolve_selected_columns(frame, cols)
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
        payload={
            "report_type": report_type,
            "row_count": int(len(frame)),
            "columns": list(frame.columns),
            "view_mode": view_mode,
            "chart": {"kind": chart_kind, "x": chart_x, "y": chart_y},
        },
    )
    return Response(
        content=stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/workspace/boards/export")
def reports_workspace_export_board(request: Request, board: str = ""):
    repo = get_repo()
    user = get_user_context(request)
    if not _can_use_reports(user):
        add_flash(request, "You do not have permission to export report boards.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    board_id = _safe_report_key(board, "")
    if not board_id:
        add_flash(request, "Select a board to export.", "error")
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

    bundle = io.BytesIO()
    manifest_widgets: list[dict[str, object]] = []
    raw_widgets = selected_board.get("widgets")
    widgets = raw_widgets if isinstance(raw_widgets, list) else []
    with zipfile.ZipFile(bundle, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
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
            csv_stream = io.StringIO()
            frame.to_csv(csv_stream, index=False)
            safe_title = _safe_report_key(str(widget.get("title") or f"widget-{index + 1}"), f"widget-{index + 1}")
            csv_name = f"{index + 1:02d}_{safe_title}.csv"
            archive.writestr(csv_name, csv_stream.getvalue())

            manifest_widgets.append(
                {
                    "index": index + 1,
                    "title": str(widget.get("title") or f"Widget {index + 1}"),
                    "widget_type": str(widget.get("widget_type") or "chart"),
                    "report_type": report_type,
                    "row_count": int(len(frame)),
                    "columns": [str(column) for column in frame.columns.tolist()],
                    "csv_file": csv_name,
                    "query": payload,
                }
            )

        manifest = {
            "version": REPORTS_WORKSPACE_VERSION,
            "board_id": selected_board.get("board_id"),
            "board_name": selected_board.get("board_name"),
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "widget_count": len(manifest_widgets),
            "widgets": manifest_widgets,
        }
        archive.writestr("board_manifest.json", json.dumps(manifest, indent=2))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"reports_board_{board_id}_{stamp}.zip"
    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="reports_workspace",
        event_type="workspace_board_export",
        payload={
            "board_id": selected_board.get("board_id"),
            "board_name": selected_board.get("board_name"),
            "widget_count": len(manifest_widgets),
        },
    )
    return Response(
        content=bundle.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


