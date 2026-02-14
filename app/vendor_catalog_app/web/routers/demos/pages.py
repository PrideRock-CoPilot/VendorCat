from __future__ import annotations

import math
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from vendor_catalog_app.repository import UNKNOWN_USER_PRINCIPAL
from vendor_catalog_app.web.core.activity import ensure_session_started, log_page_view
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.demos.common import (
    DEMO_REVIEW_SUBMISSION_NOTE_TYPES,
    DEMO_STAGE_NOTE_TYPE,
    DEMO_STAGE_ORDER,
    DEMO_SELECTION_OUTCOMES,
    DEMO_REVIEW_TEMPLATE_LIBRARY_ENTITY,
    DEMO_REVIEW_TEMPLATE_LIBRARY_NOTE_TYPE,
    DEMO_REVIEW_TEMPLATE_NOTE_TYPES,
    DEMO_STAGE_LABELS,
    build_scoring_cards,
    build_stage_history,
    build_review_summary,
    is_demo_session_open,
    parse_template_library_rows,
    parse_template_note,
    today_iso,
)

router = APIRouter(prefix="/demos")
DEMO_PAGE_SIZES = [25, 50, 100, 250]
DEFAULT_DEMO_PAGE_SIZE = 25
MAX_DEMO_PAGE_SIZE = 250


def _list_demo_note_records(repo, demo_id: str, *, note_types: list[str], limit_per_type: int) -> list[dict]:
    rows: list[dict] = []
    for note_type in note_types:
        note_rows = repo.list_demo_notes_by_demo(
            demo_id,
            note_type=note_type,
            limit=limit_per_type,
        ).to_dict("records")
        rows.extend(note_rows)
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return rows


def _normalize_demo_page_size(raw_value: str | int | None) -> int:
    try:
        value = int(str(raw_value or DEFAULT_DEMO_PAGE_SIZE).strip())
    except Exception:
        return DEFAULT_DEMO_PAGE_SIZE
    return max(1, min(value, MAX_DEMO_PAGE_SIZE))


def _normalize_demo_page(raw_value: str | int | None) -> int:
    try:
        value = int(str(raw_value or 1).strip())
    except Exception:
        return 1
    return max(1, value)


def _normalize_demo_outcome_filter(raw_value: str | None) -> str:
    value = str(raw_value or "").strip().lower()
    return value if value in {"all", *DEMO_SELECTION_OUTCOMES} else "all"


def _demos_url(*, q: str, outcome: str, page: int, page_size: int) -> str:
    query = {
        "q": q,
        "outcome": outcome,
        "page": str(page),
        "page_size": str(page_size),
    }
    return f"/demos?{urlencode(query)}"


