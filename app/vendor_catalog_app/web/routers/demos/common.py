from __future__ import annotations

import json
import re
from datetime import date
from typing import Any


DEMO_REVIEW_TEMPLATE_NOTE_TYPE = "review_form_template_v1"
DEMO_REVIEW_TEMPLATE_V2_NOTE_TYPE = "review_form_template_v2"
DEMO_REVIEW_TEMPLATE_NOTE_TYPES = [
    DEMO_REVIEW_TEMPLATE_V2_NOTE_TYPE,
    DEMO_REVIEW_TEMPLATE_NOTE_TYPE,
]
DEMO_REVIEW_TEMPLATE_LIBRARY_ENTITY = "demo_review_template"
DEMO_REVIEW_TEMPLATE_LIBRARY_NOTE_TYPE = "review_form_template_v2"

DEMO_REVIEW_SUBMISSION_NOTE_TYPE = "review_form_submission_v1"
DEMO_REVIEW_SUBMISSION_V2_NOTE_TYPE = "review_form_submission_v2"
DEMO_REVIEW_SUBMISSION_NOTE_TYPES = [
    DEMO_REVIEW_SUBMISSION_V2_NOTE_TYPE,
    DEMO_REVIEW_SUBMISSION_NOTE_TYPE,
]

QUESTION_TYPE_SCALE = "scale"
QUESTION_TYPE_BOOLEAN = "boolean"
QUESTION_TYPE_MULTI = "multi_choice"
QUESTION_TYPE_STAR = "star_rating"
QUESTION_TYPE_LIKERT = "likert_scale"
QUESTION_TYPE_DROPDOWN = "dropdown_select"
QUESTION_TYPE_SHORT_TEXT = "short_text"
QUESTION_TYPE_LONG_TEXT = "long_text"
QUESTION_TYPE_SECTION = "section_header"
ALLOWED_QUESTION_TYPES = {
    QUESTION_TYPE_SCALE,
    QUESTION_TYPE_BOOLEAN,
    QUESTION_TYPE_MULTI,
    QUESTION_TYPE_STAR,
    QUESTION_TYPE_LIKERT,
    QUESTION_TYPE_DROPDOWN,
    QUESTION_TYPE_SHORT_TEXT,
    QUESTION_TYPE_LONG_TEXT,
    QUESTION_TYPE_SECTION,
}
SCORE_SCALE_QUESTION_TYPES = {QUESTION_TYPE_SCALE, QUESTION_TYPE_STAR}
SCORE_OPTION_QUESTION_TYPES = {
    QUESTION_TYPE_BOOLEAN,
    QUESTION_TYPE_MULTI,
    QUESTION_TYPE_LIKERT,
    QUESTION_TYPE_DROPDOWN,
}
TEXT_QUESTION_TYPES = {QUESTION_TYPE_SHORT_TEXT, QUESTION_TYPE_LONG_TEXT}
NON_SCORED_QUESTION_TYPES = TEXT_QUESTION_TYPES | {QUESTION_TYPE_SECTION}
QUESTION_LAYOUT_OPTIONS = {"vertical", "horizontal", "dropdown"}
VISIBILITY_OPERATORS = {
    "equals",
    "not_equals",
    "includes_any",
    "greater_or_equal",
    "less_or_equal",
    "answered",
    "not_answered",
}
VISIBILITY_LOGIC_OPTIONS = {"all", "any"}

SCORING_METHOD_WEIGHTED_AVERAGE = "weighted_average"
SCORING_METHOD_WEIGHTED_SUM = "weighted_sum"
ALLOWED_SCORING_METHODS = {
    SCORING_METHOD_WEIGHTED_AVERAGE,
    SCORING_METHOD_WEIGHTED_SUM,
}
ASSIGNMENT_MODE_ALL = "all"
ASSIGNMENT_MODE_ALLOWLIST = "allowlist"
ALLOWED_ASSIGNMENT_MODES = {
    ASSIGNMENT_MODE_ALL,
    ASSIGNMENT_MODE_ALLOWLIST,
}

DEMO_STAGE_NOTE_TYPE = "demo_stage_v1"
DEMO_CLOSED_OUTCOMES = {"selected", "not_selected"}
DEMO_SELECTION_OUTCOMES = ["selected", "not_selected", "deferred"]
DEMO_STAGE_ORDER = ["intake", "scheduled", "in_progress", "scoring", "decision", "closed"]
DEMO_STAGE_LABELS = {
    "intake": "Intake",
    "scheduled": "Scheduled",
    "in_progress": "In Progress",
    "scoring": "Scoring",
    "decision": "Decision",
    "closed": "Closed",
}
DEFAULT_ALLOWED_REVIEW_STAGES = ["scheduled", "in_progress", "scoring", "decision"]


def today_iso() -> str:
    return date.today().isoformat()


