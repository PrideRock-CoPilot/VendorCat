from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from vendor_catalog_app.web.core.activity import ensure_session_started, log_page_view
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.projects.common import (
    PROJECT_STATUS_VALUES,
    PROJECT_STATUSES,
    _project_base_context,
    _project_type_options,
    _render_project_section,
    _safe_return_to,
    _safe_vendor_id,
    _selected_offering_rows,
    _selected_vendor_rows,
)

router = APIRouter(prefix="/projects")

@router.get("/{project_id}/offerings/new")
def project_new_offering_redirect(request: Request, project_id: str, vendor_id: str = "", return_to: str = "/projects"):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Projects - New Offering Redirect")

    target_return = _safe_return_to(return_to)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=f"/projects/{project_id}/offerings?return_to={quote(target_return, safe='')}", status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to create offerings.", "error")
        return RedirectResponse(url=f"/projects/{project_id}/offerings?return_to={quote(target_return, safe='')}", status_code=303)
    safe_vendor = _safe_vendor_id(repo, vendor_id)
    if not safe_vendor:
        add_flash(request, "Select a vendor first to create a new offering.", "error")
        return RedirectResponse(url=f"/projects/{project_id}/offerings?return_to={quote(target_return, safe='')}", status_code=303)
    return RedirectResponse(
        url=f"/vendors/{safe_vendor}/offerings/new?return_to={quote(f'/projects/{project_id}/offerings', safe='')}",
        status_code=302,
    )


@router.get("/{project_id}")
def project_default(request: Request, project_id: str, return_to: str = "/projects"):
    return RedirectResponse(
        url=f"/projects/{project_id}/summary?return_to={quote(_safe_return_to(return_to), safe='')}",
        status_code=302,
    )


@router.get("/{project_id}/summary")
def project_summary(request: Request, project_id: str, return_to: str = "/projects"):
    repo = get_repo()
    base = _project_base_context(repo, request, project_id, "summary", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)
    return _render_project_section(request, base, "summary")


@router.get("/{project_id}/ownership")
def project_ownership(request: Request, project_id: str, return_to: str = "/projects"):
    repo = get_repo()
    base = _project_base_context(repo, request, project_id, "ownership", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)
    return _render_project_section(request, base, "ownership")


@router.get("/{project_id}/offerings")
def project_offerings(request: Request, project_id: str, return_to: str = "/projects"):
    repo = get_repo()
    base = _project_base_context(repo, request, project_id, "offerings", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)
    return _render_project_section(request, base, "offerings")


@router.get("/{project_id}/demos")
def project_demos(request: Request, project_id: str, return_to: str = "/projects"):
    repo = get_repo()
    base = _project_base_context(repo, request, project_id, "demos", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)
    return _render_project_section(request, base, "demos")


@router.get("/{project_id}/docs")
def project_docs(request: Request, project_id: str, return_to: str = "/projects"):
    repo = get_repo()
    base = _project_base_context(repo, request, project_id, "docs", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)
    return _render_project_section(request, base, "docs")



@router.get("/{project_id}/notes")
def project_notes(request: Request, project_id: str, return_to: str = "/projects"):
    repo = get_repo()
    base = _project_base_context(repo, request, project_id, "notes", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)
    return _render_project_section(request, base, "notes")


@router.get("/{project_id}/changes")
def project_changes_redirect(request: Request, project_id: str, return_to: str = "/projects"):
    return RedirectResponse(
        url=f"/projects/{project_id}/notes?return_to={quote(_safe_return_to(return_to), safe='')}",
        status_code=302,
    )



