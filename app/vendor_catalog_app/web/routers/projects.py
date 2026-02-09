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
from vendor_catalog_app.web.utils.doc_links import DOC_TYPES, suggest_doc_title, suggest_doc_type


router = APIRouter(prefix="/projects")

PROJECT_STATUSES = ["all", "draft", "active", "blocked", "complete", "cancelled"]
PROJECT_SECTIONS = [
    ("summary", "Summary"),
    ("ownership", "Ownership"),
    ("offerings", "Offerings"),
    ("demos", "Demos"),
    ("docs", "Documents"),
    ("notes", "Notes"),
]
PROJECT_TYPES = ["rfp", "poc", "renewal", "implementation", "other"]
PROJECT_STATUS_VALUES = [x for x in PROJECT_STATUSES if x != "all"]


def _safe_return_to(value: str | None) -> str:
    if not value:
        return "/projects"
    if value.startswith("/projects") or value.startswith("/vendors"):
        return value
    return "/projects"


def _safe_vendor_id(repo, vendor_id: str | None) -> str | None:
    if not vendor_id:
        return None
    cleaned = str(vendor_id).strip()
    if not cleaned:
        return None
    profile = repo.get_vendor_profile(cleaned)
    if profile.empty:
        return None
    return cleaned


def _vendor_options(repo) -> list[dict[str, str]]:
    vendor_df = repo.search_vendors(search_text="", lifecycle_state="all")
    options: list[dict[str, str]] = []
    for row in vendor_df.to_dict("records"):
        vendor_id = str(row.get("vendor_id") or "")
        label = str(row.get("display_name") or row.get("legal_name") or vendor_id)
        if vendor_id:
            options.append({"vendor_id": vendor_id, "label": label})
    return options


def _offering_options(repo) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for vendor in _vendor_options(repo):
        offerings = repo.get_vendor_offerings(vendor["vendor_id"]).to_dict("records")
        for row in offerings:
            options.append(
                {
                    "offering_id": str(row.get("offering_id") or ""),
                    "vendor_id": vendor["vendor_id"],
                    "vendor_display_name": vendor["label"],
                    "offering_name": str(row.get("offering_name") or row.get("offering_id") or ""),
                }
            )
    options.sort(key=lambda x: (x["vendor_display_name"], x["offering_name"]))
    return options


def _project_nav(project_id: str, return_to: str, active_key: str) -> list[dict]:
    encoded_return = quote(return_to, safe="")
    return [
        {
            "key": key,
            "label": label,
            "url": f"/projects/{project_id}/{key}?return_to={encoded_return}",
            "active": key == active_key,
        }
        for key, label in PROJECT_SECTIONS
    ]


def _normalize_project_type(value: str) -> str:
    project_type = (value or "other").strip().lower()
    if project_type not in PROJECT_TYPES:
        raise ValueError(f"Project type must be one of: {', '.join(PROJECT_TYPES)}")
    return project_type


def _normalize_project_status(value: str) -> str:
    status = (value or "draft").strip().lower()
    if status not in PROJECT_STATUS_VALUES:
        raise ValueError(f"Status must be one of: {', '.join(PROJECT_STATUS_VALUES)}")
    return status


def _normalize_doc_type(value: str) -> str:
    doc_type = (value or "").strip().lower()
    if not doc_type:
        return ""
    if doc_type not in DOC_TYPES:
        raise ValueError(f"Document type must be one of: {', '.join(DOC_TYPES)}")
    return doc_type


