from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.http.flash import add_flash

router = APIRouter(prefix="/contracts")


@router.post("/cancel")
async def record_cancellation(request: Request):
    _ = await request.form()
    add_flash(
        request,
        "Contract cancellation is managed in Vendor 360 (Vendor -> Contracts or Offering -> Delivery).",
        "info",
    )
    return RedirectResponse(url="/contracts", status_code=303)