def normalize_selection_outcome(raw_value: str | None) -> str:
    value = str(raw_value or "").strip().lower()
    if value in set(DEMO_SELECTION_OUTCOMES):
        return value
    return "deferred"


def normalize_demo_stage(raw_value: str | None) -> str:
    value = str(raw_value or "").strip().lower()
    if value in set(DEMO_STAGE_ORDER):
        return value
    return "intake"


def _slugify_label(value: str) -> str:
    lowered = re.sub(r"\s+", "_", str(value or "").strip().lower())
    lowered = re.sub(r"[^a-z0-9_]+", "_", lowered)
    lowered = re.sub(r"_+", "_", lowered).strip("_")
    if lowered and lowered[0].isdigit():
        lowered = f"c_{lowered}"
    return lowered


def _split_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    for token in re.split(r"[,\n;|]+", str(value or "").strip()):
        clean = str(token or "").strip()
        if clean:
            tokens.append(clean)
    return tokens


def _safe_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    raw_text = str(value or "").strip()
    if not raw_text:
        return {}
    try:
        parsed = json.loads(raw_text)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _safe_float(raw_value: Any, *, default: float, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        value = float(str(raw_value).strip())
    except Exception:
        value = float(default)
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _safe_bool(raw_value: Any, *, default: bool = False) -> bool:
    text = str(raw_value or "").strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "y", "on"}


def _safe_int(raw_value: Any, *, default: int, minimum: int | None = None) -> int:
    try:
        value = int(str(raw_value).strip())
    except Exception:
        value = int(default)
    if minimum is not None:
        value = max(minimum, value)
    return value


def _default_options_for_question_type(question_type: str) -> list[dict[str, Any]]:
    if question_type == QUESTION_TYPE_BOOLEAN:
        return [
            {"value": "yes", "label": "Yes", "weight": 1.0},
            {"value": "no", "label": "No", "weight": 0.0},
        ]
    if question_type == QUESTION_TYPE_MULTI:
        return [
            {"value": "option_1", "label": "Option 1", "weight": 1.0},
            {"value": "option_2", "label": "Option 2", "weight": 0.5},
            {"value": "option_3", "label": "Option 3", "weight": 0.0},
        ]
    if question_type == QUESTION_TYPE_LIKERT:
        return [
            {"value": "strongly_disagree", "label": "Strongly Disagree", "weight": 1.0},
            {"value": "disagree", "label": "Disagree", "weight": 2.0},
            {"value": "neutral", "label": "Neutral", "weight": 3.0},
            {"value": "agree", "label": "Agree", "weight": 4.0},
            {"value": "strongly_agree", "label": "Strongly Agree", "weight": 5.0},
        ]
    if question_type == QUESTION_TYPE_DROPDOWN:
        return [
            {"value": "option_1", "label": "Option 1", "weight": 1.0},
            {"value": "option_2", "label": "Option 2", "weight": 0.0},
        ]
    return []


def _note_id_from_row(row: dict[str, Any]) -> str:
    return str(row.get("demo_note_id") or row.get("note_id") or "").strip()


def _criteria_alias_from_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aliases: list[dict[str, Any]] = []
    for question in questions:
        question_type = str(question.get("question_type") or QUESTION_TYPE_SCALE).strip().lower()
        if question_type in NON_SCORED_QUESTION_TYPES:
            continue
        aliases.append(
            {
                "code": question.get("code"),
                "label": question.get("label"),
                "weight": question.get("weight"),
                "max_score": 10.0,
            }
        )
    return aliases


def parse_criteria_csv(criteria_csv: str, *, max_score: float) -> list[dict[str, Any]]:
    values = _split_tokens(criteria_csv)
    if not values:
        raise ValueError("At least one criterion is required.")

    seen: set[str] = set()
    criteria: list[dict[str, Any]] = []
    for idx, label in enumerate(values, start=1):
        code = _slugify_label(label) or f"criterion_{idx}"
        if code in seen:
            code = f"{code}_{idx}"
        seen.add(code)
        criteria.append(
            {
                "code": code,
                "label": label[:80],
                "weight": 1.0,
                "max_score": float(max_score),
            }
        )
    return criteria[:25]


def _parse_template_v1(payload: dict[str, Any], row: dict[str, Any]) -> dict[str, Any] | None:
    criteria_raw = payload.get("criteria")
    if not isinstance(criteria_raw, list) or not criteria_raw:
        return None
    questions: list[dict[str, Any]] = []
    for idx, item in enumerate(criteria_raw, start=1):
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip().lower() or f"criterion_{idx}"
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        max_score = _safe_float(item.get("max_score"), default=10.0, minimum=1.0, maximum=100.0)
        questions.append(
            {
                "code": code,
                "label": label,
                "question_type": QUESTION_TYPE_SCALE,
                "weight": 1.0,
                "required": True,
                "help_text": "",
                "scale_min": 0.0,
                "scale_max": max_score,
                "scale_step": 0.1,
                "max_answer_weight": 1.0,
                "options": [],
            }
        )
    if not questions:
        return None
    return {
        "template_note_id": _note_id_from_row(row),
        "template_key": str(row.get("entity_id") or _note_id_from_row(row)),
        "template_version": 1,
        "template_status": "active",
        "title": str(payload.get("title") or "Demo Scorecard").strip() or "Demo Scorecard",
        "instructions": str(payload.get("instructions") or "").strip(),
        "version": "v1",
        "questions": questions,
        "criteria": _criteria_alias_from_questions(questions),
        "created_at": row.get("created_at"),
        "created_by": str(row.get("created_by") or "").strip(),
    }


