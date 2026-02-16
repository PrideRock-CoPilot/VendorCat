from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from vendor_catalog_app.infrastructure.observability import get_observability_manager
from vendor_catalog_app.web.core.identity import resolve_databricks_request_identity
from vendor_catalog_app.web.core.runtime import get_config, get_repo
from vendor_catalog_app.web.routers.system.common import _runtime_ready, _utc_now_iso
from vendor_catalog_app.web.system.bootstrap_diagnostics import (
    bootstrap_diagnostics_authorized,
    build_bootstrap_diagnostics_payload,
    candidate_env_values,
    connection_context,
    path_preview,
    raw_env_key_presence,
)

router = APIRouter(prefix="/api")


@router.get("/health/live")
def api_health_live():
    return JSONResponse(
        {
            "ok": True,
            "status": "live",
            "service": "vendor_catalog_app",
            "timestamp": _utc_now_iso(),
        },
        status_code=200,
    )


@router.get("/health/ready")
def api_health_ready():
    repo = get_repo()
    config = get_config()
    ready, error = _runtime_ready(repo)
    payload = {
        "ok": ready,
        "status": "ready" if ready else "not_ready",
        "mode": "local" if config.use_local_db else "databricks",
        "schema": config.fq_schema,
        "timestamp": _utc_now_iso(),
        "checks": {
            "runtime_tables": {
                "ok": ready,
                "error": error,
            }
        },
    }
    if ready:
        return JSONResponse(payload, status_code=200)
    return JSONResponse(payload, status_code=503)


@router.get("/health/observability")
def api_health_observability(request: Request):
    config = get_config()
    if not bootstrap_diagnostics_authorized(request, config):
        return JSONResponse({"ok": False, "error": "Not found."}, status_code=404)
    manager = get_observability_manager()
    return JSONResponse(
        {
            "ok": True,
            "status": "observability",
            "timestamp": _utc_now_iso(),
            "observability": manager.health_snapshot(),
        },
        status_code=200,
    )


@router.get("/health")
def api_health(request: Request):
    repo = get_repo()
    config = get_config()
    details_allowed = bootstrap_diagnostics_authorized(request, config)
    payload = {
        "ok": True,
        "mode": "local" if config.use_local_db else "databricks",
        "schema": config.fq_schema,
    }
    if details_allowed:
        identity = resolve_databricks_request_identity(request)
        payload["principal"] = identity.get("principal") or None
        payload["auth_context"] = {
            "forwarded_email": bool(identity.get("email")),
            "forwarded_network_id": bool(identity.get("network_id")),
        }
        payload["connection_context"] = connection_context(config)
        payload["resolved_connection"] = {
            "server_hostname_preview": path_preview(config.databricks_server_hostname, keep=40),
            "http_path_preview": path_preview(config.databricks_http_path, keep=60),
            "raw_env_key_presence": raw_env_key_presence(),
            "candidate_env_values": candidate_env_values(),
        }
    ready, error = _runtime_ready(repo)
    if ready:
        return JSONResponse(payload, status_code=200)
    payload["ok"] = False
    if error is not None and details_allowed:
        payload["error"] = error
    else:
        payload["error"] = "Runtime checks failed."
    return JSONResponse(payload, status_code=503)


@router.get("/bootstrap-diagnostics")
def api_bootstrap_diagnostics(request: Request):
    config = get_config()
    if not bootstrap_diagnostics_authorized(request, config):
        return JSONResponse({"ok": False, "error": "Not found."}, status_code=404)
    repo = get_repo()
    identity = resolve_databricks_request_identity(request)
    payload, status_code = build_bootstrap_diagnostics_payload(repo, config, identity)
    return JSONResponse(payload, status_code=status_code)

