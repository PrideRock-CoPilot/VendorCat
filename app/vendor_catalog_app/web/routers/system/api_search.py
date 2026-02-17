from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from vendor_catalog_app.web.core.activity import ensure_session_started
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.routers.system.common import _normalize_limit

router = APIRouter(prefix="/api")


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


@router.get("/contracts/search")
def api_contract_search(request: Request, q: str = "", limit: int = 20):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    rows = repo.search_contracts_typeahead(q=q, limit=_normalize_limit(limit)).to_dict("records")
    return JSONResponse({"items": rows})


@router.get("/users/search")
def api_user_search(request: Request, q: str = "", limit: int = 20):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    rows = repo.search_user_directory(q=q, limit=_normalize_limit(limit)).to_dict("records")
    return JSONResponse({"items": rows})


@router.get("/contacts/search")
def api_contact_search(request: Request, vendor_id: str = "", q: str = "", limit: int = 20):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    rows = repo.search_contacts_typeahead(
        vendor_id=vendor_id.strip() or None,
        q=q,
        limit=_normalize_limit(limit),
    ).to_dict("records")
    return JSONResponse({"items": rows})

