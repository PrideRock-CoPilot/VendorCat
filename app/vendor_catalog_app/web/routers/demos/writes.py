from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.repository import GLOBAL_CHANGE_VENDOR_ID, UNKNOWN_USER_PRINCIPAL
from vendor_catalog_app.web.flash import add_flash
from vendor_catalog_app.web.routers.demos.common import (
    DEMO_REVIEW_SUBMISSION_NOTE_TYPE,
    DEMO_REVIEW_TEMPLATE_NOTE_TYPE,
    normalize_selection_outcome,
    parse_criteria_csv,
    parse_template_note,
)
from vendor_catalog_app.web.services import get_repo, get_user_context


router = APIRouter(prefix="/demos")


@router.post("")
async def create_demo(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url="/demos", status_code=303)
    if not user.can_edit:
        add_flash(request, "View-only mode. You cannot add demo outcomes.", "error")
        return RedirectResponse(url="/demos", status_code=303)

    vendor_id = str(form.get("vendor_id", "")).strip()
    offering_id = str(form.get("offering_id", "")).strip() or None
    demo_date = str(form.get("demo_date", date.today().isoformat()))
    selection_outcome = normalize_selection_outcome(str(form.get("selection_outcome", "deferred")))
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

    try:
        if user.can_apply_change("create_demo_outcome"):
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
        else:
            request_id = repo.create_vendor_change_request(
                vendor_id=vendor_id or GLOBAL_CHANGE_VENDOR_ID,
                requestor_user_principal=user.user_principal,
                change_type="create_demo_outcome",
                payload={
                    "vendor_id": vendor_id,
                    "offering_id": offering_id,
                    "demo_date": demo_date,
                    "overall_score": overall_score,
                    "selection_outcome": selection_outcome,
                    "non_selection_reason_code": non_selection_reason,
                    "notes": notes,
                },
            )
            add_flash(request, f"Pending change request submitted: {request_id}", "success")
    except Exception as exc:
        add_flash(request, f"Could not submit demo change: {exc}", "error")
    return RedirectResponse(url="/demos", status_code=303)


@router.post("/{demo_id}/review-form/template")
async def save_demo_review_template(request: Request, demo_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)
    if not user.can_edit:
        add_flash(request, "Edit permission is required to manage review templates.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)

    demo = repo.get_demo_outcome_by_id(demo_id)
    if demo is None:
        add_flash(request, "Demo not found.", "error")
        return RedirectResponse(url="/demos", status_code=303)

    title = str(form.get("template_title", "Demo Scorecard")).strip() or "Demo Scorecard"
    criteria_csv = str(form.get("criteria_csv", "")).strip()
    instructions = str(form.get("instructions", "")).strip()
    try:
        max_score = float(str(form.get("max_score", "10")).strip() or 10.0)
    except Exception:
        max_score = 10.0
    max_score = max(1.0, min(max_score, 100.0))

    try:
        criteria = parse_criteria_csv(criteria_csv, max_score=max_score)
    except ValueError as exc:
        add_flash(request, str(exc), "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)

    payload = {
        "version": "v1",
        "title": title,
        "instructions": instructions,
        "criteria": criteria,
    }
    try:
        note_id = repo.create_demo_note(
            demo_id=demo_id,
            note_type=DEMO_REVIEW_TEMPLATE_NOTE_TYPE,
            note_text=json.dumps(payload),
            actor_user_principal=user.user_principal,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="demos",
            event_type="save_demo_review_template",
            payload={"demo_id": demo_id, "template_note_id": note_id, "criteria_count": len(criteria)},
        )
        add_flash(request, "Review form template saved.", "success")
    except Exception as exc:
        add_flash(request, f"Could not save review template: {exc}", "error")
    return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)


@router.post("/{demo_id}/review-form/submit")
async def submit_demo_review_form(request: Request, demo_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)
    if str(user.user_principal or "").strip() in {"", UNKNOWN_USER_PRINCIPAL}:
        add_flash(request, "A valid user identity is required to submit a review form.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)

    demo = repo.get_demo_outcome_by_id(demo_id)
    if demo is None:
        add_flash(request, "Demo not found.", "error")
        return RedirectResponse(url="/demos", status_code=303)

    template_rows = repo.list_demo_notes_by_demo(
        demo_id,
        note_type=DEMO_REVIEW_TEMPLATE_NOTE_TYPE,
        limit=20,
    ).to_dict("records")
    template = parse_template_note(template_rows)
    if not template:
        add_flash(request, "A review template must be created before submissions are accepted.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)

    score_rows: list[dict[str, object]] = []
    normalized_total = 0.0
    for criterion in template.get("criteria") or []:
        code = str(criterion.get("code") or "").strip().lower()
        label = str(criterion.get("label") or code)
        max_score = float(criterion.get("max_score") or 10.0)
        raw_value = str(form.get(f"score_{code}", "")).strip()
        if not raw_value:
            add_flash(request, f"Score is required for {label}.", "error")
            return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)
        try:
            score_value = float(raw_value)
        except Exception:
            add_flash(request, f"Score must be numeric for {label}.", "error")
            return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)
        if score_value < 0 or score_value > max_score:
            add_flash(request, f"Score for {label} must be between 0 and {max_score:g}.", "error")
            return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)

        normalized_total += (score_value / max_score) * 10.0
        score_rows.append(
            {
                "code": code,
                "label": label,
                "score": score_value,
                "max_score": max_score,
            }
        )

    overall_score = round(normalized_total / max(1, len(score_rows)), 2)
    comment = str(form.get("review_comment", "")).strip()
    payload = {
        "version": "v1",
        "template_note_id": template.get("template_note_id"),
        "template_title": template.get("title"),
        "scores": score_rows,
        "overall_score": overall_score,
        "comment": comment,
    }

    try:
        note_id = repo.create_demo_note(
            demo_id=demo_id,
            note_type=DEMO_REVIEW_SUBMISSION_NOTE_TYPE,
            note_text=json.dumps(payload),
            actor_user_principal=user.user_principal,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="demos",
            event_type="submit_demo_review_form",
            payload={"demo_id": demo_id, "review_note_id": note_id, "overall_score": overall_score},
        )
        add_flash(request, f"Review submitted. Overall score: {overall_score:.2f}", "success")
    except Exception as exc:
        add_flash(request, f"Could not submit review form: {exc}", "error")
    return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)

