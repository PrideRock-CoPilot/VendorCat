from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Request

from vendor_catalog_app.web.routers.contracts.common import (
    CONTRACT_EXPIRING_WINDOW_DAYS,
    CONTRACT_SCOPE_OPTIONS,
    CONTRACT_STATUS_FILTER_OPTIONS,
    CONTRACT_TAB_CANCELLED,
    CONTRACT_TAB_EXPIRING,
    CONTRACT_TAB_OFFERING,
    CONTRACT_TAB_OVERVIEW,
    CONTRACT_TAB_VENDOR,
    CONTRACT_TABS,
    contracts_rows_to_dict,
    contracts_url,
    normalize_limit,
    normalize_scope,
    normalize_status,
    normalize_tab,
    to_bool_series,
)
from vendor_catalog_app.web.services import (
    base_template_context,
    ensure_session_started,
    get_repo,
    get_user_context,
    log_page_view,
)


router = APIRouter(prefix="/contracts")


@router.get("")
def contracts(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Contracts Hub")

    active_tab = normalize_tab(request.query_params.get("tab"))
    search_text = str(request.query_params.get("q", "")).strip()
    selected_status = normalize_status(request.query_params.get("status"))
    selected_scope = normalize_scope(request.query_params.get("scope"))
    selected_limit = normalize_limit(request.query_params.get("limit"))

    contracts_df = repo.list_contracts_workspace(
        search_text=search_text,
        status=selected_status,
        contract_scope=selected_scope,
        limit=selected_limit,
    )

    if contracts_df.empty:
        contracts_df = pd.DataFrame(
            columns=[
                "contract_id",
                "vendor_id",
                "vendor_display_name",
                "offering_id",
                "offering_name",
                "contract_number",
                "contract_status",
                "start_date",
                "end_date",
                "cancelled_flag",
                "annual_value",
            ]
        )

    contracts_df = contracts_df.copy()
    contracts_df["contract_status"] = contracts_df.get("contract_status", "").fillna("").astype(str)
    contracts_df["contract_status_norm"] = contracts_df["contract_status"].str.strip().str.lower()
    contracts_df["cancelled_flag_bool"] = to_bool_series(contracts_df.get("cancelled_flag", pd.Series(dtype="object")))
    contracts_df["offering_id"] = contracts_df.get("offering_id", "").fillna("").astype(str).str.strip()
    contracts_df["contract_scope"] = contracts_df["offering_id"].map(lambda value: "offering" if value else "vendor")
    contracts_df["start_date_ts"] = pd.to_datetime(contracts_df.get("start_date"), errors="coerce")
    contracts_df["end_date_ts"] = pd.to_datetime(contracts_df.get("end_date"), errors="coerce")
    contracts_df["annual_value"] = pd.to_numeric(contracts_df.get("annual_value"), errors="coerce").fillna(0.0)

    cancelled_mask = contracts_df["cancelled_flag_bool"] | contracts_df["contract_status_norm"].eq("cancelled")
    vendor_scope_mask = contracts_df["contract_scope"].eq("vendor")
    offering_scope_mask = contracts_df["contract_scope"].eq("offering")

    today_ts = pd.Timestamp.now().normalize()
    expiring_cutoff_ts = today_ts + pd.Timedelta(days=CONTRACT_EXPIRING_WINDOW_DAYS)
    expiring_mask = (
        contracts_df["end_date_ts"].notna()
        & (contracts_df["end_date_ts"] >= today_ts)
        & (contracts_df["end_date_ts"] <= expiring_cutoff_ts)
        & (~cancelled_mask)
    )
    contracts_df["days_to_end"] = (contracts_df["end_date_ts"] - today_ts).dt.days

    status_for_breakdown = contracts_df["contract_status_norm"].where(~cancelled_mask, "cancelled")
    status_for_breakdown = status_for_breakdown.where(status_for_breakdown.str.len() > 0, "unknown")
    status_rows = (
        status_for_breakdown.value_counts(dropna=False).rename_axis("status").reset_index(name="count").to_dict("records")
    )

    vendor_summary_df = (
        contracts_df.groupby(["vendor_id", "vendor_display_name"], dropna=False, as_index=False)
        .agg(contract_count=("contract_id", "count"), annual_value=("annual_value", "sum"))
        .sort_values(["contract_count", "annual_value", "vendor_display_name"], ascending=[False, False, True])
        .head(15)
    )
    vendor_summary_df["annual_value"] = vendor_summary_df["annual_value"].round(2)
    vendor_summary_rows = vendor_summary_df.to_dict("records")

    offering_summary_df = (
        contracts_df[offering_scope_mask]
        .groupby(["vendor_id", "vendor_display_name", "offering_id", "offering_name"], dropna=False, as_index=False)
        .agg(contract_count=("contract_id", "count"), annual_value=("annual_value", "sum"))
        .sort_values(["contract_count", "annual_value", "offering_name"], ascending=[False, False, True])
        .head(15)
    )
    offering_summary_df["annual_value"] = offering_summary_df["annual_value"].round(2)
    offering_summary_rows = offering_summary_df.to_dict("records")

    by_end_date_df = contracts_df.sort_values(
        by=["end_date_ts", "vendor_display_name", "contract_number", "contract_id"],
        ascending=[True, True, True, True],
        na_position="last",
    )
    all_rows_df = by_end_date_df.copy()
    vendor_rows_df = by_end_date_df[vendor_scope_mask].copy()
    offering_rows_df = by_end_date_df[offering_scope_mask].copy()
    expiring_rows_df = by_end_date_df[expiring_mask].copy()
    cancelled_rows_df = by_end_date_df[cancelled_mask].copy()

    selected_rows_df = all_rows_df
    selected_tab_title = "All Contracts"
    if active_tab == CONTRACT_TAB_VENDOR:
        selected_rows_df = vendor_rows_df
        selected_tab_title = "Vendor-Level Contracts"
    elif active_tab == CONTRACT_TAB_OFFERING:
        selected_rows_df = offering_rows_df
        selected_tab_title = "Offering-Level Contracts"
    elif active_tab == CONTRACT_TAB_EXPIRING:
        selected_rows_df = expiring_rows_df
        selected_tab_title = f"Contracts Expiring In {CONTRACT_EXPIRING_WINDOW_DAYS} Days"
    elif active_tab == CONTRACT_TAB_CANCELLED:
        selected_rows_df = cancelled_rows_df
        selected_tab_title = "Cancelled Contracts"

    selected_rows = contracts_rows_to_dict(selected_rows_df)
    overview_rows = contracts_rows_to_dict(expiring_rows_df.head(25))

    cancellation_rows: list[dict[str, object]] = []
    if active_tab in {CONTRACT_TAB_OVERVIEW, CONTRACT_TAB_CANCELLED}:
        cancellation_df = repo.contract_cancellations().head(250).copy()
        if not cancellation_df.empty:
            cancellation_df["vendor_contract_url"] = cancellation_df.get("vendor_id", "").fillna("").map(
                lambda vendor_id: (
                    f"/vendors/{str(vendor_id).strip()}/contracts?return_to=%2Fcontracts"
                    if str(vendor_id).strip()
                    else ""
                )
            )
            cancellation_rows = cancellation_df.to_dict("records")

    tab_links = [
        {
            "id": tab_id,
            "label": tab_label,
            "href": contracts_url(
                tab=tab_id,
                q=search_text,
                status=selected_status,
                scope=selected_scope,
                limit=selected_limit,
            ),
            "active": tab_id == active_tab,
        }
        for tab_id, tab_label in CONTRACT_TABS
    ]

    metrics = {
        "total_contracts": int(len(contracts_df.index)),
        "active_contracts": int(
            (contracts_df["contract_status_norm"].eq("active") & (~contracts_df["cancelled_flag_bool"])).sum()
        ),
        "vendor_level_contracts": int(vendor_scope_mask.sum()),
        "offering_level_contracts": int(offering_scope_mask.sum()),
        "expiring_window_contracts": int(expiring_mask.sum()),
        "cancelled_contracts": int(cancelled_mask.sum()),
        "annual_value_total": float(round(contracts_df["annual_value"].sum(), 2)),
    }

    context = base_template_context(
        request=request,
        context=user,
        title="Contracts Hub",
        active_nav="contracts",
        extra={
            "tab_links": tab_links,
            "active_tab": active_tab,
            "tab_title": selected_tab_title,
            "search_text": search_text,
            "selected_status": selected_status,
            "selected_scope": selected_scope,
            "selected_limit": selected_limit,
            "status_options": CONTRACT_STATUS_FILTER_OPTIONS,
            "scope_options": CONTRACT_SCOPE_OPTIONS,
            "metrics": metrics,
            "status_rows": status_rows,
            "vendor_summary_rows": vendor_summary_rows,
            "offering_summary_rows": offering_summary_rows,
            "overview_rows": overview_rows,
            "selected_rows": selected_rows,
            "cancellation_rows": cancellation_rows,
            "expiring_window_days": CONTRACT_EXPIRING_WINDOW_DAYS,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "contracts.html", context)

