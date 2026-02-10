from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.repository import GLOBAL_CHANGE_VENDOR_ID
from vendor_catalog_app.security import approval_level_label, required_approval_level
from vendor_catalog_app.web.flash import add_flash
from vendor_catalog_app.web.services import (
    base_template_context,
    ensure_session_started,
    get_repo,
    get_user_context,
    log_page_view,
)


router = APIRouter(prefix="/workflows")

WORKFLOW_STATUSES = ["pending", "submitted", "in_review", "approved", "rejected", "all"]


def _safe_return_to(value: str | None) -> str:
    if not value:
        return "/workflows"
    if value.startswith("/workflows") or value.startswith("/vendors") or value.startswith("/projects"):
        return value
    return "/workflows"


def _normalize_status(value: str | None) -> str:
    cleaned = str(value or "pending").strip().lower()
    if cleaned not in WORKFLOW_STATUSES:
        return "pending"
    return cleaned


def _payload_obj(raw_payload: str) -> dict:
    try:
        parsed = json.loads(raw_payload or "{}")
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _required_level(row: dict) -> int:
    payload = _payload_obj(str(row.get("requested_payload_json") or ""))
    meta = payload.get("_meta") if isinstance(payload.get("_meta"), dict) else {}
    try:
        level = int(meta.get("approval_level_required", required_approval_level(str(row.get("change_type") or ""))))
    except Exception:
        level = required_approval_level(str(row.get("change_type") or ""))
    return max(1, min(level, 3))


@router.get("")
def workflow_queue(request: Request, status: str = "pending"):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Workflow Queue")

    if not user.can_edit:
        add_flash(request, "Edit permission is required to view workflows.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    selected_status = _normalize_status(status)
    query_status = "submitted" if selected_status == "pending" else selected_status
    rows = repo.list_change_requests(status=query_status).to_dict("records")
    for row in rows:
        level = _required_level(row)
        row["_approval_level"] = level
        row["_approval_label"] = approval_level_label(level)
        row["_can_decide"] = user.can_review_level(level)
        row["_vendor_display"] = "global" if str(row.get("vendor_id") or "") == GLOBAL_CHANGE_VENDOR_ID else str(
            row.get("vendor_id") or ""
        )

    context = base_template_context(
        request=request,
        context=user,
        title="Workflow Queue",
        active_nav="workflows",
        extra={
            "rows": rows,
            "selected_status": selected_status,
            "status_options": WORKFLOW_STATUSES,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "workflows.html", context)


@router.post("/{change_request_id}/decision")
async def workflow_decision(request: Request, change_request_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", "/workflows")))
    decision = str(form.get("decision", "")).strip().lower()
    notes = str(form.get("notes", "")).strip()

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Workflow decisions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if decision not in {"approved", "rejected"}:
        add_flash(request, "Decision must be approved or rejected.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    row = repo.get_change_request_by_id(change_request_id)
    if not row:
        add_flash(request, "Change request not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    status_now = str(row.get("status") or "").strip().lower()
    if status_now in {"approved", "rejected"}:
        add_flash(request, f"Change request is already {status_now}.", "info")
        return RedirectResponse(url=return_to, status_code=303)

    level = _required_level(row)
    if not user.can_review_level(level):
        add_flash(
            request,
            f"Approval level {approval_level_label(level)} is required to decide this request.",
            "error",
        )
        return RedirectResponse(url=return_to, status_code=303)

    try:
        repo.update_change_request_status(
            change_request_id=change_request_id,
            new_status=decision,
            actor_user_principal=user.user_principal,
            notes=notes,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="workflows",
            event_type="workflow_decision",
            payload={"change_request_id": change_request_id, "decision": decision, "required_level": level},
        )
        add_flash(request, f"Change request {decision}: {change_request_id}", "success")
    except Exception as exc:
        add_flash(request, f"Could not update workflow status: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)
