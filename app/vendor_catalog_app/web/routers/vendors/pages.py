from __future__ import annotations

from urllib.parse import urlencode

import pandas as pd

from vendor_catalog_app.core.defaults import (
    DEFAULT_OFFERING_ALERT_THRESHOLD_PCT,
    DEFAULT_OFFERING_INVOICE_WINDOW_MONTHS,
)
from vendor_catalog_app.web.routers.vendors.constants import (
    DEFAULT_VENDOR_FIELDS,
    DEFAULT_VENDOR_PAGE_SIZE,
    DEFAULT_VENDOR_SORT_BY,
    LIFECYCLE_STATES,
    OFFERING_LOB_FALLBACK,
    OFFERING_SERVICE_TYPE_FALLBACK,
    OFFERING_TYPES_FALLBACK,
    VENDOR_PAGE_SIZES,
    VENDOR_SETTINGS_KEY,
    VENDOR_SORT_FIELDS,
)


def _normalize_lifecycle(value: str) -> str:
    lifecycle = value.strip().lower()
    if lifecycle not in LIFECYCLE_STATES:
        raise ValueError(f"Lifecycle state must be one of: {', '.join(LIFECYCLE_STATES)}")
    return lifecycle


def _offering_type_options(repo) -> list[str]:
    options = [str(item).strip() for item in repo.list_offering_type_options() if str(item).strip()]
    return options or list(OFFERING_TYPES_FALLBACK)


def _offering_lob_options(repo) -> list[str]:
    options = [str(item).strip() for item in repo.list_offering_lob_options() if str(item).strip()]
    return options or list(OFFERING_LOB_FALLBACK)


def _offering_service_type_options(repo) -> list[str]:
    options = [str(item).strip() for item in repo.list_offering_service_type_options() if str(item).strip()]
    return options or list(OFFERING_SERVICE_TYPE_FALLBACK)


def _normalize_offering_type(repo, value: str, *, allow_blank: bool = True, extra_allowed: set[str] | None = None) -> str:
    allowed = _offering_type_options(repo)
    offering_type = (value or "").strip()
    if not offering_type:
        return "" if allow_blank else allowed[0]
    canonical_by_lower = {item.lower(): item for item in allowed}
    canonical = canonical_by_lower.get(offering_type.lower())
    if canonical:
        return canonical
    if extra_allowed and offering_type in extra_allowed:
        return offering_type
    raise ValueError(f"Offering type must be one of: {', '.join(allowed)}")


def _normalize_offering_lob(repo, value: str, *, allow_blank: bool = True, extra_allowed: set[str] | None = None) -> str:
    allowed = _offering_lob_options(repo)
    lob = (value or "").strip()
    if not lob:
        return "" if allow_blank else allowed[0]
    canonical_by_lower = {item.lower(): item for item in allowed}
    canonical = canonical_by_lower.get(lob.lower())
    if canonical:
        return canonical
    if extra_allowed and lob in extra_allowed:
        return lob
    raise ValueError(f"LOB must be one of: {', '.join(allowed)}")


def _normalize_offering_service_type(
    repo,
    value: str,
    *,
    allow_blank: bool = True,
    extra_allowed: set[str] | None = None,
) -> str:
    allowed = _offering_service_type_options(repo)
    service_type = (value or "").strip()
    if not service_type:
        return "" if allow_blank else allowed[0]
    canonical_by_lower = {item.lower(): item for item in allowed}
    canonical = canonical_by_lower.get(service_type.lower())
    if canonical:
        return canonical
    if extra_allowed and service_type in extra_allowed:
        return service_type
    raise ValueError(f"Service type must be one of: {', '.join(allowed)}")


def _load_visible_fields(repo, user_principal: str, available_fields: list[str]) -> list[str]:
    saved = repo.get_user_setting(user_principal, VENDOR_SETTINGS_KEY)
    saved_fields = saved.get("visible_fields") if isinstance(saved, dict) else None
    if not isinstance(saved_fields, list) or not saved_fields:
        saved_fields = DEFAULT_VENDOR_FIELDS
    visible = [field for field in saved_fields if field in available_fields]
    return visible or available_fields


def _merge_vendor360_settings(repo, user_principal: str, updates: dict) -> dict:
    saved = repo.get_user_setting(user_principal, VENDOR_SETTINGS_KEY)
    merged = dict(saved) if isinstance(saved, dict) else {}
    merged.update(updates)
    repo.save_user_setting(user_principal=user_principal, setting_key=VENDOR_SETTINGS_KEY, setting_value=merged)
    return merged


def _normalize_vendor_sort(sort_by: str, sort_dir: str) -> tuple[str, str]:
    normalized_sort_by = (sort_by or DEFAULT_VENDOR_SORT_BY).strip().lower()
    if normalized_sort_by not in VENDOR_SORT_FIELDS:
        normalized_sort_by = DEFAULT_VENDOR_SORT_BY
    normalized_sort_dir = "desc" if (sort_dir or "").strip().lower() == "desc" else "asc"
    return normalized_sort_by, normalized_sort_dir


def _normalize_vendor_page(page: int, page_size: int) -> tuple[int, int]:
    normalized_page_size = page_size if page_size in VENDOR_PAGE_SIZES else DEFAULT_VENDOR_PAGE_SIZE
    normalized_page = max(1, int(page or 1))
    return normalized_page, normalized_page_size


def _vendor_list_url(
    *,
    q: str,
    status: str,
    owner: str,
    risk: str,
    group: str,
    include_merged: int,
    page: int,
    page_size: int,
    sort_by: str,
    sort_dir: str,
    show_settings: int,
) -> str:
    return "/vendors?" + urlencode(
        {
            "q": q,
            "status": status,
            "owner": owner,
            "risk": risk,
            "group": group,
            "include_merged": 1 if int(include_merged or 0) else 0,
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
            "show_settings": show_settings,
        }
    )