def _parse_template_v2(payload: dict[str, Any], row: dict[str, Any]) -> dict[str, Any] | None:
    questions_raw = payload.get("questions")
    if not isinstance(questions_raw, list) or not questions_raw:
        return None
    questions: list[dict[str, Any]] = []
    used_codes: set[str] = set()
    for idx, item in enumerate(questions_raw, start=1):
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        code = str(item.get("code") or "").strip().lower() or _slugify_label(label) or f"question_{idx}"
        if code in used_codes:
            code = f"{code}_{idx}"
        used_codes.add(code)

        question_type = str(item.get("question_type") or item.get("type") or "").strip().lower()
        if question_type not in ALLOWED_QUESTION_TYPES:
            question_type = QUESTION_TYPE_SCALE
        weight = _safe_float(item.get("weight"), default=1.0, minimum=0.01, maximum=100.0)
        required = _safe_bool(item.get("required"), default=True)
        if question_type == QUESTION_TYPE_SECTION:
            required = False
        help_text = str(item.get("help_text") or "").strip()
        layout = str(item.get("layout") or item.get("display_layout") or "vertical").strip().lower()
        if layout not in QUESTION_LAYOUT_OPTIONS:
            layout = "vertical"
        if question_type in {QUESTION_TYPE_BOOLEAN, QUESTION_TYPE_LIKERT}:
            layout = "horizontal"
        if question_type == QUESTION_TYPE_DROPDOWN:
            layout = "dropdown"
        placeholder = str(item.get("placeholder") or "").strip()
        allow_multiple = _safe_bool(item.get("allow_multiple"), default=False)
        if question_type != QUESTION_TYPE_MULTI:
            allow_multiple = False

        scale_min = _safe_float(item.get("scale_min"), default=1.0, minimum=0.0, maximum=1000.0)
        scale_max = _safe_float(item.get("scale_max"), default=5.0, minimum=0.01, maximum=1000.0)
        if scale_max <= scale_min:
            scale_max = scale_min + 1.0
        scale_step = _safe_float(item.get("scale_step"), default=1.0, minimum=0.01, maximum=100.0)
        if question_type == QUESTION_TYPE_STAR:
            scale_min = 1.0
            scale_max = 5.0
            scale_step = 1.0

        options_raw = item.get("options") if isinstance(item.get("options"), list) else []
        options: list[dict[str, Any]] = []
        for option_idx, option_row in enumerate(options_raw, start=1):
            if not isinstance(option_row, dict):
                continue
            option_label = str(option_row.get("label") or "").strip()
            if not option_label:
                continue
            option_value = str(option_row.get("value") or "").strip().lower() or _slugify_label(option_label)
            if not option_value:
                option_value = f"opt_{option_idx}"
            option_weight = _safe_float(option_row.get("weight"), default=0.0, minimum=0.0, maximum=100.0)
            options.append(
                {
                    "value": option_value,
                    "label": option_label,
                    "weight": option_weight,
                }
            )

        if question_type in SCORE_OPTION_QUESTION_TYPES and not options:
            options = _default_options_for_question_type(question_type)
        if question_type in {QUESTION_TYPE_MULTI, QUESTION_TYPE_DROPDOWN, QUESTION_TYPE_LIKERT} and len(options) < 2:
            continue
        max_answer_weight = 1.0
        if question_type in SCORE_OPTION_QUESTION_TYPES and options:
            max_answer_weight = max(float(option.get("weight") or 0.0) for option in options)
            max_answer_weight = max(max_answer_weight, 0.01)
        elif question_type in NON_SCORED_QUESTION_TYPES:
            max_answer_weight = 0.0

        questions.append(
            {
                "code": code,
                "label": label,
                "question_type": question_type,
                "weight": weight,
                "required": required,
                "help_text": help_text,
                "layout": layout,
                "placeholder": placeholder,
                "allow_multiple": allow_multiple,
                "scale_min": scale_min,
                "scale_max": scale_max,
                "scale_step": scale_step,
                "max_answer_weight": max_answer_weight,
                "options": options,
            }
        )
    if not questions:
        return None
    template_key = str(
        payload.get("template_key")
        or payload.get("source_template_key")
        or row.get("entity_id")
        or ""
    ).strip() or _note_id_from_row(row)
    template_version = _safe_int(payload.get("template_version") or payload.get("source_template_version"), default=1, minimum=1)
    template_status = str(payload.get("template_status") or "active").strip().lower() or "active"
    return {
        "template_note_id": _note_id_from_row(row),
        "template_key": template_key,
        "template_version": template_version,
        "template_status": template_status,
        "title": str(payload.get("title") or "Demo Review Form").strip() or "Demo Review Form",
        "instructions": str(payload.get("instructions") or "").strip(),
        "version": "v2",
        "questions": questions,
        "criteria": _criteria_alias_from_questions(questions),
        "created_at": row.get("created_at"),
        "created_by": str(row.get("created_by") or "").strip(),
    }