def _prepare_doc_payload(form_data: dict[str, str]) -> dict[str, str]:
    doc_url = str(form_data.get("doc_url", "")).strip()
    doc_type = _normalize_doc_type(str(form_data.get("doc_type", "")))
    doc_title = str(form_data.get("doc_title", "")).strip()
    tags = str(form_data.get("tags", "")).strip()
    owner = str(form_data.get("owner", "")).strip()

    if not doc_url.lower().startswith("https://"):
        raise ValueError("Document URL must start with https://")
    if not doc_type:
        doc_type = suggest_doc_type(doc_url)
    if not doc_title:
        doc_title = suggest_doc_title(doc_url)
    if not doc_title:
        raise ValueError("Document title is required.")
    if len(doc_title) > 120:
        doc_title = doc_title[:120].rstrip()
    return {
        "doc_url": doc_url,
        "doc_type": doc_type,
        "doc_title": doc_title,
        "tags": tags,
        "owner": owner,
    }


def _project_base_context(repo, request: Request, project_id: str, section: str, return_to: str):
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, f"Projects - {section.title()}")

    project = repo.get_project_by_id(project_id)
    if project is None:
        add_flash(request, f"Project {project_id} not found.", "error")
        return None

    project_vendor_ids = [str(v) for v in (project.get("vendor_ids") or []) if str(v).strip()]
    requested_vendor_id = str(request.query_params.get("vendor_id", "")).strip()
    vendor_id = ""
    if requested_vendor_id and requested_vendor_id in project_vendor_ids:
        vendor_id = requested_vendor_id
    elif str(project.get("vendor_id") or "").strip() in project_vendor_ids:
        vendor_id = str(project.get("vendor_id") or "").strip()
    elif project_vendor_ids:
        vendor_id = project_vendor_ids[0]

    all_offerings = repo.list_project_offerings(None, project_id).to_dict("records")
    offerings = [row for row in all_offerings if not vendor_id or str(row.get("vendor_id") or "") == vendor_id]
    offering_ids = {str(row.get("offering_id") or "") for row in all_offerings}
    offering_owner_rows: list[dict] = []
    offering_contact_rows: list[dict] = []
    for mapped_vendor_id in project_vendor_ids:
        offering_owner_rows.extend(repo.get_vendor_offering_business_owners(mapped_vendor_id).to_dict("records"))
        offering_contact_rows.extend(repo.get_vendor_offering_contacts(mapped_vendor_id).to_dict("records"))
    linked_offering_owners = [row for row in offering_owner_rows if str(row.get("offering_id") or "") in offering_ids]
    linked_offering_contacts = [
        row for row in offering_contact_rows if str(row.get("offering_id") or "") in offering_ids
    ]
    demos = repo.list_project_demos(None, project_id).to_dict("records")
    notes = repo.list_project_notes(vendor_id or None, project_id).to_dict("records")
    docs = repo.list_docs("project", project_id).to_dict("records")
    activity = repo.get_project_activity(vendor_id or None, project_id).head(50).to_dict("records")
    project_vendors = repo.list_project_vendors(project_id).to_dict("records")
    owner_count = 1 if str(project.get("owner_principal") or "").strip() else 0

    summary = {
        "status": str(project.get("status") or "unknown"),
        "project_type": str(project.get("project_type") or "other"),
        "vendor_count": len(project_vendors),
        "offering_count": len(all_offerings),
        "demo_count": len(demos),
        "note_count": len(notes),
        "doc_count": len(docs),
        "owner_count": owner_count,
    }

    for row in demos:
        linked_demo_id = str(row.get("linked_vendor_demo_id") or "").strip()
        demo_vendor_id = str(row.get("vendor_id") or "").strip()
        row["_linked_vendor_demo_link"] = (
            f"/vendors/{demo_vendor_id}/demos?return_to={quote(f'/projects/{project_id}/demos', safe='')}"
            if linked_demo_id and demo_vendor_id
            else ""
        )

    return {
        "user": user,
        "project": project,
        "project_id": project_id,
        "vendor_id": vendor_id,
        "vendor_display_name": str(project.get("vendor_display_name") or vendor_id or "Unassigned"),
        "project_vendors": project_vendors,
        "return_to": _safe_return_to(return_to),
        "project_nav": _project_nav(project_id, _safe_return_to(return_to), section),
        "summary": summary,
        "offerings": offerings,
        "all_offerings": all_offerings,
        "offering_owners": linked_offering_owners,
        "offering_contacts": linked_offering_contacts,
        "demos": demos,
        "notes": notes,
        "docs": docs,
        "activity": activity,
    }


