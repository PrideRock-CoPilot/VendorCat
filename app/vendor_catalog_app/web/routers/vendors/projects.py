from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.core.defaults import DEFAULT_PROJECT_TYPE
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.vendors.common import (
    _dedupe_ordered,
    _project_demo_select_options,
    _request_scope_vendor_id,
    _safe_return_to,
    _selected_project_offering_rows,
    _selected_project_vendor_rows,
    _vendor_base_context,
    _write_blocked,
)
from vendor_catalog_app.web.routers.vendors.constants import (
    PROJECT_DEMO_OUTCOMES,
    PROJECT_DEMO_TYPES,
    PROJECT_STATUSES,
    PROJECT_TYPES_FALLBACK,
    VENDOR_DEFAULT_RETURN_TO,
)
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/vendors")


def _normalize_project_status(value: str) -> str:
    status = value.strip().lower()
    if status not in PROJECT_STATUSES:
        raise ValueError(f"Project status must be one of: {', '.join(PROJECT_STATUSES)}")
    return status


def _project_type_options(repo) -> list[str]:
    options = [str(item).strip().lower() for item in repo.list_project_type_options() if str(item).strip()]
    return options or list(PROJECT_TYPES_FALLBACK)


def _normalize_project_type(repo, value: str) -> str:
    allowed = _project_type_options(repo)
    project_type = value.strip().lower() if value else DEFAULT_PROJECT_TYPE
    if project_type not in set(allowed):
        raise ValueError(f"Project type must be one of: {', '.join(allowed)}")
    return project_type
