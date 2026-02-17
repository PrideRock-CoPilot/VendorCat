from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.core.activity import ensure_session_started, log_page_view
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.pending_approvals.common import *

router = APIRouter(prefix="/workflows")

@router.get("")
def workflow_queue(request: Request, status: str = "pending"):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Workflow Queue")

    if not user.can_access_workflows:
        add_flash(request, "Workflow access is not available for this role.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    status_options = _workflow_filter_status_options(repo)
    selected_status = _normalize_status(status, set(status_options))
    selected_queue = _normalize_queue(request.query_params.get("queue"))
    selected_lob = str(request.query_params.get("lob", "all")).strip()
    selected_requestor = str(request.query_params.get("requestor", "all")).strip()
    selected_assignee = str(request.query_params.get("assignee", "all")).strip()
    selected_people = str(request.query_params.get("people", "")).strip()
    queue_view = _load_workflow_queue_view(
        repo,
        user,
        selected_status=selected_status,
        selected_queue=selected_queue,
        selected_lob=selected_lob,
        selected_requestor=selected_requestor,
        selected_assignee=selected_assignee,
        selected_people=selected_people,
    )
    filtered_rows = list(queue_view.get("rows") or [])
    current_view_url = _workflow_queue_url(
        selected_status=selected_status,
        selected_queue=selected_queue,
        selected_lob=selected_lob,
        selected_requestor=selected_requestor,
        selected_assignee=selected_assignee,
        selected_people=selected_people,
    )
    decision_status_options = _workflow_status_options(repo)
    quick_approve_enabled = "approved" in decision_status_options
    quick_reject_enabled = "rejected" in decision_status_options
    next_candidate = next((row for row in filtered_rows if bool(row.get("_can_quick_decide"))), None)
    if next_candidate is None and filtered_rows:
        next_candidate = filtered_rows[0]
    next_pending_url = ""
    if next_candidate:
        next_id = str(next_candidate.get("change_request_id") or "").strip()
        if next_id:
            next_pending_url = f"/workflows/{next_id}?return_to={quote(current_view_url, safe='')}"

    context = base_template_context(
        request=request,
        context=user,
        title="Pending Approvals",
        active_nav="pending_approvals",
        extra={
            "rows": filtered_rows,
            "selected_status": selected_status,
            "status_options": status_options,
            "selected_queue": selected_queue,
            "queue_options": WORKFLOW_QUEUES,
            "selected_lob": selected_lob,
            "lob_options": queue_view.get("lob_options", []),
            "selected_requestor": selected_requestor,
            "requestor_options": queue_view.get("requestor_options", []),
            "selected_assignee": selected_assignee,
            "assignee_options": queue_view.get("assignee_options", []),
            "selected_people": selected_people,
            "current_view_url": current_view_url,
            "current_view_url_encoded": quote(current_view_url, safe=""),
            "next_pending_url": next_pending_url,
            "quick_approve_enabled": quick_approve_enabled,
            "quick_reject_enabled": quick_reject_enabled,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "workflows.html", context)


@router.get("/next-pending")
def workflow_next_pending(request: Request, status: str = "pending"):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Workflow Queue")

    if not user.can_access_workflows:
        add_flash(request, "Workflow access is not available for this role.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    status_options = _workflow_filter_status_options(repo)
    selected_status = _normalize_status(status, set(status_options))
    selected_queue = _normalize_queue(request.query_params.get("queue"))
    selected_lob = str(request.query_params.get("lob", "all")).strip()
    selected_requestor = str(request.query_params.get("requestor", "all")).strip()
    selected_assignee = str(request.query_params.get("assignee", "all")).strip()
    selected_people = str(request.query_params.get("people", "")).strip()
    queue_url = _workflow_queue_url(
        selected_status=selected_status,
        selected_queue=selected_queue,
        selected_lob=selected_lob,
        selected_requestor=selected_requestor,
        selected_assignee=selected_assignee,
        selected_people=selected_people,
    )

    queue_view = _load_workflow_queue_view(
        repo,
        user,
        selected_status=selected_status,
        selected_queue=selected_queue,
        selected_lob=selected_lob,
        selected_requestor=selected_requestor,
        selected_assignee=selected_assignee,
        selected_people=selected_people,
    )
    filtered_rows = list(queue_view.get("rows") or [])
    if not filtered_rows:
        add_flash(request, "No requests available in the current queue filters.", "info")
        return RedirectResponse(url=queue_url, status_code=303)

    candidate = next((row for row in filtered_rows if bool(row.get("_can_quick_decide"))), None)
    if candidate is None:
        candidate = filtered_rows[0]
    change_request_id = str(candidate.get("change_request_id") or "").strip()
    if not change_request_id:
        add_flash(request, "Could not identify the next request in queue.", "error")
        return RedirectResponse(url=queue_url, status_code=303)
    detail_url = f"/workflows/{change_request_id}?return_to={quote(queue_url, safe='')}"
    return RedirectResponse(url=detail_url, status_code=302)


@router.get("/pending-approvals")
def pending_approvals(request: Request):
    status = str(request.query_params.get("status", "pending"))
    queue = str(request.query_params.get("queue", "my_approvals")).strip().lower()
    if queue != "my_approvals":
        queue = "my_approvals"
    redirect_url = f"/workflows?status={quote(status, safe='')}&queue={quote(queue, safe='')}"
    return RedirectResponse(url=redirect_url, status_code=302)


