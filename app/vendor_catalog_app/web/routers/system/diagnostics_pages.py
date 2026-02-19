from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from vendor_catalog_app.web.core.activity import ensure_session_started, log_page_view
from vendor_catalog_app.web.core.identity import resolve_databricks_request_identity
from vendor_catalog_app.web.core.runtime import get_config, get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.terms import terms_document
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.system.bootstrap_diagnostics import (
    bootstrap_diagnostics_authorized,
    build_bootstrap_diagnostics_payload,
)
from vendor_catalog_app.web.system.connection_lab import connection_lab_enabled

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
        "connection_lab_enabled": bool(connection_lab_enabled(config)),
    }
    return request.app.state.templates.TemplateResponse(
        request,
        "bootstrap_diagnostics.html",
        context,
        status_code=status_code,
    )


@router.get("/version-info")
def version_info_page(request: Request):
    repo = get_repo()
    config = get_config()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Version Info")

    mode_label = "Local Database" if config.use_local_db else "Databricks"
    try:
        security_policy_version = int(repo.get_security_policy_version())
    except Exception:
        security_policy_version = 1

    context = base_template_context(
        request=request,
        context=user,
        title="Version Info",
        active_nav="",
        extra={
            "app_version_info": {
                "environment": str(config.env or "").strip(),
                "mode": mode_label,
                "schema": str(config.fq_schema or "").strip(),
                "security_policy_version": security_policy_version,
                "terms_version": str(terms_document(repo=repo).get("version") or "").strip(),
            }
        },
    )
    return request.app.state.templates.TemplateResponse(request, "version_info.html", context)

