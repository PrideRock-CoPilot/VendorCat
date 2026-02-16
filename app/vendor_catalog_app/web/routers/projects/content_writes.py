from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.projects.common import (
    _prepare_doc_payload,
    _request_scope_vendor_id,
    _safe_return_to,
)
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/projects")

@router.post("/{project_id}/docs/link")
@require_permission("project_doc_create")
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
        payload = _prepare_doc_payload(
            repo,
            {
                "doc_url": str(form.get("doc_url", "")),
                "doc_type": str(form.get("doc_type", "")),
                "doc_title": str(form.get("doc_title", "")),
                "tags": [str(v) for v in form.getlist("tags") if str(v).strip()],
                "owner": str(form.get("owner", "")),
            },
            actor_user_principal=user.user_principal,
        )
        if user.can_apply_change("create_doc_link"):
            doc_id = repo.create_doc_link(
                entity_type="project",
                entity_id=project_id,
                doc_title=payload["doc_title"],
                doc_url=payload["doc_url"],
                doc_type=payload["doc_type"],
                tags=payload["tags"] or None,
                doc_fqdn=payload["doc_fqdn"] or None,
                owner=payload["owner"] or None,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Document link added: {payload['doc_title']}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=_request_scope_vendor_id(change_vendor_id),
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
                    "doc_fqdn": payload["doc_fqdn"] or None,
                },
            )
    except Exception as exc:
        add_flash(request, f"Could not add document link: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)



@router.post("/{project_id}/notes/add")
@require_permission("project_note_create")
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
        if user.can_apply_change("add_project_note"):
            note_id = repo.add_project_note(
                vendor_id=vendor_id,
                project_id=project_id,
                note_text=note_text,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Project note added: {note_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=_request_scope_vendor_id(vendor_id),
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