def _series_with_bar_pct(rows: list[dict], value_key: str) -> list[dict]:
    if not rows:
        return rows
    max_value = max(float(row.get(value_key, 0) or 0) for row in rows)
    for row in rows:
        value = float(row.get(value_key, 0) or 0)
        row["bar_pct"] = int((value / max_value) * 100) if max_value > 0 else 0
    return rows


def _build_line_chart_points(
    rows: list[dict], x_key: str, y_key: str, width: int = 560, height: int = 180, pad: int = 20
) -> tuple[str, list[dict]]:
    if not rows:
        return "", rows
    cleaned = [{"x": str(row.get(x_key, "")), "y": float(row.get(y_key, 0) or 0)} for row in rows]
    if len(cleaned) == 1:
        cleaned = cleaned + [dict(cleaned[0])]

    values = [item["y"] for item in cleaned]
    min_v = min(values)
    max_v = max(values)
    span = max(max_v - min_v, 1.0)
    points = []
    n = len(cleaned)
    for idx, item in enumerate(cleaned):
        x = pad + ((width - (pad * 2)) * (idx / (n - 1)))
        y = height - pad - ((height - (pad * 2)) * ((item["y"] - min_v) / span))
        points.append(f"{x:.1f},{y:.1f}")
        item["plot_x"] = x
        item["plot_y"] = y
    return " ".join(points), cleaned


def _offering_invoice_summary(
    offering_profile: dict[str, object] | None,
    invoice_rows: list[dict[str, object]],
    *,
    window_months: int = DEFAULT_OFFERING_INVOICE_WINDOW_MONTHS,
    alert_threshold_pct: float = DEFAULT_OFFERING_ALERT_THRESHOLD_PCT,
) -> dict[str, object]:
    months = max(1, min(int(window_months or DEFAULT_OFFERING_INVOICE_WINDOW_MONTHS), 12))
    estimated_value: float | None = None
    try:
        raw_estimated = (offering_profile or {}).get("estimated_monthly_cost")
        if raw_estimated not in (None, ""):
            estimated_value = float(raw_estimated)
    except Exception:
        estimated_value = None

    if not invoice_rows:
        return {
            "window_months": months,
            "invoice_count_total": 0,
            "invoice_count_window": 0,
            "total_actual_all_time": 0.0,
            "total_actual_window": 0.0,
            "actual_monthly_avg": 0.0,
            "estimated_monthly_cost": estimated_value,
            "variance_amount": None,
            "variance_pct": None,
            "status": "no_actuals" if estimated_value not in (None, 0.0) else "no_estimate",
            "alert_flag": False,
            "alert_message": "",
            "last_invoice_date": "",
        }

    frame = pd.DataFrame(invoice_rows)
    if "amount" not in frame.columns:
        frame["amount"] = 0.0
    if "invoice_date" not in frame.columns:
        frame["invoice_date"] = None
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce").fillna(0.0)
    frame["invoice_date"] = pd.to_datetime(frame["invoice_date"], errors="coerce")
    frame = frame[frame["invoice_date"].notna()].copy()
    if frame.empty:
        return {
            "window_months": months,
            "invoice_count_total": int(len(invoice_rows)),
            "invoice_count_window": 0,
            "total_actual_all_time": 0.0,
            "total_actual_window": 0.0,
            "actual_monthly_avg": 0.0,
            "estimated_monthly_cost": estimated_value,
            "variance_amount": None,
            "variance_pct": None,
            "status": "no_actuals" if estimated_value not in (None, 0.0) else "no_estimate",
            "alert_flag": False,
            "alert_message": "",
            "last_invoice_date": "",
        }

    total_actual_all_time = float(frame["amount"].sum())
    invoice_count_total = int(len(frame))
    now_ts = pd.Timestamp.utcnow()
    if now_ts.tzinfo is not None:
        now_ts = now_ts.tz_localize(None)
    cutoff_month_start = (now_ts.to_period("M") - (months - 1)).to_timestamp()
    window = frame[frame["invoice_date"] >= cutoff_month_start].copy()
    total_actual_window = float(window["amount"].sum()) if not window.empty else 0.0
    invoice_count_window = int(len(window))
    actual_monthly_avg = total_actual_window / float(months)
    last_invoice_date = ""
    if not frame.empty:
        last_invoice_date = str(frame["invoice_date"].max().date())

    variance_amount: float | None = None
    variance_pct: float | None = None
    status = "no_estimate"
    alert_flag = False
    alert_message = ""
    if estimated_value is not None and estimated_value > 0:
        if invoice_count_window == 0:
            status = "no_actuals"
        else:
            variance_amount = actual_monthly_avg - estimated_value
            variance_pct = (variance_amount / estimated_value) * 100.0
            if variance_pct >= alert_threshold_pct:
                status = "over_budget"
                alert_flag = True
                alert_message = (
                    f"Actual monthly run-rate is {variance_pct:.1f}% above estimate over the last {months} month(s)."
                )
            elif variance_pct <= (0.0 - alert_threshold_pct):
                status = "under_budget"
            else:
                status = "on_track"

    return {
        "window_months": months,
        "invoice_count_total": invoice_count_total,
        "invoice_count_window": invoice_count_window,
        "total_actual_all_time": total_actual_all_time,
        "total_actual_window": total_actual_window,
        "actual_monthly_avg": actual_monthly_avg,
        "estimated_monthly_cost": estimated_value,
        "variance_amount": variance_amount,
        "variance_pct": variance_pct,
        "status": status,
        "alert_flag": alert_flag,
        "alert_message": alert_message,
        "last_invoice_date": last_invoice_date,
    }



