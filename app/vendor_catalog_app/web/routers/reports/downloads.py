from __future__ import annotations

from fastapi import APIRouter

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
    org: str = "all",
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
            _report_query_payload(
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


@router.get("/reports/download/powerbi")
def reports_download_powerbi(
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
            _report_query_payload(
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
        )
        return RedirectResponse(url=f"/reports?{query}", status_code=303)

    selected_cols = _resolve_selected_columns(frame, cols)
    if selected_cols:
        frame = frame[selected_cols]

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

    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        report_csv = io.StringIO()
        frame.to_csv(report_csv, index=False)
        archive.writestr("report_data.csv", report_csv.getvalue())

        chart_rows = chart_data["rows"]
        if chart_rows:
            chart_csv = io.StringIO()
            writer = csv.writer(chart_csv)
            writer.writerow(["label", "value", "share_pct"])
            for row in chart_rows:
                writer.writerow([row["label"], row["value"], row["share_pct"]])
            archive.writestr("chart_data.csv", chart_csv.getvalue())

        manifest = {
            "report_type": report_type,
            "report_label": REPORT_TYPES[report_type]["label"],
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "row_count": int(len(frame)),
            "columns": list(frame.columns),
            "view_mode": view_mode,
            "chart": {
                "kind": chart_kind,
                "x": chart_x,
                "y": chart_y,
                "point_count": len(chart_rows),
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
            "powerbi_note": "Import report_data.csv and chart_data.csv into Power BI Desktop to generate/update your PBIX report.",
        }
        archive.writestr("report_manifest.json", json.dumps(manifest, indent=2))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{report_type}_{stamp}_powerbi_seed.zip"

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="reports",
        event_type="report_powerbi_download",
        payload={
            "report_type": report_type,
            "row_count": int(len(frame)),
            "columns": list(frame.columns),
            "view_mode": view_mode,
            "chart": {"kind": chart_kind, "x": chart_x, "y": chart_y, "points": len(chart_rows)},
        },
    )
    return Response(
        content=bundle.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


