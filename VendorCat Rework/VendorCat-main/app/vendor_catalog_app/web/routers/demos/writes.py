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
    build_template_library_index,
    is_demo_session_open,
    normalize_demo_stage,
    normalize_selection_outcome,
    parse_template_note,
    parse_template_questions_from_form,
)
from vendor_catalog_app.web.security.rbac import require_permission

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


def _load_template_catalog(repo, *, include_inactive: bool = True) -> list[dict]:
    rows = repo.list_app_notes_by_entity_and_type(
        entity_name=DEMO_REVIEW_TEMPLATE_LIBRARY_ENTITY,
        note_type=DEMO_REVIEW_TEMPLATE_LIBRARY_NOTE_TYPE,
        limit=2000,
    ).to_dict("records")
    return build_template_library_index(rows, include_inactive=include_inactive)


def _next_template_version(catalog: list[dict], template_key: str) -> int:
    key = str(template_key or "").strip()
    if not key:
        return 1
    for entry in catalog:
        if str(entry.get("template_key") or "").strip() == key:
            return int(entry.get("current_version") or 0) + 1
    return 1


def _new_template_key() -> str:
    return f"frm-{str(uuid.uuid4())[:8]}"


@router.post("")
@require_permission("demo_create")
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
@require_permission("demo_stage")
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


@router.post("/forms/save")
@require_permission("demo_form_save")
async def save_demo_form_template(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()

    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url="/demos/forms", status_code=303)
    if not user.can_edit:
        add_flash(request, "Edit permission is required to manage forms.", "error")
        return RedirectResponse(url="/demos/forms", status_code=303)

    title = str(form.get("template_title", "Demo Review Form")).strip() or "Demo Review Form"
    instructions = str(form.get("instructions", "")).strip()
    template_key = str(form.get("template_key", "")).strip()
    try:
        questions = parse_template_questions_from_form(form)
    except ValueError as exc:
        add_flash(request, str(exc), "error")
        redirect_url = f"/demos/forms?template_key={template_key}" if template_key else "/demos/forms"
        return RedirectResponse(url=redirect_url, status_code=303)

    catalog = _load_template_catalog(repo, include_inactive=True)
    if not template_key:
        template_key = _new_template_key()
    template_version = _next_template_version(catalog, template_key)
    payload = {
        "version": "v2",
        "template_key": template_key,
        "template_version": template_version,
        "template_status": "active",
        "title": title,
        "instructions": instructions,
        "questions": questions,
    }

    try:
        template_note_id = repo.create_app_note(
            entity_name=DEMO_REVIEW_TEMPLATE_LIBRARY_ENTITY,
            entity_id=template_key,
            note_type=DEMO_REVIEW_TEMPLATE_LIBRARY_NOTE_TYPE,
            note_text=json.dumps(payload),
            actor_user_principal=user.user_principal,
        )
        repo.log_usage_event(
            user_principal=user.user_principal,
            page_name="demos_forms",
            event_type="save_demo_form_template",
            payload={
                "template_note_id": template_note_id,
                "template_key": template_key,
                "template_version": template_version,
                "question_count": len(questions),
            },
        )
        add_flash(request, f"Form template saved as version {template_version}.", "success")
    except Exception as exc:
        add_flash(request, f"Could not save form template: {exc}", "error")
    return RedirectResponse(url=f"/demos/forms?template_key={template_key}", status_code=303)


@router.post("/forms/{template_key}/copy")
@require_permission("demo_form_copy")
async def copy_demo_form_template(request: Request, template_key: str):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url="/demos/forms", status_code=303)
    if not user.can_edit:
        add_flash(request, "Edit permission is required to copy forms.", "error")
        return RedirectResponse(url="/demos/forms", status_code=303)

    catalog = _load_template_catalog(repo, include_inactive=True)
    source_entry = None
    for entry in catalog:
        if str(entry.get("template_key") or "").strip() == str(template_key or "").strip():
            source_entry = entry
            break
    if source_entry is None:
        add_flash(request, "Form template not found.", "error")
        return RedirectResponse(url="/demos/forms", status_code=303)

    source_template = source_entry.get("latest_template") or {}
    new_key = _new_template_key()
    payload = {
        "version": "v2",
        "template_key": new_key,
        "template_version": 1,
        "template_status": "active",
        "title": f"Copy of {str(source_template.get('title') or 'Demo Review Form')}".strip()[:140],
        "instructions": str(source_template.get("instructions") or "").strip(),
        "questions": source_template.get("questions") or [],
        "copied_from_template_key": str(source_entry.get("template_key") or "").strip(),
        "copied_from_template_version": int(source_entry.get("current_version") or 1),
    }

    try:
        repo.create_app_note(
            entity_name=DEMO_REVIEW_TEMPLATE_LIBRARY_ENTITY,
            entity_id=new_key,
            note_type=DEMO_REVIEW_TEMPLATE_LIBRARY_NOTE_TYPE,
            note_text=json.dumps(payload),
            actor_user_principal=user.user_principal,
        )
        add_flash(request, "Form template copied.", "success")
    except Exception as exc:
        add_flash(request, f"Could not copy form template: {exc}", "error")
        return RedirectResponse(url="/demos/forms", status_code=303)
    return RedirectResponse(url=f"/demos/forms?template_key={new_key}", status_code=303)


