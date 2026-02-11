from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from vendor_catalog_app.repository import SchemaBootstrapRequiredError
from vendor_catalog_app.web.services import (
    ensure_session_started,
    get_config,
    get_repo,
    get_user_context,
    resolve_databricks_request_identity,
)


router = APIRouter(prefix="/api")


def _normalize_limit(limit: int) -> int:
    return max(1, min(int(limit or 20), 50))


@router.get("/health")
def api_health(request: Request):
    repo = get_repo()
    config = get_config()
    identity = resolve_databricks_request_identity(request)
    payload = {
        "ok": True,
        "mode": "local" if config.use_local_db else "databricks",
        "schema": config.fq_schema,
        "principal": identity.get("principal") or None,
        "auth_context": {
            "forwarded_email": bool(identity.get("email")),
            "forwarded_network_id": bool(identity.get("network_id")),
        },
    }
    try:
        repo.ensure_runtime_tables()
        return JSONResponse(payload, status_code=200)
    except SchemaBootstrapRequiredError as exc:
        payload["ok"] = False
        payload["error"] = str(exc)
        return JSONResponse(payload, status_code=503)
    except Exception as exc:
        payload["ok"] = False
        payload["error"] = f"Connection check failed: {exc}"
        return JSONResponse(payload, status_code=503)


@router.get("/vendors/search")
def api_vendor_search(request: Request, q: str = "", limit: int = 20):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    rows = repo.search_vendors_typeahead(q=q, limit=_normalize_limit(limit)).to_dict("records")
    return JSONResponse({"items": rows})


@router.get("/offerings/search")
def api_offering_search(request: Request, vendor_id: str = "", q: str = "", limit: int = 20):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    rows = repo.search_offerings_typeahead(
        vendor_id=vendor_id.strip() or None,
        q=q,
        limit=_normalize_limit(limit),
    ).to_dict("records")
    return JSONResponse({"items": rows})


@router.get("/projects/search")
def api_project_search(request: Request, q: str = "", limit: int = 20):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    rows = repo.search_projects_typeahead(q=q, limit=_normalize_limit(limit)).to_dict("records")
    return JSONResponse({"items": rows})


@router.get("/users/search")
def api_user_search(request: Request, q: str = "", limit: int = 20):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    rows = repo.search_user_directory(q=q, limit=_normalize_limit(limit)).to_dict("records")
    return JSONResponse({"items": rows})
