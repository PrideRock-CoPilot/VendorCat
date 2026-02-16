from __future__ import annotations

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
    elif report_type == "offering_budget_variance":
        frame = repo.report_offering_budget_variance(
            search_text=search,
            vendor_id=vendor,
            lifecycle_state=lifecycle_state,
            horizon_days=horizon_days,
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


# Export underscore-prefixed helper functions so modular route files can
# `from ...common import *` without changing runtime behavior.
__all__ = [name for name in globals() if not name.startswith("__")]

