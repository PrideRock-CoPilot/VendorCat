from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.flash import add_flash
from vendor_catalog_app.web.services import (
    base_template_context,
    ensure_session_started,
    get_repo,
    get_user_context,
    log_page_view,
)
from vendor_catalog_app.web.routers.projects.common import (
    PROJECT_STATUSES,
    PROJECT_STATUS_VALUES,
    _project_base_context,
    _project_type_options,
    _render_project_section,
    _safe_return_to,
    _safe_vendor_id,
    _selected_offering_rows,
    _selected_vendor_rows,
)


router = APIRouter(prefix="/projects")

@router.get("")
def projects_home(request: Request, search: str = "", status: str = "all", vendor: str = "all"):
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

    rows = repo.list_all_projects(search_text=search, status=status, vendor_id=vendor).to_dict("records")
    for row in rows:
        project_id = str(row.get("project_id") or "")
        if not str(row.get("vendor_display_name") or "").strip():
            row["vendor_display_name"] = "Unassigned"
        row["_open_link"] = f"/projects/{project_id}/summary?return_to=%2Fprojects"
        row["_edit_link"] = f"/projects/{project_id}/edit?return_to=%2Fprojects"

    context = base_template_context(
        request=request,
        context=user,
        title="Projects",
        active_nav="projects",
        extra={
            "filters": {"search": search, "status": status, "vendor": vendor, "vendor_label": vendor_label},
            "status_options": PROJECT_STATUSES,
            "rows": rows,
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
            "form_action": f"/projects/{project_id}/edit",
        },
    )
    return request.app.state.templates.TemplateResponse(request, "project_edit.html", context)



