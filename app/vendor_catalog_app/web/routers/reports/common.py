from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from urllib.parse import urlencode, urlparse, urlunparse

import pandas as pd
from fastapi import APIRouter

from vendor_catalog_app.core.env import (
    TVENDOR_DATABRICKS_REPORTS_ALLOW_EMBED,
    TVENDOR_DATABRICKS_REPORTS_ALLOWED_HOSTS,
    TVENDOR_DATABRICKS_REPORTS_JSON,
    get_env,
    get_env_bool,
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
    "offering_budget_variance": {
        "label": "Budget vs Actual (Invoices)",
        "description": "Offering-level estimated monthly budget compared with actual invoice run-rate and alert status.",
    },
    "vendor_warnings": {
        "label": "Vendor Warnings",
        "description": "Data-quality and operational warnings recorded against vendors for tracking and governance.",
    },
    "vendor_data_quality_overview": {
        "label": "Vendor Data Quality Overview",
        "description": "Vendor-level counts and max dates across warning, contract, demo, invoice, ticket, and data-flow tables.",
    },
    "high_risk_vendor_inventory": {
        "label": "High Risk Vendors",
        "description": "Vendor inventory narrowed to high and critical risk tiers for immediate triage.",
    },
    "active_project_portfolio": {
        "label": "Active Project Portfolio",
        "description": "Project portfolio scoped to active workstreams and current execution priorities.",
    },
    "renewal_pipeline_90d": {
        "label": "Renewal Pipeline (90 Days)",
        "description": "Contract renewal queue limited to the next 90 days for near-term planning.",
    },
    "demo_selected_only": {
        "label": "Demo Outcomes (Selected)",
        "description": "Demo outcomes filtered to selected decisions for adoption and win analysis.",
    },
    "budget_overruns": {
        "label": "Budget Overruns",
        "description": "Offering budget variance records with over-budget status to target corrective action.",
    },
    "open_vendor_warnings": {
        "label": "Open Vendor Warnings",
        "description": "Operational and data-quality warnings currently in open status.",
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
    "offering_budget_variance": {"kind": "bar", "x": "offering_name", "y": "variance_amount"},
    "vendor_warnings": {"kind": "bar", "x": "warning_category", "y": ROW_COUNT_METRIC},
    "vendor_data_quality_overview": {"kind": "bar", "x": "vendor_display_name", "y": "open_warning_count"},
    "high_risk_vendor_inventory": {"kind": "bar", "x": "display_name", "y": "total_contract_value"},
    "active_project_portfolio": {"kind": "bar", "x": "project_name", "y": ROW_COUNT_METRIC},
    "renewal_pipeline_90d": {"kind": "line", "x": "renewal_date", "y": "annual_value"},
    "demo_selected_only": {"kind": "bar", "x": "vendor_display_name", "y": "overall_score"},
    "budget_overruns": {"kind": "bar", "x": "offering_name", "y": "variance_amount"},
    "open_vendor_warnings": {"kind": "bar", "x": "severity", "y": ROW_COUNT_METRIC},
}

DATABRICKS_SELECTED_REPORT_PARAM = "dbx_report"
REPORTS_WORKSPACE_SETTING_KEY = "reports_workspace_boards_v1"
REPORTS_WORKSPACE_VERSION = 1
MAX_WORKSPACE_BOARDS = 40
MAX_WORKSPACE_WIDGETS = 40
MAX_WORKSPACE_NAME_LEN = 120
MAX_WORKSPACE_SEARCH_LEN = 160


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
    lob: str,
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
            org_id=lob,
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
    elif report_type == "offering_budget_variance":
        frame = repo.report_offering_budget_variance(
            search_text=search,
            vendor_id=vendor,
            lifecycle_state=lifecycle_state,
            horizon_days=horizon_days,
            limit=limit,
        )
    elif report_type == "vendor_warnings":
        frame = repo.report_vendor_warnings(
            search_text=search,
            vendor_id=vendor,
            lifecycle_state=lifecycle_state,
            limit=limit,
        )
    elif report_type == "vendor_data_quality_overview":
        frame = repo.report_vendor_data_quality_overview(
            search_text=search,
            vendor_id=vendor,
            lifecycle_state=lifecycle_state,
            limit=limit,
        )
    elif report_type == "high_risk_vendor_inventory":
        frame = repo.report_vendor_inventory(
            search_text=search,
            lifecycle_state=lifecycle_state,
            owner_principal=owner_principal,
            limit=limit,
        )
        if not frame.empty and "risk_tier" in frame.columns:
            risk = frame["risk_tier"].astype(str).str.strip().str.lower()
            frame = frame[risk.isin({"high", "critical"})].copy()
    elif report_type == "active_project_portfolio":
        frame = repo.report_project_portfolio(
            search_text=search,
            status="active",
            vendor_id=vendor,
            owner_principal=owner_principal,
            limit=limit,
        )
    elif report_type == "renewal_pipeline_90d":
        frame = repo.report_contract_renewals(
            search_text=search,
            vendor_id=vendor,
            org_id=lob,
            horizon_days=90,
            limit=limit,
        )
    elif report_type == "demo_selected_only":
        frame = repo.report_demo_outcomes(
            search_text=search,
            vendor_id=vendor,
            outcome="selected",
            limit=limit,
        )
    elif report_type == "budget_overruns":
        frame = repo.report_offering_budget_variance(
            search_text=search,
            vendor_id=vendor,
            lifecycle_state=lifecycle_state,
            horizon_days=horizon_days,
            limit=limit,
        )
        if not frame.empty and "alert_status" in frame.columns:
            status = frame["alert_status"].astype(str).str.strip().str.lower()
            frame = frame[status == "over_budget"].copy()
    elif report_type == "open_vendor_warnings":
        frame = repo.report_vendor_warnings(
            search_text=search,
            vendor_id=vendor,
            lifecycle_state=lifecycle_state,
            limit=limit,
        )
        if not frame.empty and "warning_status" in frame.columns:
            status = frame["warning_status"].astype(str).str.strip().str.lower()
            frame = frame[status == "open"].copy()
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
    lob: str,
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
        "lob": lob,
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


def _workspace_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workspace_default_widget(
    *,
    report_type: str = "vendor_inventory",
    widget_type: str = "chart",
    index: int = 0,
) -> dict[str, object]:
    clean_report_type = _safe_report_type(report_type)
    clean_widget_type = str(widget_type or "chart").strip().lower()
    if clean_widget_type not in {"chart", "table", "kpi"}:
        clean_widget_type = "chart"
    preset = CHART_PRESETS.get(clean_report_type, {})
    label = str(REPORT_TYPES.get(clean_report_type, {}).get("label") or "Report")
    view_mode = "table" if clean_widget_type == "table" else "chart"
    title = f"{label} KPI" if clean_widget_type == "kpi" else label
    return {
        "id": _safe_report_key(f"{clean_report_type}-{index + 1}", f"widget-{index + 1}"),
        "widget_type": clean_widget_type,
        "title": title[:MAX_WORKSPACE_NAME_LEN],
        "report_type": clean_report_type,
        "view_mode": view_mode,
        "chart_kind": _safe_chart_kind(str(preset.get("kind") or "bar")),
        "chart_x": str(preset.get("x") or ROW_INDEX_DIMENSION),
        "chart_y": str(preset.get("y") or ROW_COUNT_METRIC),
        "search": "",
        "vendor": "all",
        "limit": 500,
    }


def _workspace_normalize_widget(widget: object, index: int) -> dict[str, object]:
    base = _workspace_default_widget(index=index)
    if not isinstance(widget, dict):
        return base

    widget_type = str(widget.get("widget_type") or widget.get("type") or base["widget_type"]).strip().lower()
    if widget_type not in {"chart", "table", "kpi"}:
        widget_type = str(base["widget_type"])
    report_type = _safe_report_type(str(widget.get("report_type") or base["report_type"]))
    preset = CHART_PRESETS.get(report_type, {})

    title = str(widget.get("title") or "").strip()
    if not title:
        label = str(REPORT_TYPES.get(report_type, {}).get("label") or report_type)
        title = f"{label} KPI" if widget_type == "kpi" else label

    view_mode = _safe_view_mode(str(widget.get("view_mode") or ("table" if widget_type == "table" else "chart")))
    chart_kind = _safe_chart_kind(str(widget.get("chart_kind") or preset.get("kind") or "bar"))
    chart_x = str(widget.get("chart_x") or preset.get("x") or ROW_INDEX_DIMENSION).strip() or ROW_INDEX_DIMENSION
    chart_y = str(widget.get("chart_y") or preset.get("y") or ROW_COUNT_METRIC).strip() or ROW_COUNT_METRIC

    try:
        limit = int(widget.get("limit", 500))
    except (TypeError, ValueError):
        limit = 500
    if limit not in ROW_LIMITS:
        limit = 500

    widget_id_seed = str(widget.get("id") or widget.get("widget_id") or f"{report_type}-{index + 1}")
    widget_id = _safe_report_key(widget_id_seed, f"widget-{index + 1}")
    if not widget_id:
        widget_id = f"widget-{index + 1}"

    return {
        "id": widget_id,
        "widget_type": widget_type,
        "title": title[:MAX_WORKSPACE_NAME_LEN],
        "report_type": report_type,
        "view_mode": view_mode,
        "chart_kind": chart_kind,
        "chart_x": chart_x,
        "chart_y": chart_y,
        "search": str(widget.get("search") or "").strip()[:MAX_WORKSPACE_SEARCH_LEN],
        "vendor": str(widget.get("vendor") or "all").strip() or "all",
        "limit": limit,
    }


def _workspace_normalize_widgets(raw_widgets: object) -> list[dict[str, object]]:
    if not isinstance(raw_widgets, list):
        return []
    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for index, raw_widget in enumerate(raw_widgets[:MAX_WORKSPACE_WIDGETS]):
        item = _workspace_normalize_widget(raw_widget, index)
        candidate_id = str(item.get("id") or "").strip() or f"widget-{index + 1}"
        unique_id = candidate_id
        suffix = 2
        while unique_id in seen_ids:
            unique_id = _safe_report_key(f"{candidate_id}-{suffix}", f"widget-{index + 1}-{suffix}") or f"widget-{index + 1}-{suffix}"
            suffix += 1
        item["id"] = unique_id
        seen_ids.add(unique_id)
        normalized.append(item)
    return normalized


def _workspace_normalize_board(raw_board: object, index: int) -> dict[str, object] | None:
    if not isinstance(raw_board, dict):
        return None
    board_name = str(raw_board.get("board_name") or raw_board.get("name") or "").strip()
    if not board_name:
        board_name = f"Report Board {index + 1}"
    board_name = board_name[:MAX_WORKSPACE_NAME_LEN]
    board_id_seed = str(raw_board.get("board_id") or raw_board.get("id") or board_name).strip()
    board_id = _safe_report_key(board_id_seed, f"board-{index + 1}") or f"board-{index + 1}"
    widgets = _workspace_normalize_widgets(raw_board.get("widgets"))
    if not widgets:
        return None
    created_at = str(raw_board.get("created_at") or "").strip() or _workspace_now_iso()
    updated_at = str(raw_board.get("updated_at") or "").strip() or created_at
    return {
        "board_id": board_id,
        "board_name": board_name,
        "widgets": widgets,
        "widget_count": len(widgets),
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _workspace_load_boards(repo, user_principal: str) -> list[dict[str, object]]:
    raw_payload = repo.get_user_setting(user_principal, REPORTS_WORKSPACE_SETTING_KEY)
    raw_boards = raw_payload.get("boards", []) if isinstance(raw_payload, dict) else []
    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for index, raw_board in enumerate(raw_boards):
        board = _workspace_normalize_board(raw_board, index)
        if board is None:
            continue
        board_id = str(board.get("board_id") or "")
        if board_id in seen_ids:
            dedupe_index = 2
            candidate = board_id
            while candidate in seen_ids:
                candidate = (
                    _safe_report_key(f"{board_id}-{dedupe_index}", f"board-{index + 1}-{dedupe_index}")
                    or f"board-{index + 1}-{dedupe_index}"
                )
                dedupe_index += 1
            board["board_id"] = candidate
            board_id = candidate
        seen_ids.add(board_id)
        normalized.append(board)
    normalized.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return normalized[:MAX_WORKSPACE_BOARDS]


def _workspace_store_boards(repo, user_principal: str, boards: list[dict[str, object]]) -> None:
    payload = {
        "version": REPORTS_WORKSPACE_VERSION,
        "boards": boards[:MAX_WORKSPACE_BOARDS],
    }
    repo.save_user_setting(user_principal, REPORTS_WORKSPACE_SETTING_KEY, payload)


def _workspace_upsert_board(
    repo,
    *,
    user_principal: str,
    board_name: str,
    board_json: str,
    board_id: str = "",
) -> dict[str, object]:
    if not str(board_json or "").strip():
        raise ValueError("Board JSON is required.")

    try:
        parsed = json.loads(str(board_json))
    except json.JSONDecodeError as exc:
        raise ValueError("Board JSON is invalid.") from exc

    if isinstance(parsed, list):
        raw_widgets = parsed
    elif isinstance(parsed, dict):
        raw_widgets = parsed.get("widgets", [])
    else:
        raise ValueError("Board JSON must be an object with widgets or a widget array.")

    widgets = _workspace_normalize_widgets(raw_widgets)
    if not widgets:
        raise ValueError("Board must include at least one widget.")

    clean_name = str(board_name or "").strip()[:MAX_WORKSPACE_NAME_LEN]
    if not clean_name and isinstance(parsed, dict):
        clean_name = str(parsed.get("board_name") or parsed.get("name") or "").strip()[:MAX_WORKSPACE_NAME_LEN]
    if not clean_name:
        clean_name = "Report Board"

    boards = _workspace_load_boards(repo, user_principal)
    now = _workspace_now_iso()
    target_id = _safe_report_key(str(board_id or "").strip(), "") if board_id else ""
    if not target_id:
        target_id = _safe_report_key(clean_name, f"board-{len(boards) + 1}") or f"board-{len(boards) + 1}"

    existing_index = -1
    for idx, item in enumerate(boards):
        if str(item.get("board_id") or "") == target_id:
            existing_index = idx
            break

    if existing_index < 0:
        if len(boards) >= MAX_WORKSPACE_BOARDS:
            raise ValueError(f"Workspace supports up to {MAX_WORKSPACE_BOARDS} saved boards.")
        used_ids = {str(item.get("board_id") or "") for item in boards}
        candidate = target_id
        suffix = 2
        while candidate in used_ids:
            candidate = _safe_report_key(f"{target_id}-{suffix}", f"board-{len(boards) + 1}-{suffix}") or f"board-{len(boards) + 1}-{suffix}"
            suffix += 1
        target_id = candidate
        board = {
            "board_id": target_id,
            "board_name": clean_name,
            "widgets": widgets,
            "widget_count": len(widgets),
            "created_at": now,
            "updated_at": now,
        }
        boards.insert(0, board)
    else:
        existing = dict(boards[existing_index])
        board = {
            "board_id": target_id,
            "board_name": clean_name,
            "widgets": widgets,
            "widget_count": len(widgets),
            "created_at": str(existing.get("created_at") or now),
            "updated_at": now,
        }
        boards[existing_index] = board

    _workspace_store_boards(repo, user_principal, boards)
    return board


def _workspace_delete_board(repo, *, user_principal: str, board_id: str) -> bool:
    target_id = _safe_report_key(str(board_id or "").strip(), "")
    if not target_id:
        return False
    boards = _workspace_load_boards(repo, user_principal)
    remaining = [item for item in boards if str(item.get("board_id") or "") != target_id]
    if len(remaining) == len(boards):
        return False
    _workspace_store_boards(repo, user_principal, remaining)
    return True


def _workspace_widget_query_payload(widget: dict[str, object]) -> dict[str, object]:
    clean_widget = _workspace_normalize_widget(widget, index=0)
    report_type = _safe_report_type(str(clean_widget.get("report_type") or "vendor_inventory"))
    vendor = str(clean_widget.get("vendor") or "all").strip() or "all"
    search = str(clean_widget.get("search") or "").strip()[:MAX_WORKSPACE_SEARCH_LEN]
    try:
        limit = int(clean_widget.get("limit", 500))
    except (TypeError, ValueError):
        limit = 500
    if limit not in ROW_LIMITS:
        limit = 500

    view_mode = _safe_view_mode(str(clean_widget.get("view_mode") or "both"))
    chart_kind = _safe_chart_kind(str(clean_widget.get("chart_kind") or "bar"))
    chart_x = str(clean_widget.get("chart_x") or "").strip()
    chart_y = str(clean_widget.get("chart_y") or "").strip()
    preset = CHART_PRESETS.get(report_type, {})
    selected_chart_x = chart_x or str(preset.get("x") or ROW_INDEX_DIMENSION)
    selected_chart_y = chart_y or str(preset.get("y") or ROW_COUNT_METRIC)

    payload = _report_query_payload(
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
        cols="",
        view_mode=view_mode,
        chart_kind=chart_kind,
        chart_x=selected_chart_x,
        chart_y=selected_chart_y,
        run=1,
    )
    return payload


# Export underscore-prefixed helper functions so modular route files can
# `from ...common import *` without changing runtime behavior.
__all__ = [name for name in globals() if not name.startswith("__")]

