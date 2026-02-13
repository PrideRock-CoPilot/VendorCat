from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.repository import UNKNOWN_USER_PRINCIPAL
from vendor_catalog_app.web.flash import add_flash
from vendor_catalog_app.web.routers.demos.common import (
    DEMO_CLOSED_OUTCOMES,
    DEMO_REVIEW_SUBMISSION_NOTE_TYPE,
    DEMO_REVIEW_TEMPLATE_NOTE_TYPE,
    build_review_summary,
    normalize_selection_outcome,
    parse_template_note,
    today_iso,
)
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

    rows = repo.demo_outcomes().to_dict("records")
    for row in rows:
        demo_id = str(row.get("demo_id") or "").strip()
        row["review_form_url"] = f"/demos/{demo_id}/review-form" if demo_id else ""

    context = base_template_context(
        request=request,
        context=user,
        title="Demo Outcomes",
        active_nav="demos",
        extra={
            "rows": rows,
            "today": today_iso(),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "demos.html", context)


@router.get("/{demo_id}/review-form")
def demo_review_form(request: Request, demo_id: str):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Demo Review Form")

    demo = repo.get_demo_outcome_by_id(demo_id)
    if demo is None:
        add_flash(request, "Demo not found.", "error")
        return RedirectResponse(url="/demos", status_code=303)

    template_rows = repo.list_demo_notes_by_demo(
        demo_id,
        note_type=DEMO_REVIEW_TEMPLATE_NOTE_TYPE,
        limit=20,
    ).to_dict("records")
    submission_rows = repo.list_demo_notes_by_demo(
        demo_id,
        note_type=DEMO_REVIEW_SUBMISSION_NOTE_TYPE,
        limit=500,
    ).to_dict("records")
    template = parse_template_note(template_rows)
    summary = build_review_summary(template=template, submission_rows=submission_rows)

    selection_outcome = normalize_selection_outcome(demo.get("selection_outcome"))
    is_closed = selection_outcome in DEMO_CLOSED_OUTCOMES
    can_submit_review = (
        not user.config.locked_mode and str(user.user_principal or "").strip() not in {"", UNKNOWN_USER_PRINCIPAL}
    )

    context = base_template_context(
        request=request,
        context=user,
        title=f"Demo Review Form - {demo_id}",
        active_nav="demos",
        extra={
            "demo": demo,
            "demo_id": demo_id,
            "review_template": template,
            "review_summary": summary,
            "is_demo_closed": is_closed,
            "can_submit_review": can_submit_review,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "demo_review_form.html", context)

