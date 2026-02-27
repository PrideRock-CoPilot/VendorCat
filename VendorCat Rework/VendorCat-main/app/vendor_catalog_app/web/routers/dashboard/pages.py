from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.routers.dashboard.common import (
    DEFAULT_DASHBOARD_HORIZON_DAYS,
    DEFAULT_DASHBOARD_MONTHS,
    clamp_horizon_days,
    clamp_months,
    has_seen_startup_splash_for_current_run,
    render_startup_splash,
)

router = APIRouter()


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_executive_alerts(
    *,
    summary: object,
    top_vendors: list[dict[str, object]],
    renewals: list[dict[str, object]],
    recent_cancellations: list[dict[str, object]],
    horizon_days: int,
) -> list[dict[str, object]]:
    alerts: list[dict[str, object]] = []

    high_risk_count = int(_as_float(getattr(summary, "high_risk_vendors", 0)))
    if high_risk_count > 0:
        highest_spend_vendor = top_vendors[0] if top_vendors else None
        vendor_name = ""
        vendor_spend = 0.0
        if highest_spend_vendor:
            vendor_name = str(
                highest_spend_vendor.get("vendor_name")
                or highest_spend_vendor.get("vendor_id")
                or ""
            )
            vendor_spend = _as_float(highest_spend_vendor.get("total_spend"), 0.0)
        detail = (
            f"{high_risk_count} high/critical risk vendors"
            + (f" · top spend: {vendor_name} (${vendor_spend:,.0f})" if vendor_name else "")
        )
        alerts.append(
            {
                "tone": "danger",
                "title": "High-Risk Exposure",
                "detail": detail,
                "href": "/vendor-360?risk=high",
                "action": "Review Risk",
            }
        )

    near_term_rows = [
        row
        for row in renewals
        if _as_float(row.get("days_to_renewal"), 9999) <= min(horizon_days, 60)
    ]
    if near_term_rows:
        near_term_value = sum(_as_float(row.get("annual_value"), 0.0) for row in near_term_rows)
        alerts.append(
            {
                "tone": "warning",
                "title": "Upcoming Renewals",
                "detail": f"{len(near_term_rows)} renewals in next 60 days (${near_term_value:,.0f})",
                "href": "/contracts",
                "action": "View Renewals",
            }
        )

    not_selected_rate = _as_float(getattr(summary, "not_selected_demo_rate", 0.0), 0.0)
    if not_selected_rate >= 0.2:
        alerts.append(
            {
                "tone": "warning",
                "title": "Demo Conversion Risk",
                "detail": f"Not-selected demo rate is {not_selected_rate * 100:.1f}%",
                "href": "/demos",
                "action": "Review Demos",
            }
        )

    if recent_cancellations:
        latest = recent_cancellations[0]
        contract_id = str(latest.get("contract_id") or "Unknown")
        reason = str(latest.get("reason_code") or "Unspecified")
        alerts.append(
            {
                "tone": "danger",
                "title": "Recent Cancellation",
                "detail": f"Contract {contract_id} cancelled · reason: {reason}",
                "href": "/contracts",
                "action": "Review Contracts",
            }
        )

    if not alerts:
        alerts.append(
            {
                "tone": "ok",
                "title": "No Immediate Alerts",
                "detail": "No high-risk, near-term renewal, or cancellation flags in current filters.",
                "href": "/reports",
                "action": "Open Reports",
            }
        )

    return alerts[:4]


def _dashboard_module():
    # Resolve through package namespace so tests can monkeypatch dashboard.get_user_context.
    from vendor_catalog_app.web.routers import dashboard as dashboard_module

    return dashboard_module