def _render_project_section(request: Request, base: dict, section: str):
    repo = get_repo()
    vendor_id = base["vendor_id"]
    project_id = base["project_id"]
    project = base["project"]
    vendor_demos = repo.get_vendor_demos(vendor_id).to_dict("records") if vendor_id else []
    demo_map_options = [{"demo_id": "", "label": "Select existing vendor demo"}]
    for row in vendor_demos:
        demo_id = str(row.get("demo_id") or "")
        label = f"{demo_id} | {row.get('selection_outcome') or 'unknown'} | {row.get('demo_date') or ''}"
        demo_map_options.append({"demo_id": demo_id, "label": label})

    for row in base["demos"]:
        demo_id = str(row.get("project_demo_id") or "")
        demo_vendor_id = str(row.get("vendor_id") or vendor_id or "")
        row["_update_action"] = f"/vendors/{demo_vendor_id}/projects/{project_id}/demos/{demo_id}/update"
        row["_remove_action"] = f"/vendors/{demo_vendor_id}/projects/{project_id}/demos/{demo_id}/remove"
        row["_demo_doc_link_action"] = f"/vendors/{demo_vendor_id}/projects/{project_id}/demos/{demo_id}/docs/link"
        row["_docs"] = repo.list_docs("demo", demo_id).to_dict("records")

    current_vendor_ids = [str(row.get("vendor_id") or "") for row in base["project_vendors"] if str(row.get("vendor_id") or "")]
    current_offering_ids = {
        str(row.get("offering_id") or "") for row in base["all_offerings"] if str(row.get("offering_id") or "")
    }
    attachable_vendor_options = [v for v in _vendor_options(repo) if v["vendor_id"] not in current_vendor_ids]
    all_vendor_options: list[dict[str, str]] = []
    vendor_seen: set[str] = set()
    for row in base["project_vendors"]:
        vendor_id = str(row.get("vendor_id") or "")
        label = str(row.get("vendor_display_name") or vendor_id)
        if vendor_id and vendor_id not in vendor_seen:
            all_vendor_options.append({"vendor_id": vendor_id, "label": label, "linked": "true"})
            vendor_seen.add(vendor_id)
    for row in attachable_vendor_options:
        vendor_id = str(row.get("vendor_id") or "")
        if vendor_id and vendor_id not in vendor_seen:
            all_vendor_options.append(
                {"vendor_id": vendor_id, "label": str(row.get("label") or vendor_id), "linked": "false"}
            )
            vendor_seen.add(vendor_id)
    attachable_offering_options = [
        o for o in _offering_options(repo) if o["offering_id"] and o["offering_id"] not in current_offering_ids
    ]

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{project.get('project_name')} - {section.title()}",
        active_nav="projects",
        extra={
            "section": section,
            "project": project,
            "project_id": project_id,
            "vendor_id": vendor_id,
            "vendor_display_name": base["vendor_display_name"],
            "project_vendors": base["project_vendors"],
            "return_to": base["return_to"],
            "project_nav": base["project_nav"],
            "summary": base["summary"],
            "project_offerings": base["offerings"],
            "project_offering_owners": base["offering_owners"],
            "project_offering_contacts": base["offering_contacts"],
            "project_demos": base["demos"],
            "project_notes": base["notes"],
            "project_docs": base["docs"],
            "project_activity": base["activity"],
            "doc_types": DOC_TYPES,
            "demo_map_options": demo_map_options,
            "attachable_vendor_options": attachable_vendor_options,
            "all_vendor_options": all_vendor_options,
            "attachable_offering_options": attachable_offering_options,
            "owner_update_action": f"/projects/{project_id}/owner/update",
            "add_vendor_action": f"/projects/{project_id}/vendors/add",
            "add_offering_action": f"/projects/{project_id}/offerings/add",
        },
    )
    return request.app.state.templates.TemplateResponse("project_section.html", context)


