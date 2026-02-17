from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.projects.common import (
    _dedupe_ordered,
    _normalize_project_status,
    _normalize_project_type,
    _resolve_owner_principal_input,
    _request_scope_vendor_id,
    _safe_return_to,
)
from vendor_catalog_app.web.routers.vendors.constants import (
    PROJECT_OWNER_CHANGE_REASON_OPTIONS,
    PROJECT_UPDATE_REASON_OPTIONS,
)
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/projects")

@router.post("/new")
@require_permission("project_create")
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

    linked_vendors = _dedupe_ordered([str(x).strip() for x in form.getlist("linked_vendors") if str(x).strip()])
    linked_offerings = _dedupe_ordered([str(x).strip() for x in form.getlist("linked_offerings") if str(x).strip()])
    try:
        resolved_owner_principal = _resolve_owner_principal_input(repo, form)
    except Exception as exc:
        add_flash(request, str(exc), "error")
        return RedirectResponse(url=f"/projects/new?return_to={quote(return_to, safe='')}", status_code=303)
    if linked_offerings:
        offering_rows = repo.get_offerings_by_ids(linked_offerings).to_dict("records")
        for row in offering_rows:
            offering_vendor_id = str(row.get("vendor_id") or "").strip()
            if offering_vendor_id and offering_vendor_id not in linked_vendors:
                linked_vendors.append(offering_vendor_id)
    linked_vendors = _dedupe_ordered(linked_vendors)
    try:
        project_payload = {
            "vendor_ids": linked_vendors,
            "project_name": str(form.get("project_name", "")).strip(),
            "project_type": _normalize_project_type(repo, str(form.get("project_type", "other"))),
            "status": _normalize_project_status(str(form.get("status", "draft"))),
            "start_date": str(form.get("start_date", "")).strip() or None,
            "target_date": str(form.get("target_date", "")).strip() or None,
            "owner_principal": resolved_owner_principal,
            "description": str(form.get("description", "")).strip() or None,
            "linked_offering_ids": linked_offerings,
        }
        if user.can_apply_change("create_project"):
            project_id = repo.create_project(
                vendor_id=None,
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
                page_name="projects",
                event_type="project_create",
                payload={"project_id": project_id, "vendor_count": len(linked_vendors)},
            )
            add_flash(request, f"Project created: {project_id}", "success")
            return RedirectResponse(
                url=f"/projects/{project_id}/summary?return_to={quote(return_to, safe='')}",
                status_code=303,
            )
        request_id = repo.create_vendor_change_request(
            vendor_id=_request_scope_vendor_id(linked_vendors[0] if linked_vendors else ""),
            requestor_user_principal=user.user_principal,
            change_type="create_project",
            payload=project_payload,
        )
        add_flash(request, f"Pending change request submitted: {request_id}", "success")
        return RedirectResponse(url="/workflows?status=pending", status_code=303)
    except Exception as exc:
        add_flash(request, f"Could not create project: {exc}", "error")
        return RedirectResponse(url=f"/projects/new?return_to={quote(return_to, safe='')}", status_code=303)



@router.post("/{project_id}/edit")
@require_permission("project_edit")
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

    linked_vendors = _dedupe_ordered([str(x).strip() for x in form.getlist("linked_vendors") if str(x).strip()])
    linked_offerings = _dedupe_ordered([str(x).strip() for x in form.getlist("linked_offerings") if str(x).strip()])
    try:
        resolved_owner_principal = _resolve_owner_principal_input(repo, form)
    except Exception as exc:
        add_flash(request, str(exc), "error")
        return RedirectResponse(url=f"/projects/{project_id}/summary?return_to={quote(return_to, safe='')}", status_code=303)
    if linked_offerings:
        offering_rows = repo.get_offerings_by_ids(linked_offerings).to_dict("records")
        for row in offering_rows:
            offering_vendor_id = str(row.get("vendor_id") or "").strip()
            if offering_vendor_id and offering_vendor_id not in linked_vendors:
                linked_vendors.append(offering_vendor_id)
    linked_vendors = _dedupe_ordered(linked_vendors)
    updates = {
        "project_name": str(form.get("project_name", "")).strip(),
        "project_type": _normalize_project_type(repo, str(form.get("project_type", "other"))),
        "status": _normalize_project_status(str(form.get("status", "draft"))),
        "start_date": str(form.get("start_date", "")).strip() or None,
        "target_date": str(form.get("target_date", "")).strip() or None,
        "owner_principal": resolved_owner_principal,
        "description": str(form.get("description", "")).strip() or None,
    }

    try:
        if user.can_apply_change("update_project"):
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
                vendor_id=_request_scope_vendor_id(cr_vendor_id),
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
@require_permission("project_owner_update")
async def project_owner_update(request: Request, project_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/projects/{project_id}/ownership")))
    try:
        owner_principal = _resolve_owner_principal_input(repo, form)
    except Exception as exc:
        add_flash(request, str(exc), "error")
        return RedirectResponse(url=return_to, status_code=303)
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
        if user.can_apply_change("update_project_owner"):
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
                vendor_id=_request_scope_vendor_id(vendor_ids[0] if vendor_ids else ""),
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



