from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.routers.dashboard.common import STARTUP_SPLASH_SESSION_KEY, render_startup_splash


router = APIRouter()


@router.get("/")
def home(request: Request):
    if request.session.get(STARTUP_SPLASH_SESSION_KEY):
        return RedirectResponse(url="/dashboard", status_code=302)
    return render_startup_splash(request, "/dashboard?splash=1")

