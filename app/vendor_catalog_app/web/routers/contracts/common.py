from __future__ import annotations

from urllib.parse import urlencode

import pandas as pd

from vendor_catalog_app.web.routers.vendors.constants import CONTRACT_STATUS_OPTIONS


CONTRACT_TAB_OVERVIEW = "overview"
CONTRACT_TAB_ALL = "all"
CONTRACT_TAB_VENDOR = "vendor"
CONTRACT_TAB_OFFERING = "offering"
CONTRACT_TAB_EXPIRING = "expiring"
CONTRACT_TAB_CANCELLED = "cancelled"

CONTRACT_TABS = [
    (CONTRACT_TAB_OVERVIEW, "Overview"),
    (CONTRACT_TAB_ALL, "All Contracts"),
    (CONTRACT_TAB_VENDOR, "Vendor-Level"),
    (CONTRACT_TAB_OFFERING, "Offering-Level"),
    (CONTRACT_TAB_EXPIRING, "Expiring Soon"),
    (CONTRACT_TAB_CANCELLED, "Cancelled"),
]
CONTRACT_SCOPE_OPTIONS = ["all", "vendor", "offering"]
CONTRACT_STATUS_FILTER_OPTIONS = ["all", *CONTRACT_STATUS_OPTIONS, "cancelled"]
CONTRACT_EXPIRING_WINDOW_DAYS = 90
CONTRACT_PAGE_SIZES = [25, 50, 100, 250]
DEFAULT_CONTRACT_PAGE_SIZE = 50


def normalize_tab(raw_value: str | None) -> str:
    value = str(raw_value or "").strip().lower()
    allowed = {tab_id for tab_id, _ in CONTRACT_TABS}
    return value if value in allowed else CONTRACT_TAB_OVERVIEW


def normalize_status(raw_value: str | None) -> str:
    value = str(raw_value or "").strip().lower()
    return value if value in set(CONTRACT_STATUS_FILTER_OPTIONS) else "all"


def normalize_scope(raw_value: str | None) -> str:
    value = str(raw_value or "").strip().lower()
    return value if value in set(CONTRACT_SCOPE_OPTIONS) else "all"


def normalize_limit(raw_value: str | None) -> int:
    try:
        value = int(str(raw_value or "").strip() or "500")
    except Exception:
        return 500
    return max(25, min(value, 5000))


def normalize_page_size(raw_value: str | None) -> int:
    try:
        value = int(str(raw_value or "").strip() or str(DEFAULT_CONTRACT_PAGE_SIZE))
    except Exception:
        return DEFAULT_CONTRACT_PAGE_SIZE
    return max(1, min(value, 250))


def normalize_page(raw_value: str | None) -> int:
    try:
        value = int(str(raw_value or "").strip() or "1")
    except Exception:
        return 1
    return max(1, value)


def to_bool_series(series: pd.Series) -> pd.Series:
    normalized = series.astype(str).str.strip().str.lower()
    return normalized.isin({"1", "true", "t", "yes", "y"})


def contracts_url(
    *,
    tab: str,
    q: str,
    status: str,
    scope: str,
    page: int,
    page_size: int,
) -> str:
    query = {
        "tab": tab,
        "q": q,
        "status": status,
        "scope": scope,
        "page": str(page),
        "page_size": str(page_size),
    }
    return f"/contracts?{urlencode(query)}"


def contracts_rows_to_dict(rows: pd.DataFrame) -> list[dict[str, object]]:
    if rows.empty:
        return []
    out = rows.copy()
    out["contract_number"] = out.get("contract_number", "").fillna("")
    out["contract_status"] = out.get("contract_status", "").fillna("")
    out["vendor_display_name"] = out.get("vendor_display_name", "").fillna(out.get("vendor_id", ""))
    out["offering_name"] = out.get("offering_name", "").fillna("Unassigned")
    out["contract_scope"] = out.get("contract_scope", "").fillna("vendor")
    out["annual_value"] = pd.to_numeric(out.get("annual_value"), errors="coerce").fillna(0.0).round(2)
    out["start_date"] = out.get("start_date", "").fillna("").astype(str)
    out["end_date"] = out.get("end_date", "").fillna("").astype(str)
    out["days_to_end"] = pd.to_numeric(out.get("days_to_end"), errors="coerce").round(0)
    out["days_to_end"] = out["days_to_end"].where(out["days_to_end"].notna(), None)
    out["vendor_contract_url"] = out.get("vendor_id", "").fillna("").map(
        lambda vendor_id: (
            f"/vendors/{str(vendor_id).strip()}/contracts?return_to=%2Fcontracts"
            if str(vendor_id).strip()
            else ""
        )
    )
    return out.to_dict("records")