def parse_template_note(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    sorted_rows = sorted(rows, key=lambda row: str(row.get("created_at") or ""), reverse=True)
    for row in sorted_rows:
        payload = _safe_json(row.get("note_text"))
        version = str(payload.get("version") or "").strip().lower()
        if version == "v2":
            parsed = _parse_template_v2(payload, row)
            if parsed:
                return parsed
            continue
        parsed = _parse_template_v1(payload, row)
        if parsed:
            return parsed
    return None


def parse_template_library_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry["latest_template"] for entry in build_template_library_index(rows)]


def build_template_library_index(rows: list[dict[str, Any]], *, include_inactive: bool = False) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        parsed = parse_template_note([row])
        if not parsed:
            continue
        template_key = str(parsed.get("template_key") or "").strip()
        note_id = str(parsed.get("template_note_id") or "").strip()
        if not template_key or not note_id:
            continue
        parsed["library_note_id"] = note_id
        grouped.setdefault(template_key, []).append(parsed)

    catalog: list[dict[str, Any]] = []
    for template_key, versions in grouped.items():
        sorted_versions = sorted(
            versions,
            key=lambda item: (
                _safe_int(item.get("template_version"), default=1, minimum=1),
                str(item.get("created_at") or ""),
            ),
            reverse=True,
        )
        latest_template = sorted_versions[0]
        status = str(latest_template.get("template_status") or "active").strip().lower() or "active"
        is_active = status == "active"
        if not include_inactive and not is_active:
            continue
        catalog.append(
            {
                "template_key": template_key,
                "title": str(latest_template.get("title") or "").strip() or "Untitled Form",
                "current_version": _safe_int(latest_template.get("template_version"), default=1, minimum=1),
                "status": status,
                "is_active": is_active,
                "question_count": len(latest_template.get("questions") or []),
                "created_at": latest_template.get("created_at"),
                "created_by": str(latest_template.get("created_by") or "").strip(),
                "latest_note_id": str(latest_template.get("library_note_id") or "").strip(),
                "latest_template": latest_template,
                "versions": sorted_versions,
            }
        )

    catalog.sort(
        key=lambda item: (
            str(item.get("title") or "").lower(),
            str(item.get("template_key") or ""),
        )
    )
    return catalog


