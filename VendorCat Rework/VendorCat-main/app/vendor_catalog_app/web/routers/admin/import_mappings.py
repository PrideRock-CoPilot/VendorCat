from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.core.activity import ensure_session_started, log_page_view
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.admin.common import (
    ADMIN_SECTION_IMPORT_MAPPINGS,
    _admin_redirect_url,
)
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/admin")

_STATUS_OPTIONS = {"pending", "approved", "rejected", "all"}


def _normalize_status(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _STATUS_OPTIONS:
        return normalized
    return "pending"


def _render(
    request: Request,
    *,
    user,
    queue_status: str,
    request_rows: list[dict[str, Any]],
    selected_request: dict[str, Any] | None,
    approved_profiles: list[dict[str, Any]],
) -> Any:
    context = base_template_context(
        request=request,
        context=user,
        title="Admin Import Mappings",
        active_nav="admin",
        extra={
            "admin_active_page": ADMIN_SECTION_IMPORT_MAPPINGS,
            "queue_status": queue_status,
            "request_rows": list(request_rows or []),
            "selected_request": dict(selected_request or {}),
            "approved_profiles": list(approved_profiles or []),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "admin/import_mappings.html", context)


def _sync_job_mapping_status(*, repo, request_row: dict[str, Any], actor: str, approved_profile_id: str = "") -> None:
    import_job_id = str(request_row.get("import_job_id") or "").strip()
    if not import_job_id:
        return
    job = repo.get_import_job(import_job_id)
    if not isinstance(job, dict):
        return
    context = dict(job.get("context") or {})
    decision = str(request_row.get("status") or "").strip().lower()
    context["mapping_approval_status"] = decision
    context["mapping_request_status"] = decision
    context["mapping_request_id"] = str(request_row.get("profile_request_id") or "").strip()
    if decision == "approved":
        context["selected_mapping_profile_id"] = approved_profile_id
        repo.set_import_job_mapping_links(
            import_job_id=import_job_id,
            mapping_profile_id=approved_profile_id,
            mapping_request_id=str(request_row.get("profile_request_id") or "").strip(),
            actor_user_principal=actor,
        )
        current_status = str(job.get("status") or "").strip().lower()
        if current_status in {"uploaded", "mapping_preview", "mapping_pending_approval"}:
            repo.update_import_job_status(
                import_job_id=import_job_id,
                status="ready_to_stage",
                actor_user_principal=actor,
            )
    elif decision == "rejected":
        repo.set_import_job_mapping_links(
            import_job_id=import_job_id,
            mapping_profile_id="",
            mapping_request_id=str(request_row.get("profile_request_id") or "").strip(),
            actor_user_principal=actor,
        )
        current_status = str(job.get("status") or "").strip().lower()
        if current_status in {"uploaded", "mapping_pending_approval"}:
            repo.update_import_job_status(
                import_job_id=import_job_id,
                status="mapping_preview",
                actor_user_principal=actor,
            )
    repo.update_import_job_context(
        import_job_id=import_job_id,
        context=context,
        actor_user_principal=actor,
    )
    if hasattr(repo, "log_import_workflow_event"):
        old_status = str(job.get("status") or "").strip().lower()
        refreshed = repo.get_import_job(import_job_id) or {}
        new_status = str(refreshed.get("status") or old_status).strip().lower()
        repo.log_import_workflow_event(
            import_job_id=import_job_id,
            old_status=old_status,
            new_status=new_status,
            actor_user_principal=actor,
            notes=(
                f"job={import_job_id} source_system={str(job.get('source_system') or '').strip() or 'unknown'} "
                f"source_object={str(job.get('source_object') or '').strip() or '-'} actor={actor}; "
                f"mapping {decision}"
            ),
        )


@router.get("/import-mappings")
@require_permission("manage_import_mapping_profile")
async def admin_import_mappings(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Admin Import Mappings")
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    queue_status = _normalize_status(request.query_params.get("status"))
    selected_request_id = str(request.query_params.get("request_id") or "").strip()
    request_rows = list(
        repo.list_import_mapping_profile_requests(
            status="" if queue_status == "all" else queue_status,
            include_all=True,
            limit=400,
        )
        or []
    )
    selected_request = None
    if selected_request_id:
        selected_request = next(
            (row for row in request_rows if str(row.get("profile_request_id") or "").strip() == selected_request_id),
            None,
        )
        if selected_request is None:
            selected_request = repo.get_import_mapping_profile_request(selected_request_id)
    if selected_request is None and request_rows:
        selected_request = request_rows[0]

    approved_profiles = list(
        repo.list_import_mapping_profiles(
            include_inactive=False,
        )
        or []
    )
    return _render(
        request,
        user=user,
        queue_status=queue_status,
        request_rows=request_rows,
        selected_request=selected_request,
        approved_profiles=approved_profiles,
    )


@router.post("/import-mappings/review")
@require_permission("manage_import_mapping_profile")
async def admin_import_mappings_review(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Admin Import Mappings")
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_IMPORT_MAPPINGS), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    request_id = str(form.get("profile_request_id") or "").strip()
    decision = str(form.get("decision") or "").strip().lower()
    review_note = str(form.get("review_note") or "").strip()
    queue_status = _normalize_status(str(form.get("status") or "pending"))
    if not request_id:
        add_flash(request, "Mapping request id is required.", "error")
        return RedirectResponse(url=f"/admin/import-mappings?status={queue_status}", status_code=303)
    if decision not in {"approved", "rejected"}:
        add_flash(request, "Decision must be approved or rejected.", "error")
        return RedirectResponse(
            url=f"/admin/import-mappings?status={queue_status}&request_id={request_id}",
            status_code=303,
        )
    if decision == "rejected" and not review_note:
        add_flash(request, "Reviewer note is required for rejected mappings.", "error")
        return RedirectResponse(
            url=f"/admin/import-mappings?status={queue_status}&request_id={request_id}",
            status_code=303,
        )

    try:
        reviewed = repo.review_import_mapping_profile_request(
            profile_request_id=request_id,
            decision=decision,
            reviewer_user_principal=user.user_principal,
            review_note=review_note,
        )
    except Exception as exc:
        add_flash(request, f"Could not review mapping request: {exc}", "error")
        return RedirectResponse(
            url=f"/admin/import-mappings?status={queue_status}&request_id={request_id}",
            status_code=303,
        )

    approved_profile_id = str(reviewed.get("approved_profile_id") or "").strip()
    _sync_job_mapping_status(
        repo=repo,
        request_row=dict(reviewed or {}),
        actor=user.user_principal,
        approved_profile_id=approved_profile_id,
    )
    if hasattr(repo, "log_usage_event"):
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="admin_import_mappings",
            event_type="mapping_request_reviewed",
            payload={
                "profile_request_id": request_id,
                "decision": decision,
                "approved_profile_id": approved_profile_id,
            },
        )
    add_flash(
        request,
        (
            f"Mapping request {request_id} approved."
            if decision == "approved"
            else f"Mapping request {request_id} rejected."
        ),
        "success",
    )
    return RedirectResponse(
        url=f"/admin/import-mappings?status={queue_status}&request_id={request_id}",
        status_code=303,
    )
