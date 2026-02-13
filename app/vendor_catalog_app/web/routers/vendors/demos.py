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
    _safe_return_to,
    _vendor_base_context,
    _write_blocked,
)
from vendor_catalog_app.web.routers.vendors.constants import VENDOR_DEFAULT_RETURN_TO

router = APIRouter(prefix="/vendors")


@router.get("/{vendor_id}/demos")
def vendor_demos_page(request: Request, vendor_id: str, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    repo = get_repo()
    base = _vendor_base_context(repo, request, vendor_id, "demos", return_to)
    if base is None:
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    context = base_template_context(
        request=request,
        context=base["user"],
        title=f"{base['display_name']} - Demos",
        active_nav="vendors",
        extra={
            "section": "demos",
            "vendor_id": vendor_id,
            "vendor_display_name": base["display_name"],
            "return_to": base["return_to"],
            "vendor_nav": base["vendor_nav"],
            "summary": base["summary"],
            "demos": repo.get_vendor_demos(vendor_id).to_dict("records"),
            "demo_scores": repo.get_vendor_demo_scores(vendor_id).to_dict("records"),
            "demo_notes": repo.get_vendor_demo_notes(vendor_id).to_dict("records"),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_section.html", context)


@router.post("/{vendor_id}/map-demo")
async def map_demo_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings")))
    demo_id = str(form.get("demo_id", "")).strip()
    offering_id = str(form.get("offering_id", "")).strip()
    reason = str(form.get("reason", "")).strip()

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not demo_id:
        add_flash(request, "Demo ID is required.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    demos_df = repo.get_vendor_demos(vendor_id)
    if demos_df[demos_df["demo_id"].astype(str) == demo_id].empty:
        add_flash(request, "Demo does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if offering_id and not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Selected offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        payload = {"demo_id": demo_id, "offering_id": offering_id or None, "reason": reason}
        if user.can_apply_change("map_demo_to_offering"):
            result = repo.map_demo_to_offering(
                demo_id=demo_id,
                vendor_id=vendor_id,
                offering_id=offering_id or None,
                actor_user_principal=user.user_principal,
                reason=reason,
            )
            add_flash(
                request,
                f"Demo mapping updated. Request ID: {result['request_id']} | Audit Event: {result['change_event_id']}",
                "success",
            )
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id,
                requestor_user_principal=user.user_principal,
                change_type="map_demo_to_offering",
                payload=payload,
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offerings",
            event_type="map_demo",
            payload={"vendor_id": vendor_id, "demo_id": demo_id, "offering_id": offering_id or None},
        )
    except Exception as exc:
        add_flash(request, f"Could not map demo: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)


@router.post("/{vendor_id}/map-demos/bulk")
async def map_demos_bulk_submit(request: Request, vendor_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    return_to = _safe_return_to(str(form.get("return_to", f"/vendors/{vendor_id}/offerings")))
    offering_id = str(form.get("offering_id", "")).strip()
    reason = str(form.get("reason", "")).strip()
    demo_ids = _dedupe_ordered([str(value or "").strip() for value in form.getlist("demo_ids")])

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have edit permission.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not demo_ids:
        add_flash(request, "Select at least one demo to map.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not offering_id:
        add_flash(request, "Select an offering for bulk demo mapping.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not reason:
        add_flash(request, "Reason is required for bulk mapping.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not repo.offering_belongs_to_vendor(vendor_id, offering_id):
        add_flash(request, "Selected offering does not belong to this vendor.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    demos_df = repo.get_vendor_demos(vendor_id)
    valid_demo_ids = {str(value).strip() for value in demos_df.get("demo_id", pd.Series(dtype=str)).tolist()}
    invalid_demo_ids = [demo_id for demo_id in demo_ids if demo_id not in valid_demo_ids]
    if invalid_demo_ids:
        preview = ", ".join(invalid_demo_ids[:5])
        if len(invalid_demo_ids) > 5:
            preview = f"{preview}, +{len(invalid_demo_ids) - 5} more"
        add_flash(request, f"Demos do not belong to this vendor: {preview}", "error")
        return RedirectResponse(url=return_to, status_code=303)

    try:
        if user.can_apply_change("map_demo_to_offering"):
            result = repo.bulk_map_demos_to_offering(
                demo_ids=demo_ids,
                vendor_id=vendor_id,
                offering_id=offering_id,
                actor_user_principal=user.user_principal,
                reason=reason,
            )
            mapped_count = int(result.get("mapped_count", 0) or 0)
            skipped_count = int(result.get("skipped_count", 0) or 0)
            add_flash(request, f"Bulk mapped {mapped_count} demo(s) to {offering_id}.", "success")
            if skipped_count:
                add_flash(request, f"Skipped {skipped_count} demo(s) already mapped to {offering_id}.", "info")
        else:
            submitted_count = 0
            for demo_id in demo_ids:
                repo.create_vendor_change_request(
                    vendor_id=vendor_id,
                    requestor_user_principal=user.user_principal,
                    change_type="map_demo_to_offering",
                    payload={"demo_id": demo_id, "offering_id": offering_id, "reason": reason},
                )
                submitted_count += 1
            add_flash(request, f"Submitted {submitted_count} demo mapping request(s).", "success")
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="vendor_offerings",
            event_type="map_demo_bulk",
            payload={"vendor_id": vendor_id, "offering_id": offering_id, "count": len(demo_ids)},
        )
    except Exception as exc:
        add_flash(request, f"Could not bulk map demos: {exc}", "error")
    return RedirectResponse(url=return_to, status_code=303)

