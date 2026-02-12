from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.services import (
    base_template_context,
    ensure_session_started,
    get_repo,
    get_user_context,
    log_page_view,
)


router = APIRouter()


def _render_startup_splash(request: Request, redirect_url: str):
    request.session["startup_splash_seen"] = True
    return request.app.state.templates.TemplateResponse(
        request,
        "startup_splash.html",
        {
            "request": request,
            "title": "Starting Vendor Catalog",
            "redirect_url": redirect_url,
            "delay_ms": 1200,
        },
    )


@router.get("/")
def home(request: Request):
    if request.session.get("startup_splash_seen"):
        return RedirectResponse(url="/dashboard", status_code=302)
    return _render_startup_splash(request, "/dashboard?splash=1")


@router.get("/dashboard")
def dashboard(request: Request, org: str = "all", months: int = 12, horizon_days: int = 180):
    if not request.session.get("startup_splash_seen"):
        # Preserve bootstrap/error behavior before rendering splash.
        get_user_context(request)
        passthrough_params = dict(request.query_params)
        passthrough_params["splash"] = "1"
        redirect_query = urlencode(passthrough_params, doseq=True)
        redirect_url = f"/dashboard?{redirect_query}" if redirect_query else "/dashboard"
        return _render_startup_splash(request, redirect_url)

    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Dashboard")

    orgs = repo.available_orgs()
    if org not in orgs:
        org = "all"
    months = max(3, min(months, 24))
    horizon_days = max(60, min(horizon_days, 365))

    kpis = repo.dashboard_kpis()
    summary = repo.executive_summary(org_id=org, months=months, horizon_days=horizon_days)
    by_category = repo.executive_spend_by_category(org_id=org, months=months)
    trend = repo.executive_monthly_spend_trend(org_id=org, months=months)
    top_vendors = repo.executive_top_vendors_by_spend(org_id=org, months=months, limit=10)
    risk_dist = repo.executive_risk_distribution(org_id=org)
    renewals = repo.executive_renewal_pipeline(org_id=org, horizon_days=horizon_days)
    recent_demos = repo.demo_outcomes().head(10)
    recent_cancellations = repo.contract_cancellations().head(10)

    context = base_template_context(
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
