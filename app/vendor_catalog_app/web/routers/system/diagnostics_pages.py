from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from vendor_catalog_app.web.core.identity import resolve_databricks_request_identity
from vendor_catalog_app.web.core.runtime import get_config, get_repo
from vendor_catalog_app.web.system.bootstrap_diagnostics import (
    bootstrap_diagnostics_authorized,
    build_bootstrap_diagnostics_payload,
)

router = APIRouter()


@router.get("/bootstrap-diagnostics")
def bootstrap_diagnostics_page(request: Request):
    config = get_config()
    if not bootstrap_diagnostics_authorized(request, config):
        return PlainTextResponse("Not found.", status_code=404)
    repo = get_repo()
    identity = resolve_databricks_request_identity(request)
    diagnostics, status_code = build_bootstrap_diagnostics_payload(repo, config, identity)
    context = {
        "request": request,
        "diagnostics": diagnostics,
        "error_message": "",
    }
    return request.app.state.templates.TemplateResponse(
        request,
        "bootstrap_diagnostics.html",
        context,
        status_code=status_code,
    )

