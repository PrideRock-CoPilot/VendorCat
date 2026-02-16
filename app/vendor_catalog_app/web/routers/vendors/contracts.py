from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.vendors.common import (
    _dedupe_ordered,
    _offering_select_options,
    _safe_return_to,
    _vendor_base_context,
    _write_blocked,
)
from vendor_catalog_app.web.routers.vendors.constants import (
    CONTRACT_CANCEL_REASON_OPTIONS,
    CONTRACT_STATUS_DEFAULT,
    CONTRACT_STATUS_OPTIONS,
    VENDOR_DEFAULT_RETURN_TO,
)
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/vendors")


@router.get("/{vendor_id}/contracts")
def vendor_contracts_page(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "contracts", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    vendor_offerings = repo.get_vendor_offerings(vendor_id).to_dict("records")
    offering_options = _offering_select_options(vendor_offerings)
    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Contracts",
        active_nav="vendors",
        extra={
            "section": "contracts",
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "summary": base["summary"],
            "contracts": repo.get_vendor_contracts(vendor_id).to_dict("records"),
            "contract_events": repo.get_vendor_contract_events(vendor_id).to_dict("records"),
            "offering_options": offering_options,
            "contract_status_options": CONTRACT_STATUS_OPTIONS,
            "contract_cancel_reason_options": CONTRACT_CANCEL_REASON_OPTIONS,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_section.html", context)


@router.post("/{vendor_id}/map-contract")
@require_permission("vendor_contract_map")
async def map_contract_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings")))
    contract_id = str(form.get("contract_id", "")).strip()
    offering_id = str(form.get("offering_id", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not contract_id:
        add_flash(request, "Contract ID is required.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    contracts_df = repo.get_vendor_contracts(vendor_id)
    if contracts_df[contracts_df["contract_id"].astype(str) == contract_id].empty:
        add_flash(request, "Contract does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if offering_id and not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Selected offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {"contract_id": contract_id, "offering_id": offering_id or None, "reason": reason}
        if user.can_apply_change("map_contract_to_offering"):
            result = repo.map_contract_to_offering(
                contract_id=contract_id,
                vendor_id=vendor_id,
                offering_id=offering_id or None,
                actor_user_principal=user.user_principal,
                reason=reason,
            )
            add_flash(
                request,
                f"Contract mapping updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="map_contract_to_offering",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offerings",
            event_type="map_contract",
            payload={"vendor_id": vendor_id, "contract_id": contract_id, "offering_id": offering_id or None},
        )
    except Exception as exc:
        add_flash(request, f"Could not map contract: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/contracts/add")@require_permission("vendor_contract_create")async def add_vendor_contract_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/contracts")))
    contract_number = str(form.get("contract_number", "")).strip()
    offering_id = str(form.get("offering_id", "")).strip() or None
    contract_status = str(form.get("contract_status", CONTRACT_STATUS_DEFAULT)).strip().lower() or CONTRACT_STATUS_DEFAULT
    start_date = str(form.get("start_date", "")).strip() or None
    end_date = str(form.get("end_date", "")).strip() or None
    annual_value_raw = str(form.get("annual_value", "")).strip()
    annual_value = annual_value_raw if annual_value_raw else None
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not contract_number:
        add_flash(request, "Contract number is required.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        if user.can_apply_change("create_contract"):
            contract_id = repo.create_contract(
                vendor_id=vendor_id,
                actor_user_principal=user.user_principal,
                contract_number=contract_number,
                contract_status=contract_status,
                offering_id=offering_id,
                start_date=start_date,
                end_date=end_date,
                annual_value=annual_value,
            )
            add_flash(request, f"Contract created: {contract_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="create_contract",
                payload={
                    "contract_number": contract_number,
                    "contract_status": contract_status,
                    "vendor_id": vendor_id,
                    "offering_id": offering_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "annual_value": annual_value,
                    "reason": reason or None,
                },
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_contracts",
            event_type="create_contract",
            payload={"vendor_id": vendor_id, "offering_id": offering_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not create contract: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/contracts/{contract_id}/cancel")@require_permission("vendor_contract_cancel")async def cancel_vendor_contract_submit(request: Request, vendor_id: str, contract_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/contracts")))
    reason_code = str(form.get("reason_code", "")).strip().lower()
    notes = str(form.get("notes", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not reason_code:
        add_flash(request, "Cancellation reason is required.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if reason_code not in set(CONTRACT_CANCEL_REASON_OPTIONS):
        add_flash(
            request,
            f"Cancellation reason must be one of: {', '.join(CONTRACT_CANCEL_REASON_OPTIONS)}",
            "error",
        )
        return RedirectResponse(url=return_to, status_code=303)

    contracts_df = repo.get_vendor_contracts(vendor_id)
    target = contracts_df[contracts_df["contract_id"].astype(str) == str(contract_id)]
    if target.empty:
        add_flash(request, "Contract does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    current_status = str(target.iloc[0].get("contract_status") or "").strip().lower()
    if current_status == "cancelled":
        add_flash(request, "Contract is already cancelled.", "info")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        if user.can_apply_change("record_contract_cancellation"):
            event_id = repo.record_contract_cancellation(
                contract_id=contract_id,
                reason_code=reason_code,
                notes=notes,
                actor_user_principal=user.user_principal,
            )
            add_flash(request, f"Contract cancellation recorded: {event_id}", "success")
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="record_contract_cancellation",
                payload={"contract_id": contract_id, "reason_code": reason_code, "notes": notes},
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_contracts",
            event_type="record_contract_cancellation",
            payload={"vendor_id": vendor_id, "contract_id": contract_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not cancel contract: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/contracts/{contract_id}/update")@require_permission("vendor_contract_update")async def update_vendor_contract_submit(request: Request, vendor_id: str, contract_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/contracts")))
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    updates = {
        "contract_number": str(form.get("contract_number", "")).strip(),
        "offering_id": str(form.get("offering_id", "")).strip() or None,
        "contract_status": str(form.get("contract_status", "")).strip().lower(),
        "start_date": str(form.get("start_date", "")).strip() or None,
        "end_date": str(form.get("end_date", "")).strip() or None,
        "annual_value": str(form.get("annual_value", "")).strip() or None,
    }

    try:
        if user.can_apply_change("update_contract"):
            result = repo.update_contract(
                vendor_id=vendor_id,
                contract_id=contract_id,
                actor_user_principal=user.user_principal,
                updates=updates,
                reason=reason,
            )
            add_flash(
                request,
                f"Contract updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="update_contract",
                payload={
                    "contract_id": contract_id,
                    "vendor_id": vendor_id,
                    "updates": updates,
                    "reason": reason or None,
                },
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_contracts",
            event_type="update_contract",
            payload={"vendor_id": vendor_id, "contract_id": contract_id},
        )
    except Exception as exc:
        add_flash(request, f"Could not update contract: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/map-contracts/bulk")
@require_permission("vendor_contract_map_bulk")
async def map_contracts_bulk_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings")))
    offering_id = str(form.get("offering_id", "")).strip()
    reason = str(form.get("reason", "")).strip()
    contract_ids = _dedupe_ordered([str(value or "").strip() for value in form.getlist("contract_ids")])

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not contract_ids:
        add_flash(request, "Select at least one contract to map.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not offering_id:
        add_flash(request, "Select an offering for bulk contract mapping.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not reason:
        add_flash(request, "Reason is required for bulk mapping.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Selected offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    contracts_df = repo.get_vendor_contracts(vendor_id)
    valid_contract_ids = {str(value).strip() for value in contracts_df.get("contract_id", pd.Series(dtype=str)).tolist()}
    invalid_contract_ids = [contract_id for contract_id in contract_ids if contract_id not in valid_contract_ids]
    if invalid_contract_ids:
        preview = ", ".join(invalid_contract_ids[:5])
        if len(invalid_contract_ids) > 5:
            preview = f"{preview}, +{len(invalid_contract_ids) - 5} more"
        add_flash(request, f"Contracts do not belong to this vendor: {preview}", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        if user.can_apply_change("map_contract_to_offering"):
            result = repo.bulk_map_contracts_to_offering(
                contract_ids=contract_ids,
                vendor_id=vendor_id,
                offering_id=offering_id,
                actor_user_principal=user.user_principal,
                reason=reason,
            )
            mapped_count = int(result.get("mapped_count", 0) or 0)
            skipped_count = int(result.get("skipped_count", 0) or 0)
            add_flash(request, f"Bulk mapped {mapped_count} contract(s) to {offering_id}.", "success")
            if skipped_count:
                add_flash(request, f"Skipped {skipped_count} contract(s) already mapped to {offering_id}.", "info")
        else:
            submitted_count = 0
            for contract_id in contract_ids:
                repo.create_vendor_change_request(
                    vendor_id=vendor_id,
                    requestor_user_principal=user.user_principal,
                    change_type="map_contract_to_offering",
                    payload={"contract_id": contract_id, "offering_id": offering_id, "reason": reason},
                )
                submitted_count += 1
            add_flash(request, f"Submitted {submitted_count} contract mapping request(s).", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offerings",
            event_type="map_contract_bulk",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "count": len(contract_ids)},
        )
    except Exception as exc:
        add_flash(request, f"Could not bulk map contracts: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)