def parse_submission_note(row: dict[str, Any]) -> dict[str, Any] | None:
    payload = _safe_json(row.get("note_text"))
    version = str(payload.get("version") or "").strip().lower()

    if version == "v2":
        answers_raw = payload.get("answers")
        if not isinstance(answers_raw, list) or not answers_raw:
            return None
        answers: list[dict[str, Any]] = []
        for item in answers_raw:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").strip().lower()
            label = str(item.get("label") or "").strip()
            if not code or not label:
                continue
            weighted_score = _safe_float(item.get("weighted_score"), default=0.0, minimum=0.0)
            weighted_max = _safe_float(item.get("weighted_max"), default=0.0, minimum=0.0)
            if weighted_max <= 0:
                score_10 = None
            else:
                score_10 = round((weighted_score / weighted_max) * 10.0, 2)
            answers.append(
                {
                    "code": code,
                    "label": label,
                    "question_type": str(item.get("question_type") or "").strip().lower(),
                    "response_value": item.get("response_value"),
                    "response_label": str(item.get("response_label") or "").strip(),
                    "question_weight": _safe_float(item.get("question_weight"), default=1.0, minimum=0.0),
                    "answer_weight": _safe_float(item.get("answer_weight"), default=0.0, minimum=0.0),
                    "weighted_score": round(weighted_score, 4),
                    "weighted_max": round(weighted_max, 4),
                    "score_10": score_10,
                }
            )
        if not answers:
            return None
        weighted_total = _safe_float(payload.get("weighted_score_total"), default=0.0, minimum=0.0)
        weighted_max_total = _safe_float(payload.get("weighted_max_total"), default=0.0, minimum=0.0)
        overall_score = _safe_float(payload.get("overall_score"), default=0.0, minimum=0.0, maximum=10.0)
        return {
            "review_note_id": _note_id_from_row(row),
            "reviewer": str(row.get("created_by") or "").strip(),
            "submitted_at": row.get("created_at"),
            "overall_score": round(overall_score, 2),
            "comment": str(payload.get("comment") or "").strip(),
            "answers": answers,
            "scores": answers,
            "weighted_score_total": round(weighted_total, 4),
            "weighted_max_total": round(weighted_max_total, 4),
            "template_note_id": str(payload.get("template_note_id") or "").strip(),
            "template_title": str(payload.get("template_title") or "").strip(),
            "version": "v2",
        }

    scores_raw = payload.get("scores")
    if not isinstance(scores_raw, list) or not scores_raw:
        return None
    answers: list[dict[str, Any]] = []
    for item in scores_raw:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip().lower()
        label = str(item.get("label") or "").strip()
        if not code or not label:
            continue
        score_value = _safe_float(item.get("score"), default=0.0, minimum=0.0)
        max_score = _safe_float(item.get("max_score"), default=10.0, minimum=0.01)
        score_10 = round((score_value / max_score) * 10.0, 2) if max_score > 0 else 0.0
        answers.append(
            {
                "code": code,
                "label": label,
                "question_type": QUESTION_TYPE_SCALE,
                "response_value": score_value,
                "response_label": f"{score_value:g}",
                "question_weight": 1.0,
                "answer_weight": round(score_value / max_score, 4) if max_score > 0 else 0.0,
                "weighted_score": score_value,
                "weighted_max": max_score,
                "score_10": score_10,
            }
        )
    if not answers:
        return None
    overall = _safe_float(payload.get("overall_score"), default=0.0, minimum=0.0, maximum=10.0)
    weighted_total = sum(float(answer.get("weighted_score") or 0.0) for answer in answers)
    weighted_max_total = sum(float(answer.get("weighted_max") or 0.0) for answer in answers)
    return {
        "review_note_id": _note_id_from_row(row),
        "reviewer": str(row.get("created_by") or "").strip(),
        "submitted_at": row.get("created_at"),
        "overall_score": round(overall, 2),
        "comment": str(payload.get("comment") or "").strip(),
        "answers": answers,
        "scores": answers,
        "weighted_score_total": round(weighted_total, 4),
        "weighted_max_total": round(weighted_max_total, 4),
        "template_note_id": str(payload.get("template_note_id") or "").strip(),
        "template_title": str(payload.get("template_title") or "").strip(),
        "version": "v1",
    }


def parse_demo_stage_note(row: dict[str, Any]) -> dict[str, Any] | None:
    payload = _safe_json(row.get("note_text"))
    if str(payload.get("version") or "") != "v1":
        return None
    stage = normalize_demo_stage(payload.get("stage"))
    return {
        "stage": stage,
        "stage_label": DEMO_STAGE_LABELS.get(stage, stage.title()),
        "notes": str(payload.get("notes") or "").strip(),
        "changed_at": row.get("created_at"),
        "changed_by": str(row.get("created_by") or "").strip(),
        "note_id": _note_id_from_row(row),
    }


