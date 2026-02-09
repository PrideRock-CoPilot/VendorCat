from __future__ import annotations

from datetime import date

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


router = APIRouter(prefix="/demos")


@router.get("")
def demos(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Demo Outcomes")

    context = base_template_context(
        request=request,
        context=user,
        title="Demo Outcomes",
        active_nav="demos",
        extra={
            "rows": repo.demo_outcomes().to_dict("records"),
            "today": date.today().isoformat(),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "demos.html", context)


@router.post("")
async def create_demo(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()

    if not user.can_edit:
        add_flash(request, "View-only mode. You cannot add demo outcomes.", "error")
        return RedirectResponse(url="/demos", status_code=303)

    vendor_id = str(form.get("vendor_id", "")).strip()
    offering_id = str(form.get("offering_id", "")).strip() or None
    demo_date = str(form.get("demo_date", date.today().isoformat()))
    selection_outcome = str(form.get("selection_outcome", "deferred"))
    non_selection_reason = str(form.get("non_selection_reason_code", "")).strip() or None
    notes = str(form.get("notes", "")).strip()

    try:
        overall_score = float(str(form.get("overall_score", "0")).strip() or 0)
    except ValueError:
        add_flash(request, "Overall score must be a number.", "error")
        return RedirectResponse(url="/demos", status_code=303)

    if selection_outcome == "not_selected" and not non_selection_reason:
        add_flash(request, "Non-selection reason is required for not_selected outcomes.", "error")
        return RedirectResponse(url="/demos", status_code=303)

    demo_id = repo.create_demo_outcome(
        vendor_id=vendor_id,
        offering_id=offering_id,
        demo_date=demo_date,
        overall_score=overall_score,
        selection_outcome=selection_outcome,
        non_selection_reason_code=non_selection_reason,
        notes=notes,
        actor_user_principal=user.user_principal,
    )
    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="demos",
        event_type="create_demo_outcome",
        payload={"demo_id": demo_id, "vendor_id": vendor_id},
    )
    add_flash(request, f"Demo outcome saved: {demo_id}", "success")
    return RedirectResponse(url="/demos", status_code=303)

