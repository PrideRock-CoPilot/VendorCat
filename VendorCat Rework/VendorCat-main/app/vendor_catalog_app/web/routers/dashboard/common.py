from __future__ import annotations

import random

from fastapi import Request

from vendor_catalog_app.core.defaults import (
    DEFAULT_STARTUP_SPLASH_MAX_DELAY_MS,
    DEFAULT_STARTUP_SPLASH_MIN_DELAY_MS,
)
from vendor_catalog_app.core.env import (
    TVENDOR_STARTUP_SPLASH_MAX_DELAY_MS,
    TVENDOR_STARTUP_SPLASH_MIN_DELAY_MS,
    get_env_int,
)

STARTUP_SPLASH_SESSION_KEY = "startup_splash_seen"
DEFAULT_DASHBOARD_MONTHS = 12
DEFAULT_DASHBOARD_HORIZON_DAYS = 180
MIN_DASHBOARD_MONTHS = 3
MAX_DASHBOARD_MONTHS = 24
MIN_DASHBOARD_HORIZON_DAYS = 60
MAX_DASHBOARD_HORIZON_DAYS = 365
STARTUP_SPLASH_MIN_DELAY_MS = get_env_int(
    TVENDOR_STARTUP_SPLASH_MIN_DELAY_MS,
    default=DEFAULT_STARTUP_SPLASH_MIN_DELAY_MS,
    min_value=250,
    max_value=30000,
)
STARTUP_SPLASH_MAX_DELAY_MS = get_env_int(
    TVENDOR_STARTUP_SPLASH_MAX_DELAY_MS,
    default=DEFAULT_STARTUP_SPLASH_MAX_DELAY_MS,
    min_value=250,
    max_value=60000,
)


def clamp_months(value: int) -> int:
    return max(MIN_DASHBOARD_MONTHS, min(int(value), MAX_DASHBOARD_MONTHS))


def clamp_horizon_days(value: int) -> int:
    return max(MIN_DASHBOARD_HORIZON_DAYS, min(int(value), MAX_DASHBOARD_HORIZON_DAYS))


def _startup_splash_run_id(request: Request) -> str:
    run_id = str(getattr(request.app.state, "startup_splash_run_id", "") or "").strip()
    return run_id or "default"


def has_seen_startup_splash_for_current_run(request: Request) -> bool:
    seen_value = str(request.session.get(STARTUP_SPLASH_SESSION_KEY, "") or "").strip()
    return bool(seen_value and seen_value == _startup_splash_run_id(request))


def render_startup_splash(request: Request, redirect_url: str):
    request.session[STARTUP_SPLASH_SESSION_KEY] = _startup_splash_run_id(request)
    min_delay_ms = min(STARTUP_SPLASH_MIN_DELAY_MS, STARTUP_SPLASH_MAX_DELAY_MS)
    max_delay_ms = max(STARTUP_SPLASH_MIN_DELAY_MS, STARTUP_SPLASH_MAX_DELAY_MS)
    delay_ms = random.randint(min_delay_ms, max_delay_ms)
    return request.app.state.templates.TemplateResponse(
        request,
        "startup_splash.html",
        {
            "request": request,
            "title": "Starting Vendor Catalog",
            "redirect_url": redirect_url,
            "delay_ms": delay_ms,
            "delay_min_ms": min_delay_ms,
            "delay_max_ms": max_delay_ms,
        },
    )
