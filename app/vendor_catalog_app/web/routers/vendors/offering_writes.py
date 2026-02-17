from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.vendors.common import (
    _normalize_contact_identity,
    _redirect_if_write_blocked,
    _resolve_write_request_context,
    _resolve_directory_user_principal,
)
from vendor_catalog_app.web.routers.vendors.constants import (
    CONTACT_ADD_REASON_OPTIONS,
    CONTACT_REMOVE_REASON_OPTIONS,
    OFFERING_INVOICE_ADD_REASON_OPTIONS,
    OFFERING_INVOICE_REMOVE_REASON_OPTIONS,
    OWNER_ADD_REASON_OPTIONS,
    OWNER_ROLE_UPDATE_REASON_OPTIONS,
    OFFERING_INVOICE_STATUSES,
    OWNER_REASSIGN_REASON_OPTIONS,
    OWNER_REMOVE_REASON_OPTIONS,
    VENDOR_DEFAULT_RETURN_TO,
)
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/vendors")


@router.post("/{vendor_id}/offerings/{offering_id}/invoices/add")
@require_permission("offering_invoice_create")
async def add_offering_invoice_submit(request: Request, vendor_id: str, offering_id: str):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=VENDOR_DEFAULT_RETURN_TO,
    )
    invoice_number = str(form.get("invoice_number", "")).strip()
    invoice_date = str(form.get("invoice_date", "")).strip()
    amount_raw = str(form.get("amount", "")).strip()
    currency_code = str(form.get("currency_code", "USD")).strip().upper() or "USD"
    invoice_status = str(form.get("invoice_status", "received")).strip().lower() or "received"
    notes = str(form.get("notes", "")).strip()
    reason = str(form.get("reason", "")).strip()

    blocked_response = _redirect_if_write_blocked(
        request,
        user,
        redirect_url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=financials&return_to={quote(return_to, safe='')}",
    )
    if blocked_response is not None:
        return blocked_response
    if invoice_status not in set(OFFERING_INVOICE_STATUSES):
        add_flash(request, f"Invoice status must be one of: {', '.join(OFFERING_INVOICE_STATUSES)}", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=financials&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    try:
        amount_value = float(amount_raw.replace(",", ""))
    except Exception:
        add_flash(request, "Invoice amount must be numeric.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=financials&return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    payload = {
        "offering_id": offering_id,
        "invoice_number": invoice_number or None,
        "invoice_date": invoice_date,
        "amount": amount_value,
        "currency_code": currency_code,
        "invoice_status": invoice_status,
        "notes": notes or None,
        "reason": reason,
    }
    try:
        if user.can_apply_change("add_offering_invoice"):
            invoice_id = repo.add_offering_invoice(
                vendor_id=vendor_id,
                offering_id=offering_id,
                invoice_number=invoice_number or None,
                invoice_date=invoice_date,
                amount=amount_value,
                currency_code=currency_code,
                invoice_status=invoice_status,
                notes=notes or None,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Invoice added: {invoice_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_offering_invoice",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_invoice_add",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "invoice_status": invoice_status},
        )
    except Exception as exc:
        add_flash(request, f"Could not add offering invoice: {exc}", "error")

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=financials&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/offerings/{offering_id}/invoices/{invoice_id}/remove")
@require_permission("offering_invoice_delete")
async def remove_offering_invoice_submit(request: Request, vendor_id: str, offering_id: str, invoice_id: str):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=VENDOR_DEFAULT_RETURN_TO,
    )
    reason = str(form.get("reason", "")).strip()

    blocked_response = _redirect_if_write_blocked(
        request,
        user,
        redirect_url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=financials&return_to={quote(return_to, safe='')}",
    )
    if blocked_response is not None:
        return blocked_response
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=financials&return_to={quote(return_to, safe='')}",
            status_code=303,
        )

    payload = {"offering_id": offering_id, "invoice_id": invoice_id, "reason": reason}
    try:
        if user.can_apply_change("remove_offering_invoice"):
            repo.remove_offering_invoice(
                vendor_id=vendor_id,
                offering_id=offering_id,
                invoice_id=invoice_id,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, "Invoice removed.", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="remove_offering_invoice",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="offering_invoice_remove",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "invoice_id": invoice_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not remove offering invoice: {exc}", "error")

    return RedirectResponse(
        url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=financials&return_to={quote(return_to, safe='')}",
        status_code=303,
    )


@router.post("/{vendor_id}/offerings/{offering_id}/owners/add")
@require_permission("offering_owner_create")
async def add_offering_owner_submit(request: Request, vendor_id: str, offering_id: str):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=f"/vendors/{vendor_id}/offerings/{offering_id}",
    )
    owner_user_principal = str(form.get("owner_user_principal", "")).strip()
    owner_user_display_name = str(form.get("owner_user_principal_display_name", "")).strip()
    owner_role = str(form.get("owner_role", "")).strip()
    reason = str(form.get("reason", "")).strip()

    blocked_response = _redirect_if_write_blocked(request, user, redirect_url=return_to)
    if blocked_response is not None:
        return blocked_response
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        owner_user_principal = _resolve_directory_user_principal(
            repo,
            principal_value=owner_user_principal,
            display_name_value=owner_user_display_name,
            error_message="Owner must exist in the app user directory.",
        )
    except Exception as exc:
        add_flash(request, str(exc), "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {
            "offering_id": offering_id,
            "owner_user_principal": owner_user_principal,
            "owner_role": owner_role,
            "reason": reason,
        }
        if user.can_apply_change("add_offering_owner"):
            owner_id = repo.add_offering_owner(
                vendor_id=vendor_id,
                offering_id=offering_id,
                owner_user_principal=owner_user_principal,
                owner_role=owner_role,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Offering owner added: {owner_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_offering_owner",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="add_offering_owner",
            payload={"vendor_id": vendor_id, "offering_id": offering_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not add offering owner: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/offerings/{offering_id}/owners/remove")
@require_permission("offering_owner_delete")
async def remove_offering_owner_submit(request: Request, vendor_id: str, offering_id: str):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=f"/vendors/{vendor_id}/offerings/{offering_id}",
    )
    offering_owner_id = str(form.get("offering_owner_id", "")).strip()
    reason_code = str(form.get("reason_code", "")).strip().lower()
    reason = str(form.get("reason", "")).strip()

    blocked_response = _redirect_if_write_blocked(request, user, redirect_url=return_to)
    if blocked_response is not None:
        return blocked_response
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not reason_code:
        add_flash(request, "Removal reason is required.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if reason_code not in set(OWNER_REMOVE_REASON_OPTIONS):
        add_flash(
            request,
            f"Removal reason must be one of: {', '.join(OWNER_REMOVE_REASON_OPTIONS)}",
            "error",
        )
        return RedirectResponse(url=return_to, status_code=303)
    reason = reason_code

    try:
        payload = {"offering_id": offering_id, "offering_owner_id": offering_owner_id, "reason": reason}
        if user.can_apply_change("remove_offering_owner"):
            repo.remove_offering_owner(
                vendor_id=vendor_id,
                offering_id=offering_id,
                offering_owner_id=offering_owner_id,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, "Offering owner removed.", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="remove_offering_owner",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="remove_offering_owner",
            payload={"vendor_id": vendor_id, "offering_id": offering_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not remove offering owner: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/offerings/owners/reassign")
@require_permission("offering_owner_edit")
async def bulk_reassign_offering_owner_submit(request: Request, vendor_id: str):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=f"/vendors/{vendor_id}/offerings",
    )
    from_owner_user_principal = str(form.get("from_owner_user_principal", "")).strip()
    to_owner_user_principal = str(form.get("to_owner_user_principal", "")).strip()
    to_owner_display_name = str(form.get("to_owner_user_principal_display_name", "")).strip()
    reason_code = str(form.get("reason_code", "")).strip().lower()

    blocked_response = _redirect_if_write_blocked(request, user, redirect_url=return_to)
    if blocked_response is not None:
        return blocked_response
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not reason_code:
        add_flash(request, "Reassignment reason is required.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if reason_code not in set(OWNER_REASSIGN_REASON_OPTIONS):
        add_flash(
            request,
            f"Reassignment reason must be one of: {', '.join(OWNER_REASSIGN_REASON_OPTIONS)}",
            "error",
        )
        return RedirectResponse(url=return_to, status_code=303)

    replacement_lookup = to_owner_user_principal or to_owner_display_name
    resolved_replacement = repo.resolve_user_login_identifier(replacement_lookup)
    if not resolved_replacement:
        add_flash(request, "Replacement owner must exist in the app user directory.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        updated_count = repo.bulk_reassign_offering_owner(
            vendor_id=vendor_id,
            from_owner_user_principal=from_owner_user_principal,
            to_owner_user_principal=resolved_replacement,
            actor_user_principal=user.user_principal,
        )
        if updated_count <= 0:
            add_flash(request, "No active owner assignments found to reassign.", "error")
        else:
            add_flash(request, f"Reassigned {updated_count} owner assignment(s).", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="bulk_reassign_offering_owner",
            payload={
                "vendor_id": vendor_id,
                "from_owner_user_principal": from_owner_user_principal,
                "to_owner_user_principal": resolved_replacement,
                "updated_count": updated_count,
                "reason_code": reason_code,
            },
        )
    except Exception as exc:
        add_flash(request, f"Could not reassign offering owners: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/offerings/{offering_id}/owners/{offering_owner_id}/reassign")
@require_permission("offering_owner_edit")
async def reassign_single_offering_owner_submit(
    request: Request,
    vendor_id: str,
    offering_id: str,
    offering_owner_id: str,
):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=f"/vendors/{vendor_id}/offerings/{offering_id}",
    )
    to_owner_user_principal = str(form.get("to_owner_user_principal", "")).strip()
    to_owner_display_name = str(form.get("to_owner_user_principal_display_name", "")).strip()
    reason_code = str(form.get("reason_code", "")).strip().lower()

    blocked_response = _redirect_if_write_blocked(request, user, redirect_url=return_to)
    if blocked_response is not None:
        return blocked_response
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not reason_code:
        add_flash(request, "Reassignment reason is required.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if reason_code not in set(OWNER_REASSIGN_REASON_OPTIONS):
        add_flash(
            request,
            f"Reassignment reason must be one of: {', '.join(OWNER_REASSIGN_REASON_OPTIONS)}",
            "error",
        )
        return RedirectResponse(url=return_to, status_code=303)

    replacement_lookup = to_owner_user_principal or to_owner_display_name
    resolved_replacement = repo.resolve_user_login_identifier(replacement_lookup)
    if not resolved_replacement:
        add_flash(request, "Replacement owner must exist in the app user directory.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    owner_rows = repo.get_vendor_offering_business_owners(vendor_id)
    owner_rows = owner_rows[
        (owner_rows["offering_id"].astype(str) == str(offering_id))
        & (owner_rows["offering_owner_id"].astype(str) == str(offering_owner_id))
    ]
    if owner_rows.empty:
        add_flash(request, "Owner record not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    owner_row = owner_rows.iloc[0]
    current_owner_principal = str(owner_row.get("owner_user_principal") or "").strip()
    owner_role = str(owner_row.get("owner_role") or "").strip() or "business_owner"
    if not current_owner_principal:
        add_flash(request, "Owner identity is missing.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if current_owner_principal.lower() == resolved_replacement.lower():
        add_flash(request, "Replacement owner must be different from the current owner.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        repo.update_offering_owner(
            vendor_id=vendor_id,
            offering_id=offering_id,
            offering_owner_id=offering_owner_id,
            owner_user_principal=resolved_replacement,
            owner_role=owner_role,
            actor_user_principal=user.user_principal,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="reassign_single_offering_owner",
            payload={
                "vendor_id": vendor_id,
                "offering_id": offering_id,
                "offering_owner_id": offering_owner_id,
                "from_owner_user_principal": current_owner_principal,
                "to_owner_user_principal": resolved_replacement,
                "reason_code": reason_code,
            },
        )
        add_flash(request, "Offering owner reassigned.", "success")
    except Exception as exc:
        add_flash(request, f"Could not reassign offering owner: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/offerings/{offering_id}/owners/{offering_owner_id}/update")
@require_permission("offering_owner_edit")
async def update_offering_owner_submit(
    request: Request,
    vendor_id: str,
    offering_id: str,
    offering_owner_id: str,
):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=f"/vendors/{vendor_id}/offerings/{offering_id}",
    )
    owner_role = str(form.get("owner_role", "")).strip()
    reason = str(form.get("reason", "")).strip()

    blocked_response = _redirect_if_write_blocked(request, user, redirect_url=return_to)
    if blocked_response is not None:
        return blocked_response
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    owner_rows = repo.get_vendor_offering_business_owners(vendor_id)
    owner_rows = owner_rows[
        (owner_rows["offering_id"].astype(str) == str(offering_id))
        & (owner_rows["offering_owner_id"].astype(str) == str(offering_owner_id))
    ]
    if owner_rows.empty:
        add_flash(request, "Owner record not found.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    owner_user_principal = str(owner_rows.iloc[0].get("owner_user_principal") or "").strip()
    if not owner_user_principal:
        add_flash(request, "Owner identity is missing.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    payload = {
        "offering_id": offering_id,
        "offering_owner_id": offering_owner_id,
        "owner_user_principal": owner_user_principal,
        "owner_role": owner_role,
        "reason": reason,
    }
    try:
        if user.can_apply_change("add_offering_owner"):
            repo.update_offering_owner(
                vendor_id=vendor_id,
                offering_id=offering_id,
                offering_owner_id=offering_owner_id,
                owner_user_principal=owner_user_principal,
                owner_role=owner_role,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, "Offering owner updated.", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_offering_owner",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="update_offering_owner",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "offering_owner_id": offering_owner_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not update offering owner: {exc}", "error")

    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/offerings/{offering_id}/contacts/add")
@require_permission("offering_contact_create")
async def add_offering_contact_submit(request: Request, vendor_id: str, offering_id: str):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=f"/vendors/{vendor_id}/offerings/{offering_id}",
    )
    full_name = str(form.get("full_name", "")).strip()
    full_name_display = str(form.get("full_name_display_name", "")).strip()
    contact_type = str(form.get("contact_type", "")).strip()
    email = str(form.get("email", "")).strip()
    phone = str(form.get("phone", "")).strip()
    reason = str(form.get("reason", "")).strip()
    full_name = _normalize_contact_identity(
        full_name=full_name,
        full_name_display=full_name_display,
        email=email,
    )

    blocked_response = _redirect_if_write_blocked(request, user, redirect_url=return_to)
    if blocked_response is not None:
        return blocked_response
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {
            "offering_id": offering_id,
            "full_name": full_name,
            "contact_type": contact_type,
            "email": email,
            "phone": phone,
            "reason": reason,
        }
        if user.can_apply_change("add_offering_contact"):
            contact_id = repo.add_offering_contact(
                vendor_id=vendor_id,
                offering_id=offering_id,
                full_name=full_name,
                contact_type=contact_type,
                email=email or None,
                phone=phone or None,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Offering contact added: {contact_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="add_offering_contact",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="add_offering_contact",
            payload={"vendor_id": vendor_id, "offering_id": offering_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not add offering contact: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/offerings/{offering_id}/contacts/remove")
@require_permission("offering_contact_delete")
async def remove_offering_contact_submit(request: Request, vendor_id: str, offering_id: str):
    repo, user, form, return_to = await _resolve_write_request_context(
        request,
        default_return_to=f"/vendors/{vendor_id}/offerings/{offering_id}",
    )
    offering_contact_id = str(form.get("offering_contact_id", "")).strip()
    reason = str(form.get("reason", "")).strip()

    blocked_response = _redirect_if_write_blocked(request, user, redirect_url=return_to)
    if blocked_response is not None:
        return blocked_response
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {"offering_id": offering_id, "offering_contact_id": offering_contact_id, "reason": reason}
        if user.can_apply_change("remove_offering_contact"):
            repo.remove_offering_contact(
                vendor_id=vendor_id,
                offering_id=offering_id,
                offering_contact_id=offering_contact_id,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, "Offering contact removed.", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="remove_offering_contact",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offering_detail",
            event_type="remove_offering_contact",
            payload={"vendor_id": vendor_id, "offering_id": offering_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not remove offering contact: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)

