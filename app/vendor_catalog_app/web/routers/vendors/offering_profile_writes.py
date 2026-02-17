from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.vendors.common import (
    _redirect_if_write_blocked,
    _resolve_write_request_context,
)
from vendor_catalog_app.web.routers.vendors.constants import (
    OFFERING_DATAFLOW_CHANGE_REASON_OPTIONS,
    OFFERING_DATAFLOW_REMOVE_REASON_OPTIONS,
    OFFERING_DATA_METHOD_OPTIONS,
    OFFERING_NOTE_TYPES,
    OFFERING_PROFILE_REASON_OPTIONS,
    OFFERING_TICKET_UPDATE_REASON_OPTIONS,
    OFFERING_TICKET_PRIORITIES,
    OFFERING_TICKET_STATUSES,
    VENDOR_DEFAULT_RETURN_TO,
)
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/vendors")


@router.post("/{vendor_id}/offerings/{offering_id}/profile/save")
@require_permission("offering_profile_edit")
async def offering_profile_save_submit(request: Request, vendor_id: str, offering_id: str):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=VENDOR_DEFAULT_RETURN_TO,
    )
    source_section = str(form.get("source_section", "profile")).strip().lower()
    if source_section not in {"profile", "dataflow"}:
        source_section = "profile"
    reason = str(form.get("reason", "")).strip()

    blocked_response = _redirect_if_write_blocked(
        request,
        user,
        redirect_url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
    )
    if blocked_response is not None:
        return blocked_response
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/offerings?return_to={quote(return_to, safe='')}", status_code=303)

    updates: dict[str, str | float | None] = {}
    if "estimated_monthly_cost" in form:
        raw_cost = str(form.get("estimated_monthly_cost", "")).strip()
        if raw_cost:
            try:
                updates["estimated_monthly_cost"] = float(raw_cost.replace(",", ""))
            except Exception:
                add_flash(request, "Estimated monthly cost must be numeric.", "error")
                return RedirectResponse(
                    url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
                    status_code=303,
                )
        else:
            updates["estimated_monthly_cost"] = None
    if "implementation_notes" in form:
        updates["implementation_notes"] = str(form.get("implementation_notes", "")).strip() or None
    if "data_sent" in form:
        updates["data_sent"] = str(form.get("data_sent", "")).strip() or None
    if "data_received" in form:
        updates["data_received"] = str(form.get("data_received", "")).strip() or None
    if "integration_method" in form:
        updates["integration_method"] = str(form.get("integration_method", "")).strip() or None
    if "inbound_method" in form:
        updates["inbound_method"] = str(form.get("inbound_method", "")).strip().lower() or None
    if "inbound_landing_zone" in form:
        updates["inbound_landing_zone"] = str(form.get("inbound_landing_zone", "")).strip() or None
    if "inbound_identifiers" in form:
        updates["inbound_identifiers"] = str(form.get("inbound_identifiers", "")).strip() or None
    if "inbound_reporting_layer" in form:
        updates["inbound_reporting_layer"] = str(form.get("inbound_reporting_layer", "")).strip() or None
    if "inbound_ingestion_notes" in form:
        updates["inbound_ingestion_notes"] = str(form.get("inbound_ingestion_notes", "")).strip() or None
    if "outbound_method" in form:
        updates["outbound_method"] = str(form.get("outbound_method", "")).strip().lower() or None
    if "outbound_creation_process" in form:
        updates["outbound_creation_process"] = str(form.get("outbound_creation_process", "")).strip() or None
    if "outbound_delivery_process" in form:
        updates["outbound_delivery_process"] = str(form.get("outbound_delivery_process", "")).strip() or None
    if "outbound_responsible_owner" in form:
        outbound_responsible_owner = str(form.get("outbound_responsible_owner", "")).strip()
        if outbound_responsible_owner:
            resolved_owner = repo.resolve_user_login_identifier(outbound_responsible_owner)
            if not resolved_owner:
                add_flash(request, "Outbound responsible owner must exist in the app user directory.", "error")
                return RedirectResponse(
                    url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
                    status_code=303,
                )
            outbound_responsible_owner = resolved_owner
        updates["outbound_responsible_owner"] = outbound_responsible_owner or None
    if "outbound_notes" in form:
        updates["outbound_notes"] = str(form.get("outbound_notes", "")).strip() or None

    if not updates:
        add_flash(request, "No profile fields were submitted.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    invalid_method_values = [
        value
        for value in [updates.get("inbound_method"), updates.get("outbound_method")]
        if value and value not in set(OFFERING_DATA_METHOD_OPTIONS)
    ]
    if invalid_method_values:
        add_flash(
            request,
            f"Data methods must be one of: {', '.join(OFFERING_DATA_METHOD_OPTIONS)}",
            "error",
        )
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    payload = {"offering_id": offering_id, "updates": updates, "reason": reason}
    try:
        if user.can_apply_change("update_offering_profile"):
            result = repo.save_offering_profile(
                vendor_id=vendor_id,
                offering_id=offering_id,
                actor_user_principal=user.user_principal,
                updates=updates,
                reason=reason,
            )
            add_flash(
                request,
                f"Offering profile updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_offering_profile",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_profile_update",
            payload={"vendor_id": vendor_id, "offering_id": offering_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not update offering profile: {exc}", "error")

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/offerings/{offering_id}/dataflows/add")
@require_permission("offering_dataflow_create")
async def add_offering_data_flow_submit(request: Request, vendor_id: str, offering_id: str):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=VENDOR_DEFAULT_RETURN_TO,
    )
    reason = str(form.get("reason", "")).strip()
    direction = str(form.get("direction", "")).strip().lower()
    flow_name = str(form.get("flow_name", "")).strip()
    method = str(form.get("method", "")).strip().lower()
    data_description = str(form.get("data_description", "")).strip()
    endpoint_details = str(form.get("endpoint_details", "")).strip()
    identifiers = str(form.get("identifiers", "")).strip()
    reporting_layer = str(form.get("reporting_layer", "")).strip()
    creation_process = str(form.get("creation_process", "")).strip()
    delivery_process = str(form.get("delivery_process", "")).strip()
    owner_user_principal = str(form.get("owner_user_principal", "")).strip()
    notes = str(form.get("notes", "")).strip()
    source_section = "dataflow"

    blocked_response = _redirect_if_write_blocked(
        request,
        user,
        redirect_url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
    )
    if blocked_response is not None:
        return blocked_response
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/offerings?return_to={quote(return_to, safe='')}", status_code=303)
    if direction not in {"inbound", "outbound"}:
        add_flash(request, "Direction must be inbound or outbound.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not flow_name:
        add_flash(request, "Data flow name is required.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if method and method not in set(OFFERING_DATA_METHOD_OPTIONS):
        add_flash(request, f"Data method must be one of: {', '.join(OFFERING_DATA_METHOD_OPTIONS)}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if owner_user_principal and not repo.resolve_user_login_identifier(owner_user_principal):
        add_flash(request, "Owner must exist in the app user directory.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    payload = {
        "offering_id": offering_id,
        "direction": direction,
        "flow_name": flow_name,
        "method": method or None,
        "data_description": data_description or None,
        "endpoint_details": endpoint_details or None,
        "identifiers": identifiers or None,
        "reporting_layer": reporting_layer or None,
        "creation_process": creation_process or None,
        "delivery_process": delivery_process or None,
        "owner_user_principal": owner_user_principal or None,
        "notes": notes or None,
        "reason": reason,
    }
    try:
        if user.can_apply_change("update_offering_profile"):
            data_flow_id = repo.add_offering_data_flow(
                vendor_id=vendor_id,
                offering_id=offering_id,
                direction=direction,
                flow_name=flow_name,
                method=method or None,
                data_description=data_description or None,
                endpoint_details=endpoint_details or None,
                identifiers=identifiers or None,
                reporting_layer=reporting_layer or None,
                creation_process=creation_process or None,
                delivery_process=delivery_process or None,
                owner_user_principal=owner_user_principal or None,
                notes=notes or None,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Offering data flow added: {data_flow_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_offering_profile",
                payload={"data_flow_action": "add", **payload},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_data_flow_add",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "direction": direction},
        )
    except Exception as exc:
        add_flash(request, f"Could not add offering data flow: {exc}", "error")

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/offerings/{offering_id}/dataflows/remove")
@require_permission("offering_dataflow_delete")
async def remove_offering_data_flow_submit(request: Request, vendor_id: str, offering_id: str):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=VENDOR_DEFAULT_RETURN_TO,
    )
    reason = str(form.get("reason", "")).strip()
    data_flow_id = str(form.get("data_flow_id", "")).strip()
    source_section = "dataflow"

    blocked_response = _redirect_if_write_blocked(
        request,
        user,
        redirect_url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
    )
    if blocked_response is not None:
        return blocked_response
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/offerings?return_to={quote(return_to, safe='')}", status_code=303)
    if not data_flow_id:
        add_flash(request, "Data flow ID is required.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    try:
        if user.can_apply_change("update_offering_profile"):
            repo.remove_offering_data_flow(
                vendor_id=vendor_id,
                offering_id=offering_id,
                data_flow_id=data_flow_id,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, "Offering data flow removed.", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_offering_profile",
                payload={
                    "offering_id": offering_id,
                    "data_flow_action": "remove",
                    "data_flow_id": data_flow_id,
                    "reason": reason,
                },
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_data_flow_remove",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "data_flow_id": data_flow_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not remove offering data flow: {exc}", "error")

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/offerings/{offering_id}/dataflows/update")
@require_permission("offering_dataflow_edit")
async def update_offering_data_flow_submit(request: Request, vendor_id: str, offering_id: str):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=VENDOR_DEFAULT_RETURN_TO,
    )
    reason = str(form.get("reason", "")).strip()
    data_flow_id = str(form.get("data_flow_id", "")).strip()
    direction = str(form.get("direction", "")).strip().lower()
    flow_name = str(form.get("flow_name", "")).strip()
    method = str(form.get("method", "")).strip().lower()
    data_description = str(form.get("data_description", "")).strip()
    endpoint_details = str(form.get("endpoint_details", "")).strip()
    identifiers = str(form.get("identifiers", "")).strip()
    reporting_layer = str(form.get("reporting_layer", "")).strip()
    creation_process = str(form.get("creation_process", "")).strip()
    delivery_process = str(form.get("delivery_process", "")).strip()
    owner_user_principal = str(form.get("owner_user_principal", "")).strip()
    notes = str(form.get("notes", "")).strip()
    source_section = "dataflow"

    blocked_response = _redirect_if_write_blocked(
        request,
        user,
        redirect_url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
    )
    if blocked_response is not None:
        return blocked_response
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=f"/vendors/{vendor_id}/offerings?return_to={quote(return_to, safe='')}", status_code=303)
    if not data_flow_id:
        add_flash(request, "Data flow ID is required.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if direction not in {"inbound", "outbound"}:
        add_flash(request, "Direction must be inbound or outbound.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&edit_data_flow_id={quote(data_flow_id, safe='')}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not flow_name:
        add_flash(request, "Data flow name is required.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&edit_data_flow_id={quote(data_flow_id, safe='')}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if method and method not in set(OFFERING_DATA_METHOD_OPTIONS):
        add_flash(request, f"Data method must be one of: {', '.join(OFFERING_DATA_METHOD_OPTIONS)}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&edit_data_flow_id={quote(data_flow_id, safe='')}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if owner_user_principal and not repo.resolve_user_login_identifier(owner_user_principal):
        add_flash(request, "Owner must exist in the app user directory.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&edit_data_flow_id={quote(data_flow_id, safe='')}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    payload = {
        "offering_id": offering_id,
        "data_flow_id": data_flow_id,
        "direction": direction,
        "flow_name": flow_name,
        "method": method or None,
        "data_description": data_description or None,
        "endpoint_details": endpoint_details or None,
        "identifiers": identifiers or None,
        "reporting_layer": reporting_layer or None,
        "creation_process": creation_process or None,
        "delivery_process": delivery_process or None,
        "owner_user_principal": owner_user_principal or None,
        "notes": notes or None,
        "reason": reason,
    }
    try:
        if user.can_apply_change("update_offering_profile"):
            result = repo.update_offering_data_flow(
                vendor_id=vendor_id,
                offering_id=offering_id,
                data_flow_id=data_flow_id,
                actor_user_principal=user.user_principal,
                updates={
                    "direction": direction,
                    "flow_name": flow_name,
                    "method": method or None,
                    "data_description": data_description or None,
                    "endpoint_details": endpoint_details or None,
                    "identifiers": identifiers or None,
                    "reporting_layer": reporting_layer or None,
                    "creation_process": creation_process or None,
                    "delivery_process": delivery_process or None,
                    "owner_user_principal": owner_user_principal or None,
                    "notes": notes or None,
                },
                reason=reason,
            )
            add_flash(
                request,
                f"Offering data flow updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_offering_profile",
                payload={"data_flow_action": "update", **payload},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_data_flow_update",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "data_flow_id": data_flow_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not update offering data flow: {exc}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&edit_data_flow_id={quote(data_flow_id, safe='')}&return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section={source_section}&edit=1&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/offerings/{offering_id}/notes/add")
@require_permission("offering_note_create")
async def add_offering_note_submit(request: Request, vendor_id: str, offering_id: str):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=VENDOR_DEFAULT_RETURN_TO,
    )
    note_type = str(form.get("note_type", "general")).strip().lower() or "general"
    note_text = str(form.get("note_text", "")).strip()

    blocked_response = _redirect_if_write_blocked(
        request,
        user,
        redirect_url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=notes&return_to={quote(return_to, safe='')}",
    )
    if blocked_response is not None:
        return blocked_response
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=notes&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if note_type not in set(OFFERING_NOTE_TYPES):
        add_flash(request, f"Note type must be one of: {', '.join(OFFERING_NOTE_TYPES)}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=notes&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not note_text:
        add_flash(request, "Note text is required.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=notes&return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    try:
        if user.can_apply_change("add_offering_note"):
            note_id = repo.add_offering_note(
                vendor_id=vendor_id,
                offering_id=offering_id,
                note_type=note_type,
                note_text=note_text,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Offering note added: {note_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_offering_note",
                payload={"offering_id": offering_id, "note_type": note_type, "note_text": note_text},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_note_add",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "note_type": note_type},
        )
    except Exception as exc:
        add_flash(request, f"Could not add offering note: {exc}", "error")

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=notes&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/offerings/{offering_id}/tickets/add")
@require_permission("offering_ticket_create")
async def add_offering_ticket_submit(request: Request, vendor_id: str, offering_id: str):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=VENDOR_DEFAULT_RETURN_TO,
    )
    title = str(form.get("title", "")).strip()
    ticket_system = str(form.get("ticket_system", "")).strip()
    external_ticket_id = str(form.get("external_ticket_id", "")).strip()
    status = str(form.get("status", "open")).strip().lower() or "open"
    priority = str(form.get("priority", "")).strip().lower()
    opened_date = str(form.get("opened_date", "")).strip()
    notes = str(form.get("notes", "")).strip()

    blocked_response = _redirect_if_write_blocked(
        request,
        user,
        redirect_url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
    )
    if blocked_response is not None:
        return blocked_response
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if status not in set(OFFERING_TICKET_STATUSES):
        add_flash(request, f"Ticket status must be one of: {', '.join(OFFERING_TICKET_STATUSES)}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if priority and priority not in set(OFFERING_TICKET_PRIORITIES):
        add_flash(request, f"Ticket priority must be one of: {', '.join(OFFERING_TICKET_PRIORITIES)}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    payload = {
        "offering_id": offering_id,
        "title": title,
        "ticket_system": ticket_system or None,
        "external_ticket_id": external_ticket_id or None,
        "status": status,
        "priority": priority or None,
        "opened_date": opened_date or None,
        "notes": notes or None,
    }
    try:
        if user.can_apply_change("add_offering_ticket"):
            ticket_id = repo.add_offering_ticket(
                vendor_id=vendor_id,
                offering_id=offering_id,
                title=title,
                ticket_system=ticket_system or None,
                external_ticket_id=external_ticket_id or None,
                status=status,
                priority=priority or None,
                opened_date=opened_date or None,
                notes=notes or None,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Offering ticket added: {ticket_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_offering_ticket",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_ticket_add",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "status": status},
        )
    except Exception as exc:
        add_flash(request, f"Could not add offering ticket: {exc}", "error")

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/offerings/{offering_id}/tickets/{ticket_id}/status")
@require_permission("offering_ticket_update")
async def update_offering_ticket_status_submit(request: Request, vendor_id: str, offering_id: str, ticket_id: str):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=VENDOR_DEFAULT_RETURN_TO,
    )
    status = str(form.get("status", "")).strip().lower()
    closed_date = str(form.get("closed_date", "")).strip()
    reason = str(form.get("reason", "")).strip()

    blocked_response = _redirect_if_write_blocked(
        request,
        user,
        redirect_url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
    )
    if blocked_response is not None:
        return blocked_response
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if status not in set(OFFERING_TICKET_STATUSES):
        add_flash(request, f"Ticket status must be one of: {', '.join(OFFERING_TICKET_STATUSES)}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    payload = {
        "ticket_id": ticket_id,
        "offering_id": offering_id,
        "status": status,
        "closed_date": closed_date or None,
        "reason": reason,
    }
    try:
        if user.can_apply_change("update_offering_ticket"):
            result = repo.update_offering_ticket(
                vendor_id=vendor_id,
                offering_id=offering_id,
                ticket_id=ticket_id,
                actor_user_principal=user.user_principal,
                updates={
                    "status": status,
                    "closed_date": closed_date or None,
                },
                reason=reason,
            )
            add_flash(
                request,
                f"Offering ticket updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_offering_ticket",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_ticket_update",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "ticket_id": ticket_id, "status": status},
        )
    except Exception as exc:
        add_flash(request, f"Could not update offering ticket: {exc}", "error")

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=tickets&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


