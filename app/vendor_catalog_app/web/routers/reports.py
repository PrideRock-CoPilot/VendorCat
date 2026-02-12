from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse, urlunparse

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from vendor_catalog_app.env import (
    TVENDOR_DATABRICKS_REPORTS_ALLOWED_HOSTS,
    TVENDOR_DATABRICKS_REPORTS_ALLOW_EMBED,
    TVENDOR_DATABRICKS_REPORTS_JSON,
    get_env,
    get_env_bool,
)
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

VIEW_MODES = ["table", "chart", "both"]
CHART_KINDS = ["bar", "line"]
ROW_INDEX_DIMENSION = "__row_index__"
ROW_COUNT_METRIC = "__row_count__"
MAX_CHART_POINTS = 40

CHART_PRESETS = {
    "vendor_inventory": {"kind": "bar", "x": "display_name", "y": "total_contract_value"},
    "project_portfolio": {"kind": "bar", "x": "status", "y": ROW_COUNT_METRIC},
    "contract_renewals": {"kind": "line", "x": "renewal_date", "y": "annual_value"},
    "demo_outcomes": {"kind": "bar", "x": "selection_outcome", "y": ROW_COUNT_METRIC},
    "owner_coverage": {"kind": "bar", "x": "owner_principal", "y": ROW_COUNT_METRIC},
}

DATABRICKS_SELECTED_REPORT_PARAM = "dbx_report"


def _can_use_reports(user) -> bool:
    return bool(getattr(user, "can_report", False))


def _safe_report_type(report_type: str) -> str:
    cleaned = (report_type or "").strip().lower()
    if cleaned in REPORT_TYPES:
        return cleaned
    return "vendor_inventory"


def _safe_query_params(params: dict[str, object]) -> str:
    safe = {k: v for k, v in params.items() if v not in (None, "", [])}
    return urlencode(safe, doseq=True)


def _safe_view_mode(view_mode: str) -> str:
    cleaned = (view_mode or "").strip().lower()
    if cleaned in VIEW_MODES:
        return cleaned
    return "both"


def _safe_chart_kind(chart_kind: str) -> str:
    cleaned = (chart_kind or "").strip().lower()
    if cleaned in CHART_KINDS:
        return cleaned
    return "bar"


def _safe_label(value: object) -> str:
    text = str(value or "").strip()
    return text or "Unknown"


def _format_chart_value(value: float) -> str:
    number = float(value or 0.0)
    if abs(number) >= 1000:
        return f"{number:,.0f}" if number.is_integer() else f"{number:,.2f}"
    return f"{number:,.0f}" if number.is_integer() else f"{number:,.2f}"


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


def _resolve_selected_columns(frame: pd.DataFrame, cols: str) -> list[str]:
    available = [str(column) for column in frame.columns.tolist()]
    requested = [x.strip() for x in cols.split(",") if x.strip()]
    if requested:
        selected = [column for column in available if column in requested]
        if selected:
            return selected
    return available


def _chart_column_options(frame: pd.DataFrame) -> tuple[list[str], list[str]]:
    columns = [str(column) for column in frame.columns.tolist()]
    metric_columns = [str(column) for column in frame.select_dtypes(include=["number"]).columns.tolist()]
    dimension_columns = [column for column in columns if column not in metric_columns]
    return dimension_columns, metric_columns


def _resolve_chart_selection(
    *,
    report_type: str,
    chart_kind: str,
    chart_x: str,
    chart_y: str,
    dimension_columns: list[str],
    metric_columns: list[str],
) -> tuple[str, str, str, list[str], list[str]]:
    dimension_options = [ROW_INDEX_DIMENSION] + [column for column in dimension_columns if column != ROW_INDEX_DIMENSION]
    metric_options = [ROW_COUNT_METRIC] + [column for column in metric_columns if column != ROW_COUNT_METRIC]

    preset = CHART_PRESETS.get(report_type, {})
    default_kind = _safe_chart_kind(str(preset.get("kind") or "bar"))
    selected_kind = _safe_chart_kind(chart_kind or default_kind)

    default_x = str(preset.get("x") or "")
    if default_x not in dimension_options:
        default_x = dimension_columns[0] if dimension_columns else ROW_INDEX_DIMENSION
    selected_x = chart_x if chart_x in dimension_options else default_x

    default_y = str(preset.get("y") or "")
    if default_y not in metric_options:
        default_y = metric_columns[0] if metric_columns else ROW_COUNT_METRIC
    selected_y = chart_y if chart_y in metric_options else default_y

    return selected_kind, selected_x, selected_y, dimension_options, metric_options