@router.get("")
def demos(
    request: Request,
    q: str = "",
    outcome: str = "all",
    page: int = 1,
    page_size: int = DEFAULT_DEMO_PAGE_SIZE,
):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Demo Outcomes")

    outcome = _normalize_demo_outcome_filter(outcome)
    page_size = _normalize_demo_page_size(page_size)
    page = _normalize_demo_page(page)

    rows_df = repo.demo_outcomes().copy()
    if outcome != "all" and "selection_outcome" in rows_df.columns:
        rows_df = rows_df[rows_df["selection_outcome"].astype(str).str.strip().str.lower() == outcome].copy()
    if q.strip():
        needle = q.strip().lower()
        searchable_columns = [
            "demo_id",
            "vendor_id",
            "offering_id",
            "selection_outcome",
            "non_selection_reason_code",
            "notes",
        ]
        mask = None
        for column in searchable_columns:
            if column not in rows_df.columns:
                continue
            col_mask = rows_df[column].astype(str).str.lower().str.contains(needle, regex=False, na=False)
            mask = col_mask if mask is None else (mask | col_mask)
        if mask is not None:
            rows_df = rows_df[mask].copy()
    if "demo_date" in rows_df.columns:
        rows_df["__demo_date_sort"] = rows_df["demo_date"].astype(str)
        rows_df = rows_df.sort_values(["__demo_date_sort", "demo_id"], ascending=[False, True], na_position="last")

    total_rows = int(len(rows_df.index))
    page_count = max(1, math.ceil(total_rows / page_size)) if total_rows else 1
    if page > page_count:
        page = page_count
    start = (page - 1) * page_size
    end = start + page_size
    rows = rows_df.iloc[start:end].to_dict("records")

    for row in rows:
        demo_id = str(row.get("demo_id") or "").strip()
        row["review_form_url"] = f"/demos/{demo_id}/review-form" if demo_id else ""
        row["workspace_url"] = f"/demos/{demo_id}" if demo_id else ""
        stage_rows = repo.list_demo_notes_by_demo(
            demo_id,
            note_type=DEMO_STAGE_NOTE_TYPE,
            limit=20,
        ).to_dict("records")
        stage_state = build_stage_history(demo=row, stage_rows=stage_rows)
        row["stage_code"] = stage_state["current_stage"]
        row["stage_label"] = stage_state["current_stage_label"]

    prev_page = page - 1 if page > 1 else 1
    next_page = page + 1 if page < page_count else page_count
    show_from = (start + 1) if total_rows else 0
    show_to = min(end, total_rows)

    context = base_template_context(
        request=request,
        context=user,
        title="Demo Outcomes",
        active_nav="demos",
        extra={
            "filters": {
                "q": q,
                "outcome": outcome,
                "page": page,
                "page_size": page_size,
            },
            "outcome_options": ["all", *DEMO_SELECTION_OUTCOMES],
            "page_sizes": DEMO_PAGE_SIZES,
            "rows": rows,
            "total_rows": total_rows,
            "page_count": page_count,
            "show_from": show_from,
            "show_to": show_to,
            "prev_page_url": _demos_url(q=q, outcome=outcome, page=prev_page, page_size=page_size),
            "next_page_url": _demos_url(q=q, outcome=outcome, page=next_page, page_size=page_size),
            "today": today_iso(),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "demos.html", context)


@router.get("/{demo_id}")
def demo_workspace(request: Request, demo_id: str):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Demo Workspace")

    demo = repo.get_demo_outcome_by_id(demo_id)
    if demo is None:
        add_flash(request, "Demo not found.", "error")
        return RedirectResponse(url="/demos", status_code=303)

    review_template_rows = _list_demo_note_records(
        repo,
        demo_id,
        note_types=DEMO_REVIEW_TEMPLATE_NOTE_TYPES,
        limit_per_type=20,
    )
    submission_rows = _list_demo_note_records(
        repo,
        demo_id,
        note_types=DEMO_REVIEW_SUBMISSION_NOTE_TYPES,
        limit_per_type=500,
    )
    stage_rows = repo.list_demo_notes_by_demo(
        demo_id,
        note_type=DEMO_STAGE_NOTE_TYPE,
        limit=200,
    ).to_dict("records")

    template = parse_template_note(review_template_rows)
    review_summary = build_review_summary(template=template, submission_rows=submission_rows)
    stage_state = build_stage_history(demo=demo, stage_rows=stage_rows)
    scoring_cards = build_scoring_cards(review_summary.get("submissions") or [])
    is_session_open = is_demo_session_open(demo=demo, stage_rows=stage_rows)
    is_closed = not is_session_open

    context = base_template_context(
        request=request,
        context=user,
        title=f"Demo Workspace - {demo_id}",
        active_nav="demos",
        extra={
            "demo": demo,
            "demo_id": demo_id,
            "review_template": template,
            "review_summary": review_summary,
            "scoring_cards": scoring_cards,
            "stage_labels": DEMO_STAGE_LABELS,
            "stage_order": DEMO_STAGE_ORDER,
            "stage_state": stage_state,
            "is_demo_closed": is_closed,
            "is_demo_session_open": is_session_open,
            "can_submit_review": (
                not user.config.locked_mode
                and str(user.user_principal or "").strip() not in {"", UNKNOWN_USER_PRINCIPAL}
                and is_session_open
            ),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "demo_detail.html", context)


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

    stage_rows = repo.list_demo_notes_by_demo(
        demo_id,
        note_type=DEMO_STAGE_NOTE_TYPE,
        limit=200,
    ).to_dict("records")
    template_rows = _list_demo_note_records(
        repo,
        demo_id,
        note_types=DEMO_REVIEW_TEMPLATE_NOTE_TYPES,
        limit_per_type=20,
    )
    submission_rows = _list_demo_note_records(
        repo,
        demo_id,
        note_types=DEMO_REVIEW_SUBMISSION_NOTE_TYPES,
        limit_per_type=500,
    )
    template = parse_template_note(template_rows)
    summary = build_review_summary(template=template, submission_rows=submission_rows)

    is_session_open = is_demo_session_open(demo=demo, stage_rows=stage_rows)
    is_closed = not is_session_open
    can_submit_review = (
        not user.config.locked_mode
        and str(user.user_principal or "").strip() not in {"", UNKNOWN_USER_PRINCIPAL}
        and is_session_open
    )
    library_rows = repo.list_app_notes_by_entity_and_type(
        entity_name=DEMO_REVIEW_TEMPLATE_LIBRARY_ENTITY,
        note_type=DEMO_REVIEW_TEMPLATE_LIBRARY_NOTE_TYPE,
        limit=200,
    ).to_dict("records")
    library_templates = parse_template_library_rows(library_rows)
    user_principal = str(user.user_principal or "").strip().lower()
    my_submission = None
    if user_principal:
        for submission in summary.get("submissions") or []:
            reviewer = str(submission.get("reviewer") or "").strip().lower()
            if reviewer == user_principal:
                my_submission = submission
                break

    context = base_template_context(
        request=request,
        context=user,
        title=f"Demo Review Form - {demo_id}",
        active_nav="demos",
        extra={
            "demo": demo,
            "demo_id": demo_id,
            "review_template": template,
            "library_templates": library_templates,
            "review_summary": summary,
            "is_demo_closed": is_closed,
            "is_demo_session_open": is_session_open,
            "can_submit_review": can_submit_review,
            "my_submission": my_submission,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "demo_review_form.html", context)