@router.post("/forms/{template_key}/delete")
@require_permission("demo_form_delete")
async def delete_demo_form_template(request: Request, template_key: str):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url="/demos/forms", status_code=303)
    if not user.can_edit:
        add_flash(request, "Edit permission is required to delete forms.", "error")
        return RedirectResponse(url="/demos/forms", status_code=303)

    catalog = _load_template_catalog(repo, include_inactive=True)
    target_entry = None
    for entry in catalog:
        if str(entry.get("template_key") or "").strip() == str(template_key or "").strip():
            target_entry = entry
            break
    if target_entry is None:
        add_flash(request, "Form template not found.", "error")
        return RedirectResponse(url="/demos/forms", status_code=303)

    latest_template = target_entry.get("latest_template") or {}
    latest_status = str(target_entry.get("status") or "").strip().lower()
    if latest_status == "deleted":
        add_flash(request, "Form template is already deleted.", "info")
        return RedirectResponse(url="/demos/forms", status_code=303)

    payload = {
        "version": "v2",
        "template_key": str(target_entry.get("template_key") or "").strip(),
        "template_version": int(target_entry.get("current_version") or 1) + 1,
        "template_status": "deleted",
        "title": str(latest_template.get("title") or "Deleted Form").strip() or "Deleted Form",
        "instructions": str(latest_template.get("instructions") or "").strip(),
        "questions": latest_template.get("questions") or [],
    }
    try:
        repo.create_app_note(
            entity_name=DEMO_REVIEW_TEMPLATE_LIBRARY_ENTITY,
            entity_id=str(target_entry.get("template_key") or "").strip(),
            note_type=DEMO_REVIEW_TEMPLATE_LIBRARY_NOTE_TYPE,
            note_text=json.dumps(payload),
            actor_user_principal=user.user_principal,
        )
        add_flash(request, "Form template deleted. Existing demo usages are preserved.", "success")
    except Exception as exc:
        add_flash(request, f"Could not delete form template: {exc}", "error")
    return RedirectResponse(url="/demos/forms", status_code=303)


@router.post("/{demo_id}/review-form/template")
@require_permission("demo_review_form_template")
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

    template_key = str(form.get("template_key", "")).strip()
    catalog = _load_template_catalog(repo, include_inactive=True)
    if not template_key:
        template_key = _new_template_key()
    template_version = _next_template_version(catalog, template_key)
    payload = {
        "version": "v2",
        "template_key": template_key,
        "template_version": template_version,
        "template_status": "active",
        "title": title,
        "instructions": instructions,
        "questions": questions,
    }
    payload_text = json.dumps(payload)

    try:
        library_note_id = repo.create_app_note(
            entity_name=DEMO_REVIEW_TEMPLATE_LIBRARY_ENTITY,
            entity_id=template_key,
            note_type=DEMO_REVIEW_TEMPLATE_LIBRARY_NOTE_TYPE,
            note_text=payload_text,
            actor_user_principal=user.user_principal,
        )

        attach_now = str(form.get("attach_now", "1")).strip().lower() not in {"0", "false", "off", "no"}
        attached_note_id = None
        if attach_now:
            attach_payload = dict(payload)
            attach_payload["source_template_note_id"] = library_note_id
            attach_payload["source_template_key"] = template_key
            attach_payload["source_template_version"] = template_version
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
                "template_key": template_key,
                "template_version": template_version,
                "question_count": len(questions),
            },
        )
        if attached_note_id:
            add_flash(
                request,
                f"Template saved (v{template_version}) and attached to this demo.",
                "success",
            )
        else:
            add_flash(request, f"Template saved to library as version {template_version}.", "success")
    except Exception as exc:
        add_flash(request, f"Could not save review template: {exc}", "error")
    return RedirectResponse(url=f"/demos/{demo_id}/review-form", status_code=303)


@router.post("/{demo_id}/review-form/template/attach")
@require_permission("demo_review_form_attach")
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
        "source_template_key": template_payload.get("template_key"),
        "source_template_version": template_payload.get("template_version"),
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
@require_permission("demo_review_form_submit")
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