def _empty_chart_dataset() -> dict[str, object]:
    return {
        "rows": [],
        "line_points": [],
        "line_path": "",
        "max_value": 0.0,
        "total_value": 0.0,
    }


def _build_chart_dataset(
    frame: pd.DataFrame,
    *,
    chart_kind: str,
    chart_x: str,
    chart_y: str,
) -> dict[str, object]:
    if frame.empty:
        return _empty_chart_dataset()

    if chart_x == ROW_INDEX_DIMENSION:
        scoped = frame.head(MAX_CHART_POINTS).copy()
        labels = [f"Row {idx + 1}" for idx in range(len(scoped))]
        if chart_y == ROW_COUNT_METRIC:
            values = [1.0] * len(scoped)
        else:
            if chart_y not in scoped.columns:
                return _empty_chart_dataset()
            values = pd.to_numeric(scoped[chart_y], errors="coerce").fillna(0.0).astype(float).tolist()
        grouped = pd.DataFrame({"label": labels, "value": values})
    else:
        if chart_x not in frame.columns:
            return _empty_chart_dataset()
        labels = frame[chart_x].map(_safe_label)
        if chart_y == ROW_COUNT_METRIC:
            grouped = labels.to_frame(name="label").groupby("label", as_index=False).size().rename(columns={"size": "value"})
        else:
            if chart_y not in frame.columns:
                return _empty_chart_dataset()
            values = pd.to_numeric(frame[chart_y], errors="coerce").fillna(0.0)
            grouped = labels.to_frame(name="label")
            grouped["value"] = values.astype(float)
            grouped = grouped.groupby("label", as_index=False)["value"].sum()

    if grouped.empty:
        return _empty_chart_dataset()

    grouped["value"] = pd.to_numeric(grouped["value"], errors="coerce").fillna(0.0)

    if chart_kind == "line":
        if chart_x != ROW_INDEX_DIMENSION:
            parsed_dates = pd.to_datetime(grouped["label"], errors="coerce", utc=True)
            if parsed_dates.notna().any():
                grouped = grouped.assign(_sort_key=parsed_dates).sort_values("_sort_key", kind="mergesort")
                grouped = grouped.drop(columns=["_sort_key"])
            else:
                grouped = grouped.sort_values("label", kind="mergesort")
        grouped = grouped.head(MAX_CHART_POINTS)
    else:
        grouped = grouped.sort_values("value", ascending=False, kind="mergesort").head(MAX_CHART_POINTS)

    max_value = float(grouped["value"].max()) if not grouped.empty else 0.0
    total_value = float(grouped["value"].sum()) if not grouped.empty else 0.0

    rows: list[dict[str, object]] = []
    for row in grouped.to_dict("records"):
        label = _safe_label(row.get("label"))
        value = float(row.get("value") or 0.0)
        rows.append(
            {
                "label": label,
                "value": value,
                "value_display": _format_chart_value(value),
                "width_pct": round((value / max_value * 100.0) if max_value > 0 else 0.0, 2),
                "share_pct": round((value / total_value * 100.0) if total_value > 0 else 0.0, 2),
            }
        )

    line_points: list[dict[str, object]] = []
    line_path = ""
    if chart_kind == "line" and rows:
        min_value = min(float(item["value"]) for item in rows)
        max_line_value = max(float(item["value"]) for item in rows)
        span = max(max_line_value - min_value, 1.0)
        point_count = len(rows)
        for index, item in enumerate(rows):
            x = 50.0 if point_count == 1 else 5.0 + (90.0 * index / (point_count - 1))
            y = 90.0 - (((float(item["value"]) - min_value) / span) * 75.0)
            line_points.append(
                {
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "label": item["label"],
                    "value_display": item["value_display"],
                }
            )
        line_path = " ".join(f"{point['x']},{point['y']}" for point in line_points)

    return {
        "rows": rows,
        "line_points": line_points,
        "line_path": line_path,
        "max_value": max_value,
        "total_value": total_value,
    }


