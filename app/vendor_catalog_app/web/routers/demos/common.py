from __future__ import annotations

import json
import re
from datetime import date
from typing import Any


DEMO_REVIEW_TEMPLATE_NOTE_TYPE = "review_form_template_v1"
DEMO_REVIEW_SUBMISSION_NOTE_TYPE = "review_form_submission_v1"
DEMO_CLOSED_OUTCOMES = {"selected", "not_selected"}
DEMO_SELECTION_OUTCOMES = ["selected", "not_selected", "deferred"]


def today_iso() -> str:
    return date.today().isoformat()


def normalize_selection_outcome(raw_value: str | None) -> str:
    value = str(raw_value or "").strip().lower()
    if value in set(DEMO_SELECTION_OUTCOMES):
        return value
    return "deferred"


def _slugify_label(value: str) -> str:
    lowered = re.sub(r"\s+", "_", str(value or "").strip().lower())
    lowered = re.sub(r"[^a-z0-9_]+", "_", lowered)
    lowered = re.sub(r"_+", "_", lowered).strip("_")
    if lowered and lowered[0].isdigit():
        lowered = f"c_{lowered}"
    return lowered


def parse_criteria_csv(criteria_csv: str, *, max_score: float) -> list[dict[str, Any]]:
    values: list[str] = []
    for token in re.split(r"[,\n;]+", str(criteria_csv or "").strip()):
        label = str(token or "").strip()
        if label:
            values.append(label)
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


def parse_template_note(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        payload = _safe_json(row.get("note_text"))
        criteria_raw = payload.get("criteria")
        if not isinstance(criteria_raw, list) or not criteria_raw:
            continue
        criteria: list[dict[str, Any]] = []
        for item in criteria_raw:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").strip().lower()
            label = str(item.get("label") or "").strip()
            if not code or not label:
                continue
            try:
                max_score = float(item.get("max_score") or 10.0)
            except Exception:
                max_score = 10.0
            criteria.append(
                {
                    "code": code,
                    "label": label,
                    "weight": 1.0,
                    "max_score": max(1.0, min(max_score, 100.0)),
                }
            )
        if not criteria:
            continue
        return {
            "template_note_id": str(row.get("demo_note_id") or ""),
            "title": str(payload.get("title") or "Demo Scorecard").strip() or "Demo Scorecard",
            "instructions": str(payload.get("instructions") or "").strip(),
            "criteria": criteria,
            "created_at": row.get("created_at"),
            "created_by": str(row.get("created_by") or "").strip(),
        }
    return None


def parse_submission_note(row: dict[str, Any]) -> dict[str, Any] | None:
    payload = _safe_json(row.get("note_text"))
    if str(payload.get("version") or "") != "v1":
        return None
    scores_raw = payload.get("scores")
    if not isinstance(scores_raw, list) or not scores_raw:
        return None
    scores: list[dict[str, Any]] = []
    for item in scores_raw:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip().lower()
        label = str(item.get("label") or "").strip()
        if not code or not label:
            continue
        try:
            score_value = float(item.get("score"))
            max_score = float(item.get("max_score") or 10.0)
        except Exception:
            continue
        scores.append(
            {
                "code": code,
                "label": label,
                "score": score_value,
                "max_score": max(1.0, max_score),
            }
        )
    if not scores:
        return None
    try:
        overall = float(payload.get("overall_score"))
    except Exception:
        overall = 0.0
    return {
        "review_note_id": str(row.get("demo_note_id") or ""),
        "reviewer": str(row.get("created_by") or "").strip(),
        "submitted_at": row.get("created_at"),
        "overall_score": overall,
        "comment": str(payload.get("comment") or "").strip(),
        "scores": scores,
    }


def build_review_summary(
    *,
    template: dict[str, Any] | None,
    submission_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    latest_by_reviewer: dict[str, dict[str, Any]] = {}
    parsed_submissions: list[dict[str, Any]] = []
    for row in submission_rows:
        parsed = parse_submission_note(row)
        if not parsed:
            continue
        reviewer = str(parsed.get("reviewer") or "").strip().lower()
        if not reviewer:
            continue
        if reviewer in latest_by_reviewer:
            continue
        latest_by_reviewer[reviewer] = parsed
        parsed_submissions.append(parsed)

    criteria = list((template or {}).get("criteria") or [])
    criterion_stats: list[dict[str, Any]] = []
    for criterion in criteria:
        code = str(criterion.get("code") or "").strip().lower()
        values: list[float] = []
        for submission in parsed_submissions:
            for score_row in submission.get("scores") or []:
                if str(score_row.get("code") or "").strip().lower() != code:
                    continue
                try:
                    values.append(float(score_row.get("score") or 0.0))
                except Exception:
                    continue
        if not values:
            criterion_stats.append(
                {
                    "code": code,
                    "label": str(criterion.get("label") or code),
                    "avg_score": None,
                    "response_count": 0,
                }
            )
            continue
        avg_score = round(sum(values) / len(values), 2)
        criterion_stats.append(
            {
                "code": code,
                "label": str(criterion.get("label") or code),
                "avg_score": avg_score,
                "response_count": len(values),
            }
        )

    overall_values: list[float] = []
    for submission in parsed_submissions:
        try:
            overall_values.append(float(submission.get("overall_score") or 0.0))
        except Exception:
            continue
    overall_avg = round(sum(overall_values) / len(overall_values), 2) if overall_values else None

    return {
        "submission_count": len(parsed_submissions),
        "overall_avg": overall_avg,
        "criterion_stats": criterion_stats,
        "submissions": parsed_submissions,
    }