@router.get("/{vendor_id}/projects")
def vendor_projects_page(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "projects", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    projects = repo.list_projects(vendor_id).to_dict("records")
    for row in projects:
        project_id = str(row.get("project_id"))
        row["_open_link"] = (
            f"/projects/{project_id}/summary?return_to="
            f"{quote(f'/vendors/{vendor_id}/projects', safe='')}"
        )
        row["_edit_link"] = (
            f"/vendors/{vendor_id}/projects/{project_id}/edit?return_to={quote(base['return_to'], safe='')}"
        )

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Projects",
        active_nav="projects",
        extra={
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "summary": base["summary"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "projects": projects,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_projects.html", context)


@router.get("/{vendor_id}/projects/new")
def project_new_form(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "projects", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)
    if _write_blocked(base["user"]):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/projects?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )
    if not base["user"].can_edit:
        add_flash(request, "You do not have permission to create projects.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/projects?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )

    selected_vendor_rows = _selected_project_vendor_rows(repo, [vendor_id])
    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - New Project",
        active_nav="projects",
        extra={
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "project_types": _project_type_options(repo),
            "project_statuses": PROJECT_STATUSES,
            "selected_vendor_rows": selected_vendor_rows,
            "selected_offering_rows": [],
            "form_action": f"/vendors/{vendor_id}/projects/new",
        },
    )
    return request.app.state.templates.TemplateResponse(request, "project_new.html", context)


@router.post("/{vendor_id}/projects/new")
@require_permission("project_create")
async def project_new_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    linked_offerings = _dedupe_ordered([str(x).strip() for x in form.getlist("linked_offerings") if str(x).strip()])
    linked_vendors = _dedupe_ordered([str(x).strip() for x in form.getlist("linked_vendors") if str(x).strip()])
    if vendor_id not in linked_vendors:
        linked_vendors.insert(0, vendor_id)
    if linked_offerings:
        offering_rows = repo.get_offerings_by_ids(linked_offerings).to_dict("records")
        for row in offering_rows:
            offering_vendor_id = str(row.get("vendor_id") or "").strip()
            if offering_vendor_id and offering_vendor_id not in linked_vendors:
                linked_vendors.append(offering_vendor_id)
    linked_vendors = _dedupe_ordered(linked_vendors)
    try:
        project_payload = {
            "vendor_id": vendor_id,
            "vendor_ids": linked_vendors,
            "project_name": str(form.get("project_name", "")).strip(),
            "project_type": _normalize_project_type(repo, str(form.get("project_type", "other"))),
            "status": _normalize_project_status(str(form.get("status", "draft"))),
            "start_date": str(form.get("start_date", "")).strip() or None,
            "target_date": str(form.get("target_date", "")).strip() or None,
            "owner_principal": str(form.get("owner_principal", "")).strip() or None,
            "description": str(form.get("description", "")).strip() or None,
            "linked_offering_ids": linked_offerings,
        }
        if user.can_apply_change("create_project"):
            project_id = repo.create_project(
                vendor_id=vendor_id,
                vendor_ids=linked_vendors,
                actor_user_principal=user.user_principal,
                project_name=project_payload["project_name"],
                project_type=project_payload["project_type"],
                status=project_payload["status"],
                start_date=project_payload["start_date"],
                target_date=project_payload["target_date"],
                owner_principal=project_payload["owner_principal"],
                description=project_payload["description"],
                linked_offering_ids=linked_offerings,
            )
            repo.log_usage_event(
                user_principal=user.user_principal,
                page_name="vendor_projects",
                event_type="project_create",
                payload={"vendor_id": vendor_id, "project_id": project_id},
            )
            add_flash(request, f"Project created: {project_id}", "success")
            return RedirectResponse(
                url=f"/projects/{project_id}/summary?return_to={quote(return_to, safe='')}",
                status_code=303,
            )
        request_id = repo.create_vendor_change_request(
            vendor_id=_request_scope_vendor_id(vendor_id),
            requestor_user_principal=user.user_principal,
            change_type="create_project",
            payload=project_payload,
        )
        add_flash(request, f"Pending change request submitted: {request_id}", "success")
        return RedirectResponse(url="/workflows?status=pending", status_code=303)
    except Exception as exc:
        add_flash(request, f"Could not create project: {exc}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/projects/new?return_to={quote(return_to, safe='')}",
            status_code=303,
        )


@router.get("/{vendor_id}/projects/{project_id}")
def project_detail_page(request: Request, vendor_id: str, project_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    return RedirectResponse(
        url=f"/projects/{project_id}/summary?return_to={quote(_safe_return_to(return_to), safe='')}",
        status_code=302,
    )


@router.get("/{vendor_id}/projects/{project_id}/edit")
def project_edit_form(request: Request, vendor_id: str, project_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "projects", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)
    project = repo.get_project(vendor_id, project_id)
    if project is None:
        add_flash(request, "Project not found for vendor.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/projects?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )
    if _write_blocked(base["user"]):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/projects/{project_id}/summary?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )
    if not base["user"].can_edit:
        add_flash(request, "You do not have permission to edit projects.", "error")
        return RedirectResponse(
            url=f"/projects/{project_id}/summary?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )

    project_vendor_ids = _dedupe_ordered([str(x).strip() for x in (project.get("vendor_ids") or []) if str(x).strip()])
    project_offering_ids = _dedupe_ordered(
        [str(x).strip() for x in (project.get("linked_offering_ids") or []) if str(x).strip()]
    )
    if vendor_id and vendor_id not in project_vendor_ids:
        project_vendor_ids.insert(0, vendor_id)
    selected_vendor_rows = _selected_project_vendor_rows(repo, project_vendor_ids)
    selected_offering_rows = _selected_project_offering_rows(repo, project_offering_ids)
    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Edit Project",
        active_nav="projects",
        extra={
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "project": project,
            "selected_vendor_rows": selected_vendor_rows,
            "selected_offering_rows": selected_offering_rows,
            "return_to": base["return_to"],
            "project_types": _project_type_options(repo),
            "project_statuses": PROJECT_STATUSES,
            "form_action": f"/vendors/{vendor_id}/projects/{project_id}/edit",
        },
    )
    return request.app.state.templates.TemplateResponse(request, "project_edit.html", context)


@router.post("/{vendor_id}/projects/{project_id}/edit")
async def project_edit_submit(request: Request, vendor_id: str, project_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/projects/{project_id}/summary?return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not user.can_edit:
        add_flash(request, "You do not have permission to edit projects.", "error")
        return RedirectResponse(
            url=f"/projects/{project_id}/summary?return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    linked_offerings = _dedupe_ordered([str(x).strip() for x in form.getlist("linked_offerings") if str(x).strip()])
    linked_vendors = _dedupe_ordered([str(x).strip() for x in form.getlist("linked_vendors") if str(x).strip()])
    if vendor_id not in linked_vendors:
        linked_vendors.insert(0, vendor_id)
    if linked_offerings:
        offering_rows = repo.get_offerings_by_ids(linked_offerings).to_dict("records")
        for row in offering_rows:
            offering_vendor_id = str(row.get("vendor_id") or "").strip()
            if offering_vendor_id and offering_vendor_id not in linked_vendors:
                linked_vendors.append(offering_vendor_id)
    linked_vendors = _dedupe_ordered(linked_vendors)
    updates = {
        "project_name": str(form.get("project_name", "")).strip(),
        "project_type": str(form.get("project_type", "other")),
        "status": str(form.get("status", "draft")),
        "start_date": str(form.get("start_date", "")).strip() or None,
        "target_date": str(form.get("target_date", "")).strip() or None,
        "owner_principal": str(form.get("owner_principal", "")).strip() or None,
        "description": str(form.get("description", "")).strip() or None,
    }

    try:
        updates["project_type"] = _normalize_project_type(repo, str(updates.get("project_type", "other")))
        updates["status"] = _normalize_project_status(str(updates.get("status", "draft")))
        if user.can_apply_change("update_project"):
            result = repo.update_project(
                vendor_id=vendor_id,
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
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_project",
                payload={"project_id": project_id, "updates": updates, "linked_offering_ids": linked_offerings, "reason": reason},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_project_detail",
            event_type="project_update",
            payload={"vendor_id": vendor_id, "project_id": project_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not update project: {exc}", "error")

    return RedirectResponse(
        url=f"/projects/{project_id}/summary?return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.get("/{vendor_id}/projects/{project_id}/demos/new")
def project_demo_new_form(request: Request, vendor_id: str, project_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "projects", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)
    project = repo.get_project(vendor_id, project_id)
    if project is None:
        add_flash(request, "Project not found for vendor.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/projects?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )
    if _write_blocked(base["user"]):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/projects/{project_id}/demos?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )
    if not base["user"].can_edit:
        add_flash(request, "You do not have permission to add demos.", "error")
        return RedirectResponse(
            url=f"/projects/{project_id}/demos?return_to={quote(base['return_to'], safe='')}",
            status_code=303,
        )

    offerings = repo.get_vendor_offerings(vendor_id).to_dict("records")
    vendor_demos = repo.get_vendor_demos(vendor_id).to_dict("records")
    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - New Project Demo",
        active_nav="projects",
        extra={
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "project": project,
            "return_to": base["return_to"],
            "offerings": offerings,
            "project_demo_types": PROJECT_DEMO_TYPES,
            "project_demo_outcomes": PROJECT_DEMO_OUTCOMES,
            "demo_map_options": _project_demo_select_options(vendor_demos),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "project_demo_new.html", context)


@router.post("/{vendor_id}/projects/{project_id}/demos/new")
async def project_demo_new_submit(request: Request, vendor_id: str, project_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to add demos.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    linked_vendor_demo_id = str(form.get("linked_vendor_demo_id", "")).strip()
    try:
        demo_payload = {
            "vendor_id": vendor_id,
            "project_id": project_id,
            "demo_name": str(form.get("demo_name", "")).strip(),
            "demo_datetime_start": str(form.get("demo_datetime_start", "")).strip() or None,
            "demo_datetime_end": str(form.get("demo_datetime_end", "")).strip() or None,
            "demo_type": str(form.get("demo_type", "live")).strip() or "live",
            "outcome": str(form.get("outcome", "unknown")).strip() or "unknown",
            "score": float(str(form.get("score", "")).strip()) if str(form.get("score", "")).strip() else None,
            "attendees_internal": str(form.get("attendees_internal", "")).strip() or None,
            "attendees_vendor": str(form.get("attendees_vendor", "")).strip() or None,
            "notes": str(form.get("notes", "")).strip() or None,
            "followups": str(form.get("followups", "")).strip() or None,
            "linked_offering_id": str(form.get("linked_offering_id", "")).strip() or None,
            "linked_vendor_demo_id": linked_vendor_demo_id or None,
        }
        if user.can_apply_change("create_project_demo"):
            demo_id = repo.create_project_demo(
                vendor_id=vendor_id,
                project_id=project_id,
                actor_user_principal=user.user_principal,
                demo_name=demo_payload["demo_name"],
                demo_datetime_start=demo_payload["demo_datetime_start"],
                demo_datetime_end=demo_payload["demo_datetime_end"],
                demo_type=demo_payload["demo_type"],
                outcome=demo_payload["outcome"],
                score=demo_payload["score"],
                attendees_internal=demo_payload["attendees_internal"],
                attendees_vendor=demo_payload["attendees_vendor"],
                notes=demo_payload["notes"],
                followups=demo_payload["followups"],
                linked_offering_id=demo_payload["linked_offering_id"],
                linked_vendor_demo_id=demo_payload["linked_vendor_demo_id"],
            )
            repo.log_usage_event(
                user_principal=user.user_principal,
                page_name="vendor_project_detail",
                event_type="project_demo_create",
                payload={"vendor_id": vendor_id, "project_id": project_id, "project_demo_id": demo_id},
            )
            add_flash(request, f"Project demo created: {demo_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=_request_scope_vendor_id(vendor_id),
                requestor_user_principal=user.user_principal,
                change_type="create_project_demo",
                payload=demo_payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
    except Exception as exc:
        add_flash(request, f"Could not create project demo: {exc}", "error")
    return RedirectResponse(
        url=f"/projects/{project_id}/demos?return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/projects/{project_id}/demos/map")
async def project_demo_map_submit(request: Request, vendor_id: str, project_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))
    vendor_demo_id = str(form.get("vendor_demo_id", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to map demos.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not vendor_demo_id:
        add_flash(request, "Vendor demo is required.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        demo_id = repo.map_vendor_demo_to_project(
            vendor_id=vendor_id,
            project_id=project_id,
            vendor_demo_id=vendor_demo_id,
            actor_user_principal=user.user_principal,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_project_detail",
            event_type="project_demo_map",
            payload={"vendor_id": vendor_id, "project_id": project_id, "vendor_demo_id": vendor_demo_id, "project_demo_id": demo_id},
        )
        add_flash(request, f"Vendor demo mapped to project: {demo_id}", "success")
    except Exception as exc:
        add_flash(request, f"Could not map vendor demo: {exc}", "error")
    return RedirectResponse(
        url=f"/projects/{project_id}/demos?return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/projects/{project_id}/demos/{demo_id}/update")
async def project_demo_update_submit(request: Request, vendor_id: str, project_id: str, demo_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to update demos.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    updates = {
        "demo_name": str(form.get("demo_name", "")).strip(),
        "demo_datetime_start": str(form.get("demo_datetime_start", "")).strip() or None,
        "demo_datetime_end": str(form.get("demo_datetime_end", "")).strip() or None,
        "demo_type": str(form.get("demo_type", "")).strip() or None,
        "outcome": str(form.get("outcome", "")).strip() or None,
        "score": float(str(form.get("score", "")).strip()) if str(form.get("score", "")).strip() else None,
        "attendees_internal": str(form.get("attendees_internal", "")).strip() or None,
        "attendees_vendor": str(form.get("attendees_vendor", "")).strip() or None,
        "notes": str(form.get("notes", "")).strip() or None,
        "followups": str(form.get("followups", "")).strip() or None,
        "linked_offering_id": str(form.get("linked_offering_id", "")).strip() or None,
    }
    updates = {k: v for k, v in updates.items() if v is not None and v != ""}

    try:
        if user.can_apply_change("update_project_demo"):
            result = repo.update_project_demo(
                vendor_id=vendor_id,
                project_id=project_id,
                project_demo_id=demo_id,
                actor_user_principal=user.user_principal,
                updates=updates,
                reason=reason,
            )
            add_flash(
                request,
                f"Project demo updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_project_demo",
                payload={"project_id": project_id, "project_demo_id": demo_id, "updates": updates, "reason": reason},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_project_detail",
            event_type="project_demo_update",
            payload={"vendor_id": vendor_id, "project_id": project_id, "project_demo_id": demo_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not update project demo: {exc}", "error")
    return RedirectResponse(
        url=f"/projects/{project_id}/demos?return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/projects/{project_id}/demos/{demo_id}/remove")
async def project_demo_remove_submit(request: Request, vendor_id: str, project_id: str, demo_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to remove demos.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        if user.can_apply_change("remove_project_demo"):
            repo.remove_project_demo(
                vendor_id=vendor_id,
                project_id=project_id,
                project_demo_id=demo_id,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, "Project demo removed.", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="remove_project_demo",
                payload={"project_id": project_id, "project_demo_id": demo_id},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
    except Exception as exc:
        add_flash(request, f"Could not remove project demo: {exc}", "error")
    return RedirectResponse(
        url=f"/projects/{project_id}/demos?return_to={quote(return_to, safe='')}",
        status_code=303,
    )


