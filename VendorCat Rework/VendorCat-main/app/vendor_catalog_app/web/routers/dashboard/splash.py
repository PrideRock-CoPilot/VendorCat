from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.routers.dashboard.common import (
    has_seen_startup_splash_for_current_run,
    render_startup_splash,
)

router = APIRouter()


@router.get("/")
def home(request: Request):
    if has_seen_startup_splash_for_current_run(request):
        return RedirectResponse(url="/dashboard", status_code=302)
    return render_startup_splash(request, "/dashboard?splash=1")
