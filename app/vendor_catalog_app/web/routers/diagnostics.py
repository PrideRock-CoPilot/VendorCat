from __future__ import annotations

from fastapi import APIRouter, Request

from vendor_catalog_app.web.bootstrap_diagnostics import build_bootstrap_diagnostics_payload
from vendor_catalog_app.web.services import get_config, get_repo, resolve_databricks_request_identity


router = APIRouter()


@router.get("/bootstrap-diagnostics")
def bootstrap_diagnostics_page(request: Request):
    repo = get_repo()
    config = get_config()
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
