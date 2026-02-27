from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.core.defaults import DEFAULT_DOC_TITLE_MAX_LENGTH
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.vendors.common import (
    _request_scope_vendor_id,
    _safe_return_to,
    _write_blocked,
)
from vendor_catalog_app.web.routers.vendors.constants import VENDOR_DEFAULT_RETURN_TO
from vendor_catalog_app.web.utils.doc_links import (
    extract_doc_fqdn,
    normalize_doc_tags,
    suggest_doc_title,
    suggest_doc_type,
)
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/vendors")


def _normalize_doc_source(repo, value: str, *, doc_url: str = "") -> str:
    allowed = {str(item).strip().lower() for item in repo.list_doc_source_options() if str(item).strip()}
    if not allowed:
        raise ValueError("Document source lookup options are not configured.")
    source = str(value or "").strip().lower()
    if source:
        if source not in allowed:
            raise ValueError(f"Source must be one of: {', '.join(sorted(allowed))}")
        return source

    inferred = suggest_doc_type(doc_url).strip().lower()
    if inferred in allowed:
        return inferred
    if "other" in allowed:
        return "other"
    return sorted(allowed)[0]


def _prepare_doc_payload(
    repo,
    form_data: dict[str, object],
    *,
    actor_user_principal: str,
) -> dict[str, str]:
    doc_url = str(form_data.get("doc_url", "")).strip()
    doc_type = _normalize_doc_source(repo, str(form_data.get("doc_type", "")), doc_url=doc_url)
    doc_title = str(form_data.get("doc_title", "")).strip()
    raw_tags = form_data.get("tags")
    owner = str(form_data.get("owner", "")).strip() or str(actor_user_principal or "").strip()
    doc_fqdn = extract_doc_fqdn(doc_url)

    if not doc_url:
        raise ValueError("Document link is required.")
    if not doc_title:
        doc_title = suggest_doc_title(doc_url)
    if not doc_title:
        raise ValueError("Document title is required.")
    if len(doc_title) > DEFAULT_DOC_TITLE_MAX_LENGTH:
        doc_title = doc_title[:DEFAULT_DOC_TITLE_MAX_LENGTH].rstrip()
    owner_login = repo.resolve_user_login_identifier(owner)
    if not owner_login:
        raise ValueError("Owner must exist in the app user directory.")

    collected_tags: list[str] = []
    if isinstance(raw_tags, list):
        collected_tags.extend(str(item or "") for item in raw_tags)
    elif raw_tags is not None:
        collected_tags.append(str(raw_tags or ""))
    normalized_tags = normalize_doc_tags(collected_tags, doc_type="", fqdn="", doc_url="")
    allowed_tags = {str(item).strip().lower() for item in repo.list_doc_tag_options() if str(item).strip()}
    invalid_tags = [tag for tag in normalized_tags if tag not in allowed_tags]
    if invalid_tags:
        raise ValueError(f"Tags must be selected from admin-managed options: {', '.join(sorted(allowed_tags))}")
    return {
        "doc_url": doc_url,
        "doc_type": doc_type,
        "doc_title": doc_title,
        "tags": ",".join(normalized_tags),
        "owner": owner_login,
        "doc_fqdn": doc_fqdn,
    }
def _entity_exists_for_doc(repo, vendor_id: str, entity_type: str, entity_id: str) -> bool:
    if entity_type == "vendor":
        return not repo.get_vendor_profile(vendor_id).empty and str(entity_id) == str(vendor_id)
    if entity_type == "project":
        return repo.project_belongs_to_vendor(vendor_id, entity_id)
    if entity_type == "offering":
        return repo.offering_belongs_to_vendor(vendor_id, entity_id)
    if entity_type == "demo":
        project_rows = repo.list_projects(vendor_id).to_dict("records")
        for row in project_rows:
            demos = repo.list_project_demos(vendor_id, str(row.get("project_id")))
            if not demos.empty and not demos[demos["project_demo_id"].astype(str) == str(entity_id)].empty:
                return True
        return False
    return False


