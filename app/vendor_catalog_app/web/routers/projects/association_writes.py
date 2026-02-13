from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.flash import add_flash
from vendor_catalog_app.web.services import get_repo, get_user_context
from vendor_catalog_app.web.routers.projects.common import (
    _dedupe_ordered,
    _normalize_project_status,
    _normalize_project_type,
    _prepare_doc_payload,
    _request_scope_vendor_id,
    _safe_return_to,
    _safe_vendor_id,
)


router = APIRouter(prefix="/projects")

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
    safe_vendor_id = _safe_vendor_id(repo, add_vendor_id)
    if not safe_vendor_id:
        add_flash(request, "Selected vendor was not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    add_vendor_id = safe_vendor_id

    project = repo.get_project_by_id(project_id)
    if project is None:
        add_flash(request, "Project not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    vendor_ids = _dedupe_ordered([str(x) for x in (project.get("vendor_ids") or []) if str(x).strip()])
    if add_vendor_id not in vendor_ids:
        vendor_ids.append(add_vendor_id)
    try:
        if user.can_apply_change("attach_project_vendor"):
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
                vendor_id=_request_scope_vendor_id(vendor_ids[0] if vendor_ids else add_vendor_id),
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

    offering_rows = repo.get_offerings_by_ids([add_offering_id]).to_dict("records")
    if not offering_rows:
        add_flash(request, "Selected offering was not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    offering_vendor_id = str(offering_rows[0].get("vendor_id") or "").strip()

    vendor_ids = _dedupe_ordered([str(x) for x in (project.get("vendor_ids") or []) if str(x).strip()])
    offering_ids = _dedupe_ordered([str(x) for x in (project.get("linked_offering_ids") or []) if str(x).strip()])
    if offering_vendor_id and offering_vendor_id not in vendor_ids:
        vendor_ids.append(offering_vendor_id)
    if add_offering_id not in offering_ids:
        offering_ids.append(add_offering_id)

    try:
        if user.can_apply_change("attach_project_offering"):
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
                vendor_id=_request_scope_vendor_id(vendor_ids[0] if vendor_ids else ""),
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



