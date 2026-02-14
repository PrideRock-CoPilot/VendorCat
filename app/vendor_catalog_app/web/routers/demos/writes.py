from __future__ import annotations

import json
import uuid
from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from vendor_catalog_app.repository import (
    GLOBAL_CHANGE_VENDOR_ID,
    UNKNOWN_USER_PRINCIPAL,
)
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.demos.common import (
    DEMO_REVIEW_SUBMISSION_V2_NOTE_TYPE,
    DEMO_REVIEW_TEMPLATE_LIBRARY_ENTITY,
    DEMO_REVIEW_TEMPLATE_LIBRARY_NOTE_TYPE,
    DEMO_REVIEW_TEMPLATE_NOTE_TYPES,
    DEMO_REVIEW_TEMPLATE_V2_NOTE_TYPE,
    DEMO_STAGE_NOTE_TYPE,
    DEMO_STAGE_ORDER,
    build_submission_from_form,
    is_demo_session_open,
    normalize_demo_stage,
    normalize_selection_outcome,
    parse_template_note,
    parse_template_questions_from_form,
)

router = APIRouter(prefix="/demos")


def _list_template_rows(repo, demo_id: str) -> list[dict]:
    rows: list[dict] = []
    for note_type in DEMO_REVIEW_TEMPLATE_NOTE_TYPES:
        rows.extend(
            repo.list_demo_notes_by_demo(
                demo_id,
                note_type=note_type,
                limit=20,
            ).to_dict("records")
        )
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return rows


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
            try:
                repo.create_demo_note(
                    demo_id=demo_id,
                    note_type=DEMO_STAGE_NOTE_TYPE,
                    note_text=json.dumps(
                        {
                            "version": "v1",
                            "stage": "scheduled",
                            "notes": "Demo record created.",
                        }
                    ),
                    actor_user_principal=user.user_principal,
                )
            except Exception:
                pass
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


@router.post("/{demo_id}/stage")
async def update_demo_stage(request: Request, demo_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}", status_code=303)
    if not user.can_edit:
        add_flash(request, "Edit permission is required to update demo stage.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}", status_code=303)

    stage = normalize_demo_stage(str(form.get("stage", "")).strip())
    notes = str(form.get("notes", "")).strip()
    if stage not in set(DEMO_STAGE_ORDER):
        add_flash(request, "Invalid stage selected.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}", status_code=303)

    demo = repo.get_demo_outcome_by_id(demo_id)
    if demo is None:
        add_flash(request, "Demo not found.", "error")
        return RedirectResponse(url="/demos", status_code=303)

    payload = {"version": "v1", "stage": stage, "notes": notes}
    try:
        repo.create_demo_note(
            demo_id=demo_id,
            note_type=DEMO_STAGE_NOTE_TYPE,
            note_text=json.dumps(payload),
            actor_user_principal=user.user_principal,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="demos",
            event_type="update_demo_stage",
            payload={"demo_id": demo_id, "stage": stage},
        )
        add_flash(request, f"Demo stage updated: {stage}", "success")
    except Exception as exc:
        add_flash(request, f"Could not update stage: {exc}", "error")
    return RedirectResponse(url=f"/demos/{demo_id}", status_code=303)


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

    title = str(form.get("template_title", "Demo Review Form")).strip() or "Demo Review Form"
    instructions = str(form.get("instructions", "")).strip()
    try:
        questions = parse_template_questions_from_form(form)
    except ValueError as exc:
        add_flash(request, str(exc), "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)

    payload = {
        "version": "v2",
        "title": title,
        "instructions": instructions,
        "questions": questions,
    }
    payload_text = json.dumps(payload)

    try:
        library_note_id = repo.create_app_note(
            entity_name=DEMO_REVIEW_TEMPLATE_LIBRARY_ENTITY,
            entity_id=str(uuid.uuid4()),
            note_type=DEMO_REVIEW_TEMPLATE_LIBRARY_NOTE_TYPE,
            note_text=payload_text,
            actor_user_principal=user.user_principal,
        )

        attach_now = str(form.get("attach_now", "1")).strip().lower() not in {"0", "false", "off", "no"}
        attached_note_id = None
        if attach_now:
            attach_payload = dict(payload)
            attach_payload["source_template_note_id"] = library_note_id
            attached_note_id = repo.create_demo_note(
                demo_id=demo_id,
                note_type=DEMO_REVIEW_TEMPLATE_V2_NOTE_TYPE,
                note_text=json.dumps(attach_payload),
                actor_user_principal=user.user_principal,
            )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="demos",
            event_type="save_demo_review_template_v2",
            payload={
                "demo_id": demo_id,
                "library_note_id": library_note_id,
                "attached_note_id": attached_note_id,
                "question_count": len(questions),
            },
        )
        if attached_note_id:
            add_flash(request, "Template saved to library and attached to this demo.", "success")
        else:
            add_flash(request, "Template saved to library.", "success")
    except Exception as exc:
        add_flash(request, f"Could not save review template: {exc}", "error")
    return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)


