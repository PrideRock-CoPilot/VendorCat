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


def _dashboard_module():
    # Resolve through package namespace so tests can monkeypatch dashboard.get_user_context.
    from vendor_catalog_app.web.routers import dashboard as dashboard_module

    return dashboard_module


@router.get("/dashboard")
def dashboard(
    request: Request,
    org: str = "all",
    months: int = DEFAULT_DASHBOARD_MONTHS,
    horizon_days: int = DEFAULT_DASHBOARD_HORIZON_DAYS,
):
    if not has_seen_startup_splash_for_current_run(request):
        passthrough_params = dict(request.query_params)
        passthrough_params["splash"] = "1"
        redirect_query = urlencode(passthrough_params, doseq=True)
        redirect_url = f"/dashboard?{redirect_query}" if redirect_query else "/dashboard"
        return render_startup_splash(request, redirect_url)

    dashboard_module = _dashboard_module()
    repo = dashboard_module.get_repo()
    user = dashboard_module.get_user_context(request)
    if not set(getattr(user, "roles", set()) or set()):
        return RedirectResponse(url="/access/request", status_code=303)
    dashboard_module.ensure_session_started(request, user)
    dashboard_module.log_page_view(request, user, "Dashboard")

    orgs = repo.available_orgs()
    if org not in orgs:
        org = "all"
    months = clamp_months(months)
    horizon_days = clamp_horizon_days(horizon_days)

    kpis = repo.dashboard_kpis()
    summary = repo.executive_summary(org_id=org, months=months, horizon_days=horizon_days)
    by_category = repo.executive_spend_by_category(org_id=org, months=months)
    trend = repo.executive_monthly_spend_trend(org_id=org, months=months)
    top_vendors = repo.executive_top_vendors_by_spend(org_id=org, months=months, limit=10)
    risk_dist = repo.executive_risk_distribution(org_id=org)
    renewals = repo.executive_renewal_pipeline(org_id=org, horizon_days=horizon_days)
    recent_demos = repo.demo_outcomes().head(10)
    recent_cancellations = repo.contract_cancellations().head(10)

    context = dashboard_module.base_template_context(
        request=request,
        context=user,
        title="Dashboard",
        active_nav="dashboard",
        extra={
            "selected_org": org,
            "months": months,
            "horizon_days": horizon_days,
            "orgs": orgs,
            "kpis": kpis,
            "summary": summary,
            "by_category": by_category.to_dict("records"),
            "trend": trend.to_dict("records"),
            "top_vendors": top_vendors.to_dict("records"),
            "risk_dist": risk_dist.to_dict("records"),
            "renewals": renewals.to_dict("records"),
            "recent_demos": recent_demos.to_dict("records"),
            "recent_cancellations": recent_cancellations.to_dict("records"),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "dashboard.html", context)
