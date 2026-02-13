from __future__ import annotations

from fastapi import Request


STARTUP_SPLASH_SESSION_KEY = "startup_splash_seen"
DEFAULT_DASHBOARD_MONTHS = 12
DEFAULT_DASHBOARD_HORIZON_DAYS = 180
MIN_DASHBOARD_MONTHS = 3
MAX_DASHBOARD_MONTHS = 24
MIN_DASHBOARD_HORIZON_DAYS = 60
MAX_DASHBOARD_HORIZON_DAYS = 365


def clamp_months(value: int) -> int:
    return max(MIN_DASHBOARD_MONTHS, min(int(value), MAX_DASHBOARD_MONTHS))


def clamp_horizon_days(value: int) -> int:
    return max(MIN_DASHBOARD_HORIZON_DAYS, min(int(value), MAX_DASHBOARD_HORIZON_DAYS))


def render_startup_splash(request: Request, redirect_url: str):
    request.session[STARTUP_SPLASH_SESSION_KEY] = True
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