@router.post("/{demo_id}/review-form/template/attach")
async def attach_demo_review_template(request: Request, demo_id: str):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)
    if not user.can_edit:
        add_flash(request, "Edit permission is required to attach templates.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)

    demo = repo.get_demo_outcome_by_id(demo_id)
    if demo is None:
        add_flash(request, "Demo not found.", "error")
        return RedirectResponse(url="/demos", status_code=303)

    library_template_id = str(form.get("library_template_id", "")).strip()
    if not library_template_id:
        add_flash(request, "Select a template to attach.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)

    template_note = repo.get_app_note_by_id(library_template_id)
    if template_note is None:
        add_flash(request, "Template not found.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)
    if str(template_note.get("entity_name") or "").strip().lower() != DEMO_REVIEW_TEMPLATE_LIBRARY_ENTITY:
        add_flash(request, "Template type is invalid.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)
    if str(template_note.get("note_type") or "").strip().lower() != DEMO_REVIEW_TEMPLATE_LIBRARY_NOTE_TYPE:
        add_flash(request, "Template note type is invalid.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)

    template_payload = parse_template_note([template_note])
    if not template_payload:
        add_flash(request, "Template payload is invalid.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)

    attach_payload = {
        "version": "v2",
        "title": template_payload.get("title"),
        "instructions": template_payload.get("instructions"),
        "questions": template_payload.get("questions") or [],
        "source_template_note_id": library_template_id,
    }
    try:
        attached_note_id = repo.create_demo_note(
            demo_id=demo_id,
            note_type=DEMO_REVIEW_TEMPLATE_V2_NOTE_TYPE,
            note_text=json.dumps(attach_payload),
            actor_user_principal=user.user_principal,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="demos",
            event_type="attach_demo_review_template",
            payload={
                "demo_id": demo_id,
                "library_note_id": library_template_id,
                "attached_note_id": attached_note_id,
            },
        )
        add_flash(request, "Template attached to demo.", "success")
    except Exception as exc:
        add_flash(request, f"Could not attach template: {exc}", "error")
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

    stage_rows = repo.list_demo_notes_by_demo(
        demo_id,
        note_type=DEMO_STAGE_NOTE_TYPE,
        limit=200,
    ).to_dict("records")
    if not is_demo_session_open(demo=demo, stage_rows=stage_rows):
        add_flash(request, "Demo session is closed. Review answers can only be updated while the session is open.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)

    template_rows = _list_template_rows(repo, demo_id)
    template = parse_template_note(template_rows)
    if not template:
        add_flash(request, "A review template must be attached before submissions are accepted.", "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)

    try:
        scored = build_submission_from_form(template=template, form_data=form)
    except ValueError as exc:
        add_flash(request, str(exc), "error")
        return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)

    comment = str(form.get("review_comment", "")).strip()
    payload = {
        "version": "v2",
        "template_note_id": template.get("template_note_id"),
        "template_title": template.get("title"),
        "answers": scored.get("answers") or [],
        "overall_score": scored.get("overall_score"),
        "weighted_score_total": scored.get("weighted_score_total"),
        "weighted_max_total": scored.get("weighted_max_total"),
        "comment": comment,
    }
    payload_text = json.dumps(payload)

    try:
        existing_rows = repo.list_demo_notes_by_demo_and_creator(
            demo_id,
            note_type=DEMO_REVIEW_SUBMISSION_V2_NOTE_TYPE,
            created_by=user.user_principal,
            limit=1,
        ).to_dict("records")
        if existing_rows:
            review_note_id = str(existing_rows[0].get("demo_note_id") or "").strip()
            repo.update_demo_note_text(
                demo_note_id=review_note_id,
                demo_id=demo_id,
                note_type=DEMO_REVIEW_SUBMISSION_V2_NOTE_TYPE,
                note_text=payload_text,
                actor_user_principal=user.user_principal,
            )
            event_type = "update_demo_review_form"
            action_label = "updated"
        else:
            review_note_id = repo.create_demo_note(
                demo_id=demo_id,
                note_type=DEMO_REVIEW_SUBMISSION_V2_NOTE_TYPE,
                note_text=payload_text,
                actor_user_principal=user.user_principal,
            )
            event_type = "submit_demo_review_form"
            action_label = "submitted"

        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="demos",
            event_type=event_type,
            payload={
                "demo_id": demo_id,
                "review_note_id": review_note_id,
                "overall_score": scored.get("overall_score"),
            },
        )
        add_flash(request, f"Review {action_label}. Overall score: {float(scored.get('overall_score') or 0):.2f}", "success")
    except Exception as exc:
        add_flash(request, f"Could not submit review form: {exc}", "error")
    return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)