def build_review_summary(
    *,
    template: dict[str, Any] | None,
    submission_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    latest_by_reviewer: dict[str, dict[str, Any]] = {}
    parsed_submissions: list[dict[str, Any]] = []
    sorted_rows = sorted(submission_rows, key=lambda row: str(row.get("created_at") or ""), reverse=True)
    for row in sorted_rows:
        parsed = parse_submission_note(row)
        if not parsed:
            continue
        reviewer = str(parsed.get("reviewer") or "").strip().lower()
        if not reviewer or reviewer in latest_by_reviewer:
            continue
        latest_by_reviewer[reviewer] = parsed
        parsed_submissions.append(parsed)

    questions = list((template or {}).get("questions") or [])
    criterion_stats: list[dict[str, Any]] = []
    for question in questions:
        question_type = str(question.get("question_type") or QUESTION_TYPE_SCALE).strip().lower()
        if question_type in NON_SCORED_QUESTION_TYPES:
            continue
        code = str(question.get("code") or "").strip().lower()
        values: list[float] = []
        for submission in parsed_submissions:
            for answer_row in submission.get("answers") or []:
                if str(answer_row.get("code") or "").strip().lower() != code:
                    continue
                raw_score = answer_row.get("score_10")
                if raw_score is None:
                    continue
                values.append(_safe_float(raw_score, default=0.0, minimum=0.0, maximum=10.0))
        if not values:
            criterion_stats.append(
                {
                    "code": code,
                    "label": str(question.get("label") or code),
                    "avg_score": None,
                    "response_count": 0,
                }
            )
            continue
        avg_score = round(sum(values) / len(values), 2)
        criterion_stats.append(
            {
                "code": code,
                "label": str(question.get("label") or code),
                "avg_score": avg_score,
                "response_count": len(values),
            }
        )

    overall_values: list[float] = []
    for submission in parsed_submissions:
        overall_values.append(_safe_float(submission.get("overall_score"), default=0.0, minimum=0.0, maximum=10.0))
    overall_avg = round(sum(overall_values) / len(overall_values), 2) if overall_values else None

    return {
        "submission_count": len(parsed_submissions),
        "overall_avg": overall_avg,
        "criterion_stats": criterion_stats,
        "submissions": parsed_submissions,
    }


def build_stage_history(*, demo: dict[str, Any], stage_rows: list[dict[str, Any]]) -> dict[str, Any]:
    parsed_rows: list[dict[str, Any]] = []
    for row in stage_rows:
        parsed = parse_demo_stage_note(row)
        if parsed:
            parsed_rows.append(parsed)

    parsed_rows = sorted(
        parsed_rows,
        key=lambda row: str(row.get("changed_at") or ""),
        reverse=True,
    )

    outcome = normalize_selection_outcome(demo.get("selection_outcome"))
    if outcome in DEMO_CLOSED_OUTCOMES:
        current_stage = "closed"
    elif parsed_rows:
        current_stage = normalize_demo_stage(parsed_rows[0].get("stage"))
    else:
        current_stage = "scheduled"

    current_index = DEMO_STAGE_ORDER.index(current_stage)
    stage_steps: list[dict[str, Any]] = []
    for idx, code in enumerate(DEMO_STAGE_ORDER):
        state = "upcoming"
        if idx < current_index:
            state = "completed"
        elif idx == current_index:
            state = "current"
        stage_steps.append(
            {
                "code": code,
                "label": DEMO_STAGE_LABELS.get(code, code.title()),
                "state": state,
            }
        )

    return {
        "current_stage": current_stage,
        "current_stage_label": DEMO_STAGE_LABELS.get(current_stage, current_stage.title()),
        "steps": stage_steps,
        "history_rows": parsed_rows,
    }


def is_demo_session_open(*, demo: dict[str, Any], stage_rows: list[dict[str, Any]]) -> bool:
    outcome = normalize_selection_outcome(demo.get("selection_outcome"))
    if outcome in DEMO_CLOSED_OUTCOMES:
        return False
    stage_state = build_stage_history(demo=demo, stage_rows=stage_rows)
    return str(stage_state.get("current_stage") or "").strip().lower() != "closed"


def build_scoring_cards(submissions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for row in submissions:
        answer_rows = row.get("answers") or row.get("scores") or []
        weighted_total = 0.0
        weighted_max_total = 0.0
        for answer_row in answer_rows:
            weighted_total += _safe_float(answer_row.get("weighted_score"), default=0.0, minimum=0.0)
            weighted_max_total += _safe_float(answer_row.get("weighted_max"), default=0.0, minimum=0.0)
        normalized_score = 0.0
        if weighted_max_total > 0:
            normalized_score = round((weighted_total / weighted_max_total) * 10.0, 2)
        cards.append(
            {
                "review_note_id": row.get("review_note_id"),
                "reviewer": row.get("reviewer"),
                "submitted_at": row.get("submitted_at"),
                "overall_score": row.get("overall_score"),
                "comment": row.get("comment"),
                "answers": answer_rows,
                "scores": answer_rows,
                "total_earned": round(weighted_total, 2),
                "total_possible": round(weighted_max_total, 2),
                "normalized_score": normalized_score,
            }
        )
    return cards


def parse_template_questions_from_form(form_data: Any) -> list[dict[str, Any]]:
    labels = [str(value or "").strip() for value in form_data.getlist("question_label[]")]
    types = [str(value or "").strip().lower() for value in form_data.getlist("question_type[]")]
    weights = [str(value or "").strip() for value in form_data.getlist("question_weight[]")]
    scale_mins = [str(value or "").strip() for value in form_data.getlist("scale_min[]")]
    scale_maxes = [str(value or "").strip() for value in form_data.getlist("scale_max[]")]
    scale_steps = [str(value or "").strip() for value in form_data.getlist("scale_step[]")]
    option_labels_rows = [str(value or "").strip() for value in form_data.getlist("option_labels[]")]
    option_weights_rows = [str(value or "").strip() for value in form_data.getlist("option_weights[]")]
    help_text_rows = [str(value or "").strip() for value in form_data.getlist("question_help_text[]")]
    required_rows = [str(value or "").strip().lower() for value in form_data.getlist("question_required[]")]
    layout_rows = [str(value or "").strip().lower() for value in form_data.getlist("question_layout[]")]
    placeholder_rows = [str(value or "").strip() for value in form_data.getlist("question_placeholder[]")]
    allow_multiple_rows = [str(value or "").strip().lower() for value in form_data.getlist("allow_multiple[]")]

    def _value(values: list[str], index: int, default: str = "") -> str:
        if index < len(values):
            return values[index]
        return default

    parsed_questions: list[dict[str, Any]] = []
    used_codes: set[str] = set()
    for idx, label in enumerate(labels):
        if not label:
            continue
        question_type = _value(types, idx, QUESTION_TYPE_SCALE)
        if question_type not in ALLOWED_QUESTION_TYPES:
            question_type = QUESTION_TYPE_SCALE

        question_weight = _safe_float(_value(weights, idx, "1"), default=1.0, minimum=0.01, maximum=100.0)
        help_text = _value(help_text_rows, idx, "")
        required = _safe_bool(_value(required_rows, idx, "true"), default=True)
        if question_type == QUESTION_TYPE_SECTION:
            required = False
        layout = _value(layout_rows, idx, "vertical")
        if layout not in QUESTION_LAYOUT_OPTIONS:
            layout = "vertical"
        if question_type in {QUESTION_TYPE_BOOLEAN, QUESTION_TYPE_LIKERT}:
            layout = "horizontal"
        if question_type == QUESTION_TYPE_DROPDOWN:
            layout = "dropdown"
        placeholder = _value(placeholder_rows, idx, "")
        allow_multiple = _safe_bool(_value(allow_multiple_rows, idx, "false"), default=False)
        if question_type != QUESTION_TYPE_MULTI:
            allow_multiple = False

        code = _slugify_label(label) or f"question_{idx + 1}"
        if code in used_codes:
            code = f"{code}_{idx + 1}"
        used_codes.add(code)

        scale_min = _safe_float(_value(scale_mins, idx, "1"), default=1.0, minimum=0.0, maximum=1000.0)
        scale_max = _safe_float(_value(scale_maxes, idx, "5"), default=5.0, minimum=0.01, maximum=1000.0)
        if scale_max <= scale_min and question_type in SCORE_SCALE_QUESTION_TYPES:
            raise ValueError(f"Scale max must be greater than min for '{label}'.")
        scale_step = _safe_float(_value(scale_steps, idx, "1"), default=1.0, minimum=0.01, maximum=100.0)
        if question_type == QUESTION_TYPE_STAR:
            scale_min = 1.0
            scale_max = 5.0
            scale_step = 1.0

        options: list[dict[str, Any]] = []
        max_answer_weight = 1.0
        if question_type in SCORE_OPTION_QUESTION_TYPES:
            option_labels = _split_tokens(_value(option_labels_rows, idx, ""))
            option_weights = _split_tokens(_value(option_weights_rows, idx, ""))

            if not option_labels:
                defaults = _default_options_for_question_type(question_type)
                option_labels = [str(row.get("label") or "") for row in defaults]
                option_weights = [str(row.get("weight") or "0") for row in defaults]
            if question_type in {QUESTION_TYPE_MULTI, QUESTION_TYPE_DROPDOWN, QUESTION_TYPE_LIKERT} and len(option_labels) < 2:
                raise ValueError(f"Provide at least two options for '{label}'.")

            if option_weights and len(option_weights) != len(option_labels):
                raise ValueError(f"Option weights must match option count for '{label}'.")
            if not option_weights:
                option_weights = ["1" for _ in option_labels]
                if question_type == QUESTION_TYPE_BOOLEAN and len(option_weights) >= 2:
                    option_weights[1] = "0"

            used_values: set[str] = set()
            for option_idx, option_label in enumerate(option_labels, start=1):
                value = _slugify_label(option_label) or f"option_{option_idx}"
                if value in used_values:
                    value = f"{value}_{option_idx}"
                used_values.add(value)
                weight = _safe_float(option_weights[option_idx - 1], default=0.0, minimum=0.0, maximum=100.0)
                options.append({"value": value, "label": option_label, "weight": weight})

            max_answer_weight = max(float(option.get("weight") or 0.0) for option in options)
            max_answer_weight = max(max_answer_weight, 0.01)
        elif question_type in NON_SCORED_QUESTION_TYPES:
            max_answer_weight = 0.0

        parsed_questions.append(
            {
                "code": code,
                "label": label[:160],
                "question_type": question_type,
                "weight": question_weight,
                "required": required,
                "help_text": help_text[:240],
                "layout": layout,
                "placeholder": placeholder[:120],
                "allow_multiple": allow_multiple,
                "scale_min": scale_min,
                "scale_max": scale_max,
                "scale_step": scale_step,
                "max_answer_weight": max_answer_weight,
                "options": options,
            }
        )

    if not parsed_questions:
        raise ValueError("At least one question is required.")
    return parsed_questions


def build_submission_from_form(*, template: dict[str, Any], form_data: Any) -> dict[str, Any]:
    answers: list[dict[str, Any]] = []
    weighted_score_total = 0.0
    weighted_max_total = 0.0
    for question in template.get("questions") or []:
        code = str(question.get("code") or "").strip().lower()
        label = str(question.get("label") or code)
        question_type = str(question.get("question_type") or QUESTION_TYPE_SCALE).strip().lower()
        question_weight = _safe_float(question.get("weight"), default=1.0, minimum=0.01, maximum=100.0)
        if question_type in NON_SCORED_QUESTION_TYPES:
            question_weight = _safe_float(question.get("weight"), default=1.0, minimum=0.0, maximum=100.0)
        is_required = _safe_bool(question.get("required"), default=True)
        if question_type == QUESTION_TYPE_SECTION:
            is_required = False
        answer_key = f"answer_{code}"
        raw_values = [str(value or "").strip() for value in form_data.getlist(answer_key)]
        raw_values = [value for value in raw_values if value]
        raw_value = raw_values[0] if raw_values else str(form_data.get(answer_key, "")).strip()
        if raw_value and not raw_values:
            raw_values = [raw_value]

        if question_type == QUESTION_TYPE_SECTION:
            continue
        if not raw_values and is_required:
            raise ValueError(f"Answer is required for '{label}'.")
        if not raw_values and not is_required:
            continue

        answer_weight = 0.0
        response_value: Any = raw_value
        response_label = raw_value
        weighted_max = 0.0

        if question_type in SCORE_SCALE_QUESTION_TYPES:
            scale_min = _safe_float(question.get("scale_min"), default=1.0, minimum=0.0)
            scale_max = _safe_float(question.get("scale_max"), default=5.0, minimum=0.01)
            scale_step = _safe_float(question.get("scale_step"), default=1.0, minimum=0.01)
            if question_type == QUESTION_TYPE_STAR:
                scale_min = 1.0
                scale_max = 5.0
                scale_step = 1.0
            if scale_max <= scale_min:
                scale_max = scale_min + 1.0
            try:
                numeric = float(raw_values[0])
            except Exception as exc:
                raise ValueError(f"Answer for '{label}' must be numeric.") from exc
            if scale_step > 0:
                numeric = round(round((numeric - scale_min) / scale_step) * scale_step + scale_min, 6)
            if numeric < scale_min or numeric > scale_max:
                raise ValueError(f"Answer for '{label}' must be between {scale_min:g} and {scale_max:g}.")
            normalized = (numeric - scale_min) / (scale_max - scale_min)
            answer_weight = max(0.0, min(1.0, normalized))
            response_value = numeric
            response_label = f"{numeric:g}"
            weighted_max = question_weight * 1.0
        elif question_type in SCORE_OPTION_QUESTION_TYPES:
            options = [option for option in question.get("options") or [] if isinstance(option, dict)]
            if not options:
                raise ValueError(f"Question '{label}' is missing options.")
            allow_multiple = _safe_bool(question.get("allow_multiple"), default=False)
            selected_values = raw_values if (allow_multiple and question_type == QUESTION_TYPE_MULTI) else raw_values[:1]
            matched_options: list[dict[str, Any]] = []
            for selected_value in selected_values:
                selected_option = None
                for option in options:
                    if str(option.get("value") or "").strip().lower() == selected_value.lower():
                        selected_option = option
                        break
                if selected_option is None:
                    raise ValueError(f"Invalid answer for '{label}'.")
                matched_options.append(selected_option)

            if not matched_options:
                raise ValueError(f"Answer is required for '{label}'.")
            weights = [
                _safe_float(option.get("weight"), default=0.0, minimum=0.0, maximum=100.0)
                for option in matched_options
            ]
            answer_weight = sum(weights) / len(weights)
            if len(matched_options) == 1:
                response_value = str(matched_options[0].get("value") or "").strip()
                response_label = str(matched_options[0].get("label") or response_value).strip()
            else:
                response_value = [str(option.get("value") or "").strip() for option in matched_options]
                response_label = ", ".join(str(option.get("label") or "").strip() for option in matched_options)
            max_answer_weight = _safe_float(question.get("max_answer_weight"), default=1.0, minimum=0.01)
            weighted_max = question_weight * max_answer_weight
        else:
            text_value = raw_values[0]
            response_value = text_value
            response_label = text_value
            answer_weight = 0.0
            weighted_max = 0.0

        weighted_score = question_weight * answer_weight
        score_10 = round((weighted_score / weighted_max) * 10.0, 2) if weighted_max > 0 else None
        weighted_score_total += weighted_score
        weighted_max_total += weighted_max
        answers.append(
            {
                "code": code,
                "label": label,
                "question_type": question_type,
                "question_weight": question_weight,
                "response_value": response_value,
                "response_label": response_label,
                "answer_weight": round(answer_weight, 4),
                "weighted_score": round(weighted_score, 4),
                "weighted_max": round(weighted_max, 4),
                "score_10": score_10,
            }
        )

    overall_score = 0.0
    if weighted_max_total > 0:
        overall_score = round((weighted_score_total / weighted_max_total) * 10.0, 2)

    return {
        "answers": answers,
        "overall_score": overall_score,
        "weighted_score_total": round(weighted_score_total, 4),
        "weighted_max_total": round(weighted_max_total, 4),
    }