def _chart_dimension_items(keys: list[str]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for key in keys:
        label = "Row Order" if key == ROW_INDEX_DIMENSION else key
        items.append({"key": key, "label": label})
    return items


def _chart_metric_items(keys: list[str]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for key in keys:
        label = "Row Count" if key == ROW_COUNT_METRIC else key
        items.append({"key": key, "label": label})
    return items


def _report_query_payload(
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
    cols: str,
    view_mode: str,
    chart_kind: str,
    chart_x: str,
    chart_y: str,
    run: int | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
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
        "view_mode": view_mode,
        "chart_kind": chart_kind,
        "chart_x": chart_x,
        "chart_y": chart_y,
    }
    if run is not None:
        payload["run"] = run
    return payload


def _to_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "y", "on"}


def _normalize_host(value: str) -> str:
    host = str(value or "").strip().lower()
    if not host:
        return ""
    host = host.replace("https://", "").replace("http://", "").strip("/")
    if "/" in host:
        host = host.split("/", 1)[0].strip()
    if ":" in host:
        host = host.split(":", 1)[0].strip()
    return host


def _safe_report_key(raw: str, fallback: str) -> str:
    text = re.sub(r"[^a-z0-9_-]+", "-", str(raw or "").strip().lower()).strip("-_")
    return (text or fallback)[:80]


def _resolve_external_url(raw_url: str, *, default_host: str) -> str:
    value = str(raw_url or "").strip()
    if not value:
        return ""
    if value.startswith("/"):
        host = _normalize_host(default_host)
        if not host:
            return ""
        return f"https://{host}{value}"
    parsed = urlparse(value)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        return ""
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.params, parsed.query, ""))


def _allowed_databricks_hosts(config_host: str) -> set[str]:
    hosts: list[str] = []
    if config_host:
        hosts.append(_normalize_host(config_host))
    for token in get_env(TVENDOR_DATABRICKS_REPORTS_ALLOWED_HOSTS, "").split(","):
        cleaned = _normalize_host(token)
        if cleaned:
            hosts.append(cleaned)
    return {host for host in hosts if host}


def _is_allowed_report_url(url: str, allowed_hosts: set[str]) -> bool:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme.lower() != "https":
        return False
    if not parsed.hostname:
        return False
    if not allowed_hosts:
        return True
    return _normalize_host(parsed.hostname) in allowed_hosts


def _databricks_report_options(config) -> list[dict[str, object]]:
    raw_json = get_env(TVENDOR_DATABRICKS_REPORTS_JSON, "")
    if not raw_json:
        return []
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return []

    items = payload.get("reports", []) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []

    allow_embed_default = get_env_bool(TVENDOR_DATABRICKS_REPORTS_ALLOW_EMBED, default=False)
    config_host = _normalize_host(getattr(config, "databricks_server_hostname", ""))
    allowed_hosts = _allowed_databricks_hosts(config_host)

    reports: list[dict[str, object]] = []
    seen_keys: set[str] = set()
    for index, raw_item in enumerate(items):
        item = raw_item if isinstance(raw_item, dict) else {"label": str(raw_item or ""), "url": str(raw_item or "")}
        label = str(item.get("label") or item.get("title") or item.get("name") or "").strip()
        if not label:
            label = f"Databricks Report {index + 1}"
        url_value = _resolve_external_url(str(item.get("url") or ""), default_host=config_host)
        if not url_value or not _is_allowed_report_url(url_value, allowed_hosts):
            continue

        key_seed = str(item.get("id") or label or f"dbx-report-{index + 1}")
        key = _safe_report_key(key_seed, f"dbx-report-{index + 1}")
        while key in seen_keys:
            key = _safe_report_key(f"{key}-{index + 1}", f"dbx-report-{index + 1}")
        seen_keys.add(key)

        requested_embed = item.get("allow_embed")
        allow_embed = _to_bool(requested_embed, default=allow_embed_default)
        embed_candidate = _resolve_external_url(str(item.get("embed_url") or url_value), default_host=config_host)
        can_embed = bool(allow_embed and embed_candidate and _is_allowed_report_url(embed_candidate, allowed_hosts))

        reports.append(
            {
                "key": key,
                "label": label,
                "description": str(item.get("description") or "").strip(),
                "url": url_value,
                "embed_url": embed_candidate if can_embed else "",
                "can_embed": can_embed,
            }
        )

    return reports


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


@router.post("/reports/email")
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