async def _create_doc_link_for_entity(
    request: Request,
    *,
    form,
    vendor_id: str,
    entity_type: str,
    entity_id: str,
    page_name: str,
    event_payload: dict[str, str],
    redirect_url: str,
):
    repo = get_repo()
    user = get_user_context(request)
    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))
    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to or redirect_url, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to add document links.", "error")
        return RedirectResponse(url=return_to or redirect_url, status_code=303)
    if not _entity_exists_for_doc(repo, vendor_id, entity_type, entity_id):
        add_flash(request, "Target record was not found for this vendor.", "error")
        return RedirectResponse(url=return_to or redirect_url, status_code=303)

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
                entity_type=entity_type,
                entity_id=entity_id,
                doc_title=payload["doc_title"],
                doc_url=payload["doc_url"],
                doc_type=payload["doc_type"],
                tags=payload["tags"] or None,
                doc_fqdn=payload["doc_fqdn"] or None,
                owner=payload["owner"] or None,
                actor_user_principal=user.user_principal,
            )
            repo.log_usage_event(
                user_principal=user.user_principal,
                page_name=page_name,
                event_type="doc_link_create",
                payload={**event_payload, "doc_id": doc_id, "entity_type": entity_type},
            )
            add_flash(request, f"Document link added: {payload['doc_title']}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=_request_scope_vendor_id(vendor_id),
                requestor_user_principal=user.user_principal,
                change_type="create_doc_link",
                payload={
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "doc_title": payload["doc_title"],
                    "doc_url": payload["doc_url"],
                    "doc_type": payload["doc_type"],
                    "tags": payload["tags"] or None,
                    "doc_fqdn": payload["doc_fqdn"] or None,
                    "owner": payload["owner"] or None,
                },
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
    except Exception as exc:
        add_flash(request, f"Could not add document link: {exc}", "error")
    target = return_to or redirect_url
    return RedirectResponse(url=target, status_code=303)


@router.post("/{vendor_id}/docs/link")
@require_permission("vendor_doc_create")
async def vendor_doc_link_submit(request: Request, vendor_id: str):
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/summary")))
    return await _create_doc_link_for_entity(
        request,
        form=form,
        vendor_id=vendor_id,
        entity_type="vendor",
        entity_id=vendor_id,
        page_name="vendor_summary",
        event_payload={"vendor_id": vendor_id},
        redirect_url=f"/vendors/{vendor_id}/summary?return_to={quote(return_to, safe='')}",
    )


@router.post("/{vendor_id}/projects/{project_id}/docs/link")
@require_permission("project_doc_create")
async def project_doc_link_submit(request: Request, vendor_id: str, project_id: str):
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/projects/{project_id}/docs")))
    return await _create_doc_link_for_entity(
        request,
        form=form,
        vendor_id=vendor_id,
        entity_type="project",
        entity_id=project_id,
        page_name="vendor_project_detail",
        event_payload={"vendor_id": vendor_id, "project_id": project_id},
        redirect_url=f"/vendors/{vendor_id}/projects/{project_id}?return_to={quote(return_to, safe='')}",
    )


@router.post("/{vendor_id}/offerings/{offering_id}/docs/link")
@require_permission("offering_doc_create")
async def offering_doc_link_submit(request: Request, vendor_id: str, offering_id: str):
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings/{offering_id}")))
    return await _create_doc_link_for_entity(
        request,
        form=form,
        vendor_id=vendor_id,
        entity_type="offering",
        entity_id=offering_id,
        page_name="vendor_offering_detail",
        event_payload={"vendor_id": vendor_id, "offering_id": offering_id},
        redirect_url=f"/vendors/{vendor_id}/offerings/{offering_id}?return_to={quote(return_to, safe='')}",
    )


@router.post("/{vendor_id}/projects/{project_id}/demos/{demo_id}/docs/link")
@require_permission("demo_doc_create")
async def project_demo_doc_link_submit(request: Request, vendor_id: str, project_id: str, demo_id: str):
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/projects/{project_id}/demos")))
    return await _create_doc_link_for_entity(
        request,
        form=form,
        vendor_id=vendor_id,
        entity_type="demo",
        entity_id=demo_id,
        page_name="vendor_project_detail",
        event_payload={"vendor_id": vendor_id, "project_id": project_id, "project_demo_id": demo_id},
        redirect_url=f"/vendors/{vendor_id}/projects/{project_id}?return_to={quote(return_to, safe='')}",
    )


@router.post("/docs/{doc_id}/remove")
@require_permission("doc_delete")
async def doc_link_remove_submit(request: Request, doc_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))
    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to remove document links.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    doc = repo.get_doc_link(doc_id)
    if not doc:
        add_flash(request, "Document link not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    try:
        if user.can_apply_change("remove_doc_link"):
            repo.remove_doc_link(doc_id=doc_id, actor_user_principal=user.user_principal)
            add_flash(request, "Document link removed.", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=_request_scope_vendor_id(str(form.get("vendor_id", "")).strip() or str(doc.get("entity_id"))),
                requestor_user_principal=user.user_principal,
                change_type="remove_doc_link",
                payload={"doc_id": doc_id},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_docs",
            event_type="doc_link_remove",
            payload={"doc_id": doc_id, "entity_type": str(doc.get("entity_type"))},
        )
    except Exception as exc:
        add_flash(request, f"Could not remove document link: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)