@router.get("")
def projects_home(request: Request, search: str = "", status: str = "all", vendor: str = "all"):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Projects")

    vendor_options = [{"vendor_id": "all", "label": "all"}, *_vendor_options(repo)]

    if status not in PROJECT_STATUSES:
        status = "all"
    if vendor != "all" and not _safe_vendor_id(repo, vendor):
        vendor = "all"

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
            "filters": {"search": search, "status": status, "vendor": vendor},
            "status_options": PROJECT_STATUSES,
            "vendor_options": vendor_options,
            "rows": rows,
        },
    )
    return request.app.state.templates.TemplateResponse("projects.html", context)


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

    context = base_template_context(
        request=request,
        context=user,
        title="New Project",
        active_nav="projects",
        extra={
            "vendor_id": safe_vendor or "",
            "vendor_display_name": "Global",
            "return_to": _safe_return_to(return_to),
            "project_types": PROJECT_TYPES,
            "project_statuses": PROJECT_STATUS_VALUES,
            "offerings": _offering_options(repo),
            "vendor_options": _vendor_options(repo),
            "selected_vendor_ids": selected_vendor_ids,
            "form_action": "/projects/new",
        },
    )
    return request.app.state.templates.TemplateResponse("project_new.html", context)


@router.post("/new")
async def projects_new_submit(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/projects")))

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to create projects.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    linked_vendors = [str(x).strip() for x in form.getlist("linked_vendors") if str(x).strip()]
    linked_offerings = [str(x).strip() for x in form.getlist("linked_offerings") if str(x).strip()]
    try:
        project_id = repo.create_project(
            vendor_id=None,
            vendor_ids=linked_vendors,
            actor_user_principal=user.user_principal,
            project_name=str(form.get("project_name", "")).strip(),
            project_type=_normalize_project_type(str(form.get("project_type", "other"))),
            status=_normalize_project_status(str(form.get("status", "draft"))),
            start_date=str(form.get("start_date", "")).strip() or None,
            target_date=str(form.get("target_date", "")).strip() or None,
            owner_principal=str(form.get("owner_principal", "")).strip() or None,
            description=str(form.get("description", "")).strip() or None,
            linked_offering_ids=linked_offerings,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="projects",
            event_type="project_create",
            payload={"project_id": project_id, "vendor_count": len(linked_vendors)},
        )
        add_flash(request, f"Project created: {project_id}", "success")
        return RedirectResponse(
            url=f"/projects/{project_id}/summary?return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    except Exception as exc:
        add_flash(request, f"Could not create project: {exc}", "error")
        return RedirectResponse(url=f"/projects/new?return_to={quote(return_to, safe='')}", status_code=303)


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

    context = base_template_context(
        request=request,
        context=user,
        title="Edit Project",
        active_nav="projects",
        extra={
            "vendor_id": str(project.get("vendor_id") or ""),
            "vendor_display_name": str(project.get("vendor_display_name") or ""),
            "project": project,
            "offerings": _offering_options(repo),
            "vendor_options": _vendor_options(repo),
            "return_to": _safe_return_to(return_to),
            "project_types": PROJECT_TYPES,
            "project_statuses": PROJECT_STATUS_VALUES,
            "form_action": f"/projects/{project_id}/edit",
        },
    )
    return request.app.state.templates.TemplateResponse("project_edit.html", context)


@router.post("/{project_id}/edit")
async def project_edit_submit(request: Request, project_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/projects")))
    reason = str(form.get("reason", "")).strip()

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=f"/projects/{project_id}/summary?return_to={quote(return_to, safe='')}", status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to edit projects.", "error")
        return RedirectResponse(url=f"/projects/{project_id}/summary?return_to={quote(return_to, safe='')}", status_code=303)

    linked_vendors = [str(x).strip() for x in form.getlist("linked_vendors") if str(x).strip()]
    linked_offerings = [str(x).strip() for x in form.getlist("linked_offerings") if str(x).strip()]
    updates = {
        "project_name": str(form.get("project_name", "")).strip(),
        "project_type": _normalize_project_type(str(form.get("project_type", "other"))),
        "status": _normalize_project_status(str(form.get("status", "draft"))),
        "start_date": str(form.get("start_date", "")).strip() or None,
        "target_date": str(form.get("target_date", "")).strip() or None,
        "owner_principal": str(form.get("owner_principal", "")).strip() or None,
        "description": str(form.get("description", "")).strip() or None,
    }

    try:
        if user.can_direct_apply:
            result = repo.update_project(
                vendor_id=None,
                project_id=project_id,
                actor_user_principal=user.user_principal,
                updates=updates,
                vendor_ids=linked_vendors,
                linked_offering_ids=linked_offerings,
                reason=reason,
            )
            add_flash(
                request,
                f"Project updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            current_project = repo.get_project_by_id(project_id) or {}
            current_vendor_ids = [str(x) for x in (current_project.get("vendor_ids") or []) if str(x).strip()]
            cr_vendor_id = linked_vendors[0] if linked_vendors else (current_vendor_ids[0] if current_vendor_ids else "")
            request_id = repo.create_vendor_change_request(
                vendor_id=cr_vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_project",
                payload={
                    "project_id": project_id,
                    "updates": updates,
                    "vendor_ids": linked_vendors,
                    "linked_offering_ids": linked_offerings,
                    "reason": reason,
                },
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="projects",
            event_type="project_update",
            payload={"project_id": project_id, "vendor_count": len(linked_vendors)},
        )
    except Exception as exc:
        add_flash(request, f"Could not update project: {exc}", "error")

    return RedirectResponse(
        url=f"/projects/{project_id}/summary?return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{project_id}/owner/update")
async def project_owner_update(request: Request, project_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/projects/{project_id}/ownership")))
    owner_principal = str(form.get("owner_principal", "")).strip() or None
    reason = str(form.get("reason", "")).strip() or "Update project owner"

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to update owners.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    project = repo.get_project_by_id(project_id)
    if project is None:
        add_flash(request, "Project not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        if user.can_direct_apply:
            result = repo.update_project(
                vendor_id=None,
                project_id=project_id,
                actor_user_principal=user.user_principal,
                updates={"owner_principal": owner_principal},
                vendor_ids=None,
                linked_offering_ids=None,
                reason=reason,
            )
            add_flash(
                request,
                f"Owner updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            vendor_ids = [str(x) for x in (project.get("vendor_ids") or []) if str(x).strip()]
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_ids[0] if vendor_ids else "",
                requestor_user_principal=user.user_principal,
                change_type="update_project_owner",
                payload={"project_id": project_id, "owner_principal": owner_principal, "reason": reason},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="projects",
            event_type="project_owner_update",
            payload={"project_id": project_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not update owner: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{project_id}/vendors/add")
async def project_add_vendor(request: Request, project_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/projects/{project_id}/offerings")))
    add_vendor_id = str(form.get("vendor_id", "")).strip()
    reason = str(form.get("reason", "")).strip() or "Quick add vendor"

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to add vendors.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not add_vendor_id:
        add_flash(request, "Select a vendor to add.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    project = repo.get_project_by_id(project_id)
    if project is None:
        add_flash(request, "Project not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    vendor_ids = [str(x) for x in (project.get("vendor_ids") or []) if str(x).strip()]
    if add_vendor_id not in vendor_ids:
        vendor_ids.append(add_vendor_id)
    try:
        if user.can_direct_apply:
            result = repo.update_project(
                vendor_id=None,
                project_id=project_id,
                actor_user_principal=user.user_principal,
                updates={},
                vendor_ids=vendor_ids,
                linked_offering_ids=None,
                reason=reason,
            )
            add_flash(
                request,
                f"Vendor attached. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_ids[0] if vendor_ids else add_vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="attach_project_vendor",
                payload={"project_id": project_id, "vendor_ids": vendor_ids, "reason": reason},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="projects",
            event_type="project_vendor_add",
            payload={"project_id": project_id, "vendor_id": add_vendor_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not attach vendor: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{project_id}/offerings/add")
async def project_add_offering(request: Request, project_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/projects/{project_id}/offerings")))
    add_offering_id = str(form.get("offering_id", "")).strip()
    reason = str(form.get("reason", "")).strip() or "Quick add offering"

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to add offerings.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not add_offering_id:
        add_flash(request, "Select an offering to add.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    project = repo.get_project_by_id(project_id)
    if project is None:
        add_flash(request, "Project not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    vendor_ids = [str(x) for x in (project.get("vendor_ids") or []) if str(x).strip()]
    offering_ids = [str(x) for x in (project.get("linked_offering_ids") or []) if str(x).strip()]
    if add_offering_id not in offering_ids:
        offering_ids.append(add_offering_id)

    try:
        if user.can_direct_apply:
            result = repo.update_project(
                vendor_id=None,
                project_id=project_id,
                actor_user_principal=user.user_principal,
                updates={},
                vendor_ids=vendor_ids,
                linked_offering_ids=offering_ids,
                reason=reason,
            )
            add_flash(
                request,
                f"Offering attached. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_ids[0] if vendor_ids else "",
                requestor_user_principal=user.user_principal,
                change_type="attach_project_offering",
                payload={
                    "project_id": project_id,
                    "vendor_ids": vendor_ids,
                    "linked_offering_ids": offering_ids,
                    "reason": reason,
                },
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="projects",
            event_type="project_offering_add",
            payload={"project_id": project_id, "offering_id": add_offering_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not attach offering: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


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


@router.post("/{project_id}/docs/link")
async def project_doc_link_submit(request: Request, project_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/projects/{project_id}/docs")))

    project = repo.get_project_by_id(project_id)
    if project is None:
        add_flash(request, "Project not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to add document links.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    project_vendor_ids = [str(x).strip() for x in (project.get("vendor_ids") or []) if str(x).strip()]
    change_vendor_id = project_vendor_ids[0] if project_vendor_ids else str(project.get("vendor_id") or "").strip()
    try:
        payload = _prepare_doc_payload(dict(form))
        if user.can_direct_apply:
            doc_id = repo.create_doc_link(
                entity_type="project",
                entity_id=project_id,
                doc_title=payload["doc_title"],
                doc_url=payload["doc_url"],
                doc_type=payload["doc_type"],
                tags=payload["tags"] or None,
                owner=payload["owner"] or None,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Document link added: {payload['doc_title']}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=change_vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="create_doc_link",
                payload={"entity_type": "project", "entity_id": project_id, **payload},
            )
            doc_id = ""
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="projects",
            event_type="doc_link_create",
            payload={
                "project_id": project_id,
                "entity_type": "project",
                "doc_id": doc_id or None,
                "doc_type": payload["doc_type"],
            },
        )
    except Exception as exc:
        add_flash(request, f"Could not add document link: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


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


@router.post("/{project_id}/notes/add")
async def project_note_add(request: Request, project_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/projects/{project_id}/notes")))
    note_text = str(form.get("note_text", "")).strip()

    project = repo.get_project_by_id(project_id)
    if project is None:
        add_flash(request, "Project not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    vendor_id = str(project.get("vendor_id") or "")

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to add notes.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not note_text:
        add_flash(request, "Note text is required.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        if user.can_direct_apply:
            note_id = repo.add_project_note(
                vendor_id=vendor_id,
                project_id=project_id,
                note_text=note_text,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Project note added: {note_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_project_note",
                payload={"project_id": project_id, "note_text": note_text},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")

        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="projects",
            event_type="project_note_add",
            payload={"project_id": project_id, "vendor_id": vendor_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not add project note: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)
