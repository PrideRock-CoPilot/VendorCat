from __future__ import annotations

from fastapi import APIRouter

from vendor_catalog_app.web.routers.pending_approvals.common import *


router = APIRouter(prefix="/workflows")

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
    decision_options = set(_workflow_status_options(repo))
    if decision not in decision_options:
        add_flash(request, "Decision must be selected from admin-managed workflow statuses.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    row = repo.get_change_request_by_id(change_request_id)
    if not row:
        add_flash(request, "Change request not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    status_now = str(row.get("status") or "").strip().lower()
    if _is_terminal_workflow_status(status_now):
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
    payload = _payload_obj(str(row.get("requested_payload_json") or ""))
    vendor_id = str(row.get("vendor_id") or "").strip()
    if vendor_id and vendor_id != GLOBAL_CHANGE_VENDOR_ID:
        vendor_rows = repo.get_vendors_by_ids([vendor_id]).to_dict("records")
        if vendor_rows:
            owner_org = str(vendor_rows[0].get("owner_org_id") or "").strip()
            if owner_org:
                payload.setdefault("owner_org_id", owner_org)
    row_scope = {"_org_values": _payload_org_values(payload)}
    scoped_orgs, has_enterprise_scope = _user_scope(repo, user)
    if not _row_in_user_scope(
        row=row_scope,
        user_scoped_orgs=scoped_orgs,
        user_has_enterprise_scope=has_enterprise_scope,
    ):
        add_flash(request, "This approval is outside your assigned business-unit scope.", "error")
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
