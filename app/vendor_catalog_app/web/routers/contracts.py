from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.flash import add_flash
from vendor_catalog_app.web.services import (
    base_template_context,
    ensure_session_started,
    get_repo,
    get_user_context,
    log_page_view,
)


router = APIRouter(prefix="/contracts")


@router.get("")
def contracts(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Contract Cancellations")

    context = base_template_context(
        request=request,
        context=user,
        title="Contract Cancellations",
        active_nav="contracts",
        extra={"rows": repo.contract_cancellations().to_dict("records")},
    )
    return request.app.state.templates.TemplateResponse(request, "contracts.html", context)


@router.post("/cancel")
async def record_cancellation(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()

    if not user.can_edit:
        add_flash(request, "View-only mode. You cannot record cancellations.", "error")
        return RedirectResponse(url="/contracts", status_code=303)

    contract_id = str(form.get("contract_id", "")).strip()
    reason_code = str(form.get("reason_code", "")).strip()
    notes = str(form.get("notes", "")).strip()

    if not contract_id or not reason_code:
        add_flash(request, "Contract ID and reason code are required.", "error")
        return RedirectResponse(url="/contracts", status_code=303)

    event_id = repo.record_contract_cancellation(
        contract_id=contract_id,
        reason_code=reason_code,
        notes=notes,
        actor_user_principal=user.user_principal,
    )
    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="contracts",
        event_type="record_contract_cancellation",
        payload={"contract_id": contract_id, "event_id": event_id},
    )
    add_flash(request, f"Contract cancellation recorded: {event_id}", "success")
    return RedirectResponse(url="/contracts", status_code=303)

