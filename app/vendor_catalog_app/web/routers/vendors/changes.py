from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.core.security import (
    MAX_APPROVAL_LEVEL,
    MIN_CHANGE_APPROVAL_LEVEL,
    required_approval_level,
)
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.vendors.common import (
    _safe_return_to,
    _vendor_base_context,
    _write_blocked,
)
from vendor_catalog_app.web.routers.vendors.constants import (
    LIFECYCLE_STATES,
    RISK_TIERS,
    VENDOR_DEFAULT_RETURN_TO,
    VENDOR_PROFILE_CHANGE_REASON_OPTIONS,
)
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/vendors")


@router.get("/{vendor_id}/lineage")
def vendor_lineage_page(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "lineage", return_to)
    if isinstance(base, RedirectResponse):
        return base
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Lineage/Audit",
        active_nav="vendors",
        extra={
            "section": "lineage",
            "vendor_id": base["vendor_id"],
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "summary": base["summary"],
            "source_lineage": repo.get_vendor_source_lineage(base["vendor_id"]).to_dict("records"),
            "change_requests": repo.get_vendor_change_requests(base["vendor_id"]).to_dict("records"),
            "audit_events": repo.get_vendor_audit_events(base["vendor_id"]).to_dict("records"),
            "merge_history": (
                repo.list_vendor_merge_history(vendor_id=base["vendor_id"], limit=50)
                if hasattr(repo, "list_vendor_merge_history")
                else []
            ),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_section.html", context)


@router.get("/{vendor_id}/changes")
def vendor_changes_page(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "changes", return_to)
    if isinstance(base, RedirectResponse):
        return base
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Changes",
        active_nav="vendors",
        extra={
            "section": "changes",
            "vendor_id": base["vendor_id"],
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "summary": base["summary"],
            "profile": base["profile"].to_dict("records"),
            "recent_audit": repo.get_vendor_audit_events(base["vendor_id"]).head(5).to_dict("records"),
            "lifecycle_states": LIFECYCLE_STATES,
            "risk_tiers": RISK_TIERS,
            "vendor_profile_change_reason_options": VENDOR_PROFILE_CHANGE_REASON_OPTIONS,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_section.html", context)


@router.post("/{vendor_id}/direct-update")
@require_permission("vendor_edit")
async def vendor_direct_update(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)
    if not user.can_apply_change("update_vendor_profile"):
        required_level = required_approval_level("update_vendor_profile")
        add_flash(request, f"Direct updates require approval level {required_level} or higher.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)

    profile = repo.get_vendor_profile(vendor_id)
    if profile.empty:
        add_flash(request, f"Vendor {vendor_id} not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    current = profile.iloc[0].to_dict()
    candidate_updates = {
        "legal_name": str(form.get("legal_name", "")).strip(),
        "display_name": str(form.get("display_name", "")).strip(),
        "lifecycle_state": str(form.get("lifecycle_state", "")).strip(),
        "owner_org_id": str(form.get("owner_org_id", "")).strip(),
        "risk_tier": str(form.get("risk_tier", "")).strip(),
    }
    updates = {key: value for key, value in candidate_updates.items() if value != str(current.get(key, "")).strip()}
    reason = str(form.get("reason", "")).strip()

    if not updates:
        add_flash(request, "No field values changed.", "info")
        return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)
    if not reason:
        add_flash(request, "Reason for change is required.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)

    try:
        result = repo.apply_vendor_profile_update(
            vendor_id=vendor_id,
            actor_user_principal=user.user_principal,
            updates=updates,
            reason=reason,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_360",
            event_type="apply_vendor_update",
            payload={"vendor_id": vendor_id, "fields": sorted(list(updates.keys()))},
        )
        add_flash(
            request,
            f"Vendor updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
            "success",
        )
    except Exception as exc:
        add_flash(request, f"Could not apply update: {exc}", "error")

    return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)


@router.post("/{vendor_id}/change-request")
async def vendor_change_request(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    check_permission = user.can_submit_requests
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)
    if not check_permission:
        add_flash(request, "You do not have permission to submit change requests.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)

    change_type = str(form.get("change_type", "update_vendor_profile"))
    change_notes = str(form.get("change_notes", "")).strip()
    requested_level_raw = str(form.get("approval_level_required", "")).strip()
    assigned_approver = str(form.get("assigned_approver", "")).strip()
    try:
        minimum_level = required_approval_level(change_type)
        requested_level = minimum_level
        if requested_level_raw:
            requested_level = max(MIN_CHANGE_APPROVAL_LEVEL, min(int(requested_level_raw), MAX_APPROVAL_LEVEL))
            requested_level = max(requested_level, minimum_level)
        payload = {"notes": change_notes}
        payload_meta: dict[str, object] = {}
        if requested_level != minimum_level:
            payload_meta["approval_level_required"] = requested_level
        if assigned_approver:
            payload_meta["assigned_approver"] = assigned_approver
        if payload_meta:
            payload["_meta"] = payload_meta
        request_id = repo.create_vendor_change_request(
            vendor_id=vendor_id,
            requestor_user_principal=user.user_principal,
            change_type=change_type,
            payload=payload,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_360",
            event_type="submit_change_request",
            payload={
                "vendor_id": vendor_id,
                "change_type": change_type,
                "approval_level_required": requested_level,
                "assigned_approver": assigned_approver or None,
            },
        )
        add_flash(request, f"Change request submitted: {request_id}", "success")
    except Exception as exc:
        add_flash(request, f"Could not submit change request: {exc}", "error")
    return RedirectResponse(url=f"/vendors/{vendor_id}/changes?return_to={quote(return_to, safe='')}", status_code=303)

