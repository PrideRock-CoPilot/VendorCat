from __future__ import annotations

from fastapi import APIRouter

from vendor_catalog_app.web.routers.pending_approvals.common import *


router = APIRouter(prefix="/workflows")

@router.get("/{change_request_id}")
def workflow_detail(request: Request, change_request_id: str, return_to: str = "/workflows"):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Workflow Detail")

    if not user.can_access_workflows:
        add_flash(request, "Workflow access is not available for this role.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    safe_return_to = _safe_return_to(return_to)
    row = repo.get_change_request_by_id(change_request_id)
    if not row:
        add_flash(request, "Change request not found.", "error")
        return RedirectResponse(url=safe_return_to, status_code=303)

    payload = _payload_obj(str(row.get("requested_payload_json") or ""))
    vendor_id = str(row.get("vendor_id") or "").strip()
    if vendor_id and vendor_id != GLOBAL_CHANGE_VENDOR_ID:
        vendor_rows = repo.get_vendors_by_ids([vendor_id]).to_dict("records")
        if vendor_rows:
            owner_org = str(vendor_rows[0].get("owner_org_id") or "").strip()
            if owner_org:
                payload.setdefault("owner_org_id", owner_org)

    row["_payload"] = payload
    row["_approval_level"] = _required_level(row)
    row["_approval_label"] = approval_level_label(int(row["_approval_level"]))
    row["_can_decide"] = user.can_review_level(int(row["_approval_level"]))
    row["_org_values"] = _payload_org_values(payload)
    row["_lob_values"] = _payload_lob_values(payload, {})
    row["_lob_display"] = ", ".join(row["_lob_values"]) if row["_lob_values"] else "-"
    row["_summary"] = _payload_summary(payload)

    if user.can_approve_requests:
        scoped_orgs, has_enterprise_scope = _user_scope(repo, user)
        refs = _user_refs(repo, user)
        requester_raw = str(row.get("requestor_user_principal_raw") or row.get("requestor_user_principal") or "").strip().lower()
        is_requester = requester_raw in refs
        if not is_requester and not _row_in_user_scope(
            row=row,
            user_scoped_orgs=scoped_orgs,
            user_has_enterprise_scope=has_enterprise_scope,
        ):
            add_flash(request, "This approval is outside your assigned business-unit scope.", "error")
            return RedirectResponse(url=safe_return_to, status_code=303)

    side_by_side_rows = _build_side_by_side_rows(repo, row, payload)
    decision_status_options = _workflow_status_options(repo)
    target_links = _build_target_links(repo, row, payload, return_to=safe_return_to)

    context = base_template_context(
        request=request,
        context=user,
        title=f"Approval Request {change_request_id}",
        active_nav="pending_approvals",
        extra={
            "row": row,
            "side_by_side_rows": side_by_side_rows,
            "decision_status_options": decision_status_options,
            "target_links": target_links,
            "return_to": safe_return_to,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "workflow_detail.html", context)


