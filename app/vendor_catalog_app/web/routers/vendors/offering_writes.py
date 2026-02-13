from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.flash import add_flash
from vendor_catalog_app.web.routers.vendors.common import _safe_return_to, _write_blocked
from vendor_catalog_app.web.routers.vendors.constants import OFFERING_INVOICE_STATUSES, VENDOR_DEFAULT_RETURN_TO
from vendor_catalog_app.web.services import get_repo, get_user_context


router = APIRouter(prefix="/vendors")


@router.post("/{vendor_id}/offerings/{offering_id}/invoices/add")
async def add_offering_invoice_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))
    invoice_number = str(form.get("invoice_number", "")).strip()
    invoice_date = str(form.get("invoice_date", "")).strip()
    amount_raw = str(form.get("amount", "")).strip()
    currency_code = str(form.get("currency_code", "USD")).strip().upper() or "USD"
    invoice_status = str(form.get("invoice_status", "received")).strip().lower() or "received"
    notes = str(form.get("notes", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=financials&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=financials&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
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
async def remove_offering_invoice_submit(request: Request, vendor_id: str, offering_id: str, invoice_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(
            url=f"/vendors/{vendor_id}/offerings/{offering_id}?section=financials&return_to={quote(return_to, safe='')}",
            status_code=303,
        )
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
async def add_offering_owner_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings/{offering_id}")))
    owner_user_principal = str(form.get("owner_user_principal", "")).strip()
    owner_role = str(form.get("owner_role", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
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
async def remove_offering_owner_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings/{offering_id}")))
    offering_owner_id = str(form.get("offering_owner_id", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

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


@router.post("/{vendor_id}/offerings/{offering_id}/contacts/add")
async def add_offering_contact_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings/{offering_id}")))
    full_name = str(form.get("full_name", "")).strip()
    contact_type = str(form.get("contact_type", "")).strip()
    email = str(form.get("email", "")).strip()
    phone = str(form.get("phone", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
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
async def remove_offering_contact_submit(request: Request, vendor_id: str, offering_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings/{offering_id}")))
    offering_contact_id = str(form.get("offering_contact_id", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
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
