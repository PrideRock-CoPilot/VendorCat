from __future__ import annotations

import math
from urllib.parse import urlencode

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
    _project_type_options,
    _safe_return_to,
    _safe_vendor_id,
    _selected_offering_rows,
    _selected_vendor_rows,
)
from vendor_catalog_app.web.routers.vendors.constants import PROJECT_UPDATE_REASON_OPTIONS

router = APIRouter(prefix="/projects")

PROJECT_PAGE_SIZES = [25, 50, 100, 250]
DEFAULT_PROJECT_PAGE_SIZE = 25
MAX_PROJECT_PAGE_SIZE = 250
MAX_PROJECT_LIST_ROWS = 5000


def _normalize_project_page_size(raw_value: str | int | None) -> int:
    try:
        value = int(str(raw_value or DEFAULT_PROJECT_PAGE_SIZE).strip())
    except Exception:
        return DEFAULT_PROJECT_PAGE_SIZE
    return max(1, min(value, MAX_PROJECT_PAGE_SIZE))


def _normalize_project_page(raw_value: str | int | None) -> int:
    try:
        value = int(str(raw_value or 1).strip())
    except Exception:
        return 1
    return max(1, value)


def _projects_url(
    *,
    search: str,
    status: str,
    vendor: str,
    page: int,
    page_size: int,
) -> str:
    query = {
        "search": search,
        "status": status,
        "vendor": vendor,
        "page": str(page),
        "page_size": str(page_size),
    }
    return f"/projects?{urlencode(query)}"

@router.get("")
def projects_home(
    request: Request,
    search: str = "",
    status: str = "all",
    vendor: str = "all",
    page: int = 1,
    page_size: int = DEFAULT_PROJECT_PAGE_SIZE,
):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Projects")

    if status not in PROJECT_STATUSES:
        status = "all"
    if vendor != "all" and not _safe_vendor_id(repo, vendor):
        vendor = "all"
    vendor_label = ""
    if vendor != "all":
        profile = repo.get_vendor_profile(vendor)
        if not profile.empty:
            row = profile.iloc[0].to_dict()
            vendor_label = str(row.get("display_name") or row.get("legal_name") or vendor)

    page_size = _normalize_project_page_size(page_size)
    page = _normalize_project_page(page)
    rows_df = repo.list_all_projects(
        search_text=search,
        status=status,
        vendor_id=vendor,
        limit=MAX_PROJECT_LIST_ROWS,
    ).copy()
    total_rows = int(len(rows_df.index))
    page_count = max(1, math.ceil(total_rows / page_size)) if total_rows else 1
    if page > page_count:
        page = page_count
    start = (page - 1) * page_size
    end = start + page_size
    rows = rows_df.iloc[start:end].to_dict("records")
    for row in rows:
        project_id = str(row.get("project_id") or "")
        if not str(row.get("vendor_display_name") or "").strip():
            row["vendor_display_name"] = "Unassigned"
        row["_open_link"] = f"/projects/{project_id}/summary?return_to=%2Fprojects"
        row["_edit_link"] = f"/projects/{project_id}/edit?return_to=%2Fprojects"

    prev_page = page - 1 if page > 1 else 1
    next_page = page + 1 if page < page_count else page_count
    show_from = (start + 1) if total_rows else 0
    show_to = min(end, total_rows)

    context = base_template_context(
        request=request,
        context=user,
        title="Projects",
        active_nav="projects",
        extra={
            "filters": {
                "search": search,
                "status": status,
                "vendor": vendor,
                "vendor_label": vendor_label,
                "page": page,
                "page_size": page_size,
            },
            "status_options": PROJECT_STATUSES,
            "page_sizes": PROJECT_PAGE_SIZES,
            "rows": rows,
            "total_rows": total_rows,
            "page_count": page_count,
            "show_from": show_from,
            "show_to": show_to,
            "prev_page_url": _projects_url(
                search=search,
                status=status,
                vendor=vendor,
                page=prev_page,
                page_size=page_size,
            ),
            "next_page_url": _projects_url(
                search=search,
                status=status,
                vendor=vendor,
                page=next_page,
                page_size=page_size,
            ),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "projects.html", context)


@router.get("/new")
def projects_new_form(request: Request, vendor_id: str = "", return_to: str = "/projects"):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Projects - New")

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url="/projects", status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to create projects.", "error")
        return RedirectResponse(url="/projects", status_code=303)

    selected_vendor_ids: list[str] = []
    safe_vendor = _safe_vendor_id(repo, vendor_id)
    if safe_vendor:
        selected_vendor_ids = [safe_vendor]
    selected_vendor_rows = _selected_vendor_rows(repo, selected_vendor_ids)

    context = base_template_context(
        request=request,
        context=user,
        title="New Project",
        active_nav="projects",
        extra={
            "vendor_id": safe_vendor or "",
            "vendor_display_name": "Global",
            "return_to": _safe_return_to(return_to),
            "project_types": _project_type_options(repo),
            "project_statuses": PROJECT_STATUS_VALUES,
            "selected_vendor_rows": selected_vendor_rows,
            "selected_offering_rows": [],
            "form_action": "/projects/new",
        },
    )
    return request.app.state.templates.TemplateResponse(request, "project_new.html", context)



@router.get("/{project_id}/edit")
def project_edit_form(request: Request, project_id: str, return_to: str = "/projects"):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Projects - Edit")

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=f"/projects/{project_id}/summary?return_to=%2Fprojects", status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to edit projects.", "error")
        return RedirectResponse(url=f"/projects/{project_id}/summary?return_to=%2Fprojects", status_code=303)

    project = repo.get_project_by_id(project_id)
    if project is None:
        add_flash(request, "Project not found.", "error")
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    project_vendor_ids = [str(x).strip() for x in (project.get("vendor_ids") or []) if str(x).strip()]
    project_offering_ids = [str(x).strip() for x in (project.get("linked_offering_ids") or []) if str(x).strip()]
    selected_vendor_rows = _selected_vendor_rows(repo, project_vendor_ids)
    selected_offering_rows = _selected_offering_rows(repo, project_offering_ids)

    context = base_template_context(
        request=request,
        context=user,
        title="Edit Project",
        active_nav="projects",
        extra={
            "vendor_id": str(project.get("vendor_id") or ""),
            "vendor_display_name": str(project.get("vendor_display_name") or ""),
            "project": project,
            "selected_vendor_rows": selected_vendor_rows,
            "selected_offering_rows": selected_offering_rows,
            "return_to": _safe_return_to(return_to),
            "project_types": _project_type_options(repo),
            "project_statuses": PROJECT_STATUS_VALUES,
            "project_update_reason_options": PROJECT_UPDATE_REASON_OPTIONS,
            "form_action": f"/projects/{project_id}/edit",
        },
    )
    return request.app.state.templates.TemplateResponse(request, "project_edit.html", context)