@router.get("/dashboard")
def dashboard(
    request: Request,
    business_unit: str = "all",
    org: str | None = None,
    months: int = DEFAULT_DASHBOARD_MONTHS,
    horizon_days: int = DEFAULT_DASHBOARD_HORIZON_DAYS,
):
    dashboard_module = _dashboard_module()
    user = dashboard_module.get_user_context(request)
    if not set(getattr(user, "roles", set()) or set()):
        return RedirectResponse(url="/access/request", status_code=303)
    if not has_seen_startup_splash_for_current_run(request):
        passthrough_params = dict(request.query_params)
        passthrough_params["splash"] = "1"
        redirect_query = urlencode(passthrough_params, doseq=True)
        redirect_url = f"/dashboard?{redirect_query}" if redirect_query else "/dashboard"
        return render_startup_splash(request, redirect_url)

    repo = dashboard_module.get_repo()
    dashboard_module.ensure_session_started(request, user)
    dashboard_module.log_page_view(request, user, "Dashboard")

    orgs = repo.available_orgs()
    selected_business_unit = str(org if org is not None and str(org).strip() else business_unit).strip() or "all"
    if selected_business_unit not in orgs:
        selected_business_unit = "all"
    months = clamp_months(months)
    horizon_days = clamp_horizon_days(horizon_days)

    kpis = repo.dashboard_kpis()
    summary = repo.executive_summary(org_id=selected_business_unit, months=months, horizon_days=horizon_days)
    by_category_df = repo.executive_spend_by_category(org_id=selected_business_unit, months=months)
    trend_df = repo.executive_monthly_spend_trend(org_id=selected_business_unit, months=months)
    top_vendors_df = repo.executive_top_vendors_by_spend(org_id=selected_business_unit, months=months, limit=10)
    risk_dist_df = repo.executive_risk_distribution(org_id=selected_business_unit)
    renewals_df = repo.executive_renewal_pipeline(org_id=selected_business_unit, horizon_days=horizon_days)
    recent_demos_df = repo.demo_outcomes().head(10)
    recent_cancellations_df = repo.contract_cancellations().head(10)

    by_category = by_category_df.to_dict("records")
    trend = trend_df.to_dict("records")
    top_vendors = top_vendors_df.to_dict("records")
    risk_dist = risk_dist_df.to_dict("records")
    renewals = renewals_df.to_dict("records")
    recent_demos = recent_demos_df.to_dict("records")
    recent_cancellations = recent_cancellations_df.to_dict("records")

    trend_max = max((_as_float(row.get("total_spend"), 0.0) for row in trend), default=0.0)
    category_max = max((_as_float(row.get("total_spend"), 0.0) for row in by_category), default=0.0)
    risk_total = sum(_as_float(row.get("vendor_count"), 0.0) for row in risk_dist)
    renewals_30_count = sum(1 for row in renewals if _as_float(row.get("days_to_renewal"), 9999) <= 30)
    renewals_60_count = sum(1 for row in renewals if _as_float(row.get("days_to_renewal"), 9999) <= 60)
    renewals_30_value = sum(
        _as_float(row.get("annual_value"), 0.0)
        for row in renewals
        if _as_float(row.get("days_to_renewal"), 9999) <= 30
    )

    executive_alerts = _build_executive_alerts(
        summary=summary,
        top_vendors=top_vendors,
        renewals=renewals,
        recent_cancellations=recent_cancellations,
        horizon_days=horizon_days,
    )

    context = dashboard_module.base_template_context(
        request=request,
        context=user,
        title="Dashboard",
        active_nav="dashboard",
        extra={
            "selected_business_unit": selected_business_unit,
            "months": months,
            "horizon_days": horizon_days,
            "orgs": orgs,
            "kpis": kpis,
            "summary": summary,
            "by_category": by_category,
            "trend": trend,
            "top_vendors": top_vendors,
            "risk_dist": risk_dist,
            "renewals": renewals,
            "recent_demos": recent_demos,
            "recent_cancellations": recent_cancellations,
            "trend_max": trend_max,
            "category_max": category_max,
            "risk_total": risk_total,
            "renewals_30_count": renewals_30_count,
            "renewals_60_count": renewals_60_count,
            "renewals_30_value": renewals_30_value,
            "executive_alerts": executive_alerts,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "dashboard.html", context)

