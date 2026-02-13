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
    _ = await request.form()
    add_flash(
        request,
        "Contract cancellation is managed in Vendor 360 (Vendor -> Contracts or Offering -> Delivery).",
        "info",
    )
    return RedirectResponse(url="/contracts", status_code=303)
