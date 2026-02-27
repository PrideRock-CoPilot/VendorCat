from __future__ import annotations

import csv
import io
import json
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, Literal, cast

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.core.responses import api_error, api_json, parse_json_body
from apps.core.services.permission_registry import authorize_mutation
from apps.core.services.policy_engine import PolicyEngine
from apps.identity.services import build_policy_snapshot, sync_user_directory
from apps.reports.constants import REPORT_OUTPUT_FORMATS, REPORT_RUN_STATUSES
from apps.reports.contracts import ReportEmailRequest, ReportRunRequest
from apps.reports.models import ReportEmailRequestRecord, ReportRun


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _parse_warnings(raw: str) -> tuple[str, ...]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return ()
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return ()


def _serialize_report_run(record: ReportRun) -> dict[str, Any]:
    warnings = _parse_warnings(record.warnings_json)
    download_url = record.file_path or None
    if record.status == "completed" and record.report_format == "csv" and not download_url:
        download_url = f"/api/v1/reports/runs/{record.report_run_id}/download"

    return {
        "run_id": record.report_run_id,
        "status": record.status,
        "row_count": int(record.row_count),
        "download_url": download_url,
        "warnings": list(warnings),
        "report_code": record.report_code,
        "output_format": record.report_format,
        "requested_by": record.triggered_by,
        "created_at": _iso(record.created_at),
        "updated_at": _iso(record.updated_at),
    }


def _parse_email_list(raw_value: Any) -> tuple[str, ...]:
    if isinstance(raw_value, str):
        return tuple(part.strip() for part in raw_value.split(",") if part.strip())
    if isinstance(raw_value, list):
        return tuple(str(item).strip() for item in raw_value if str(item).strip())
    if isinstance(raw_value, tuple):
        return tuple(str(item).strip() for item in raw_value if str(item).strip())
    return ()


def _permission_denied(request: HttpRequest, permission: str) -> JsonResponse:
    return api_error(
        request,
        code="forbidden",
        message=f"Missing permission: {permission}",
        status=403,
    )


def _require_permission(request: HttpRequest, permission: str) -> tuple[bool, JsonResponse | None]:
    identity = sync_user_directory_context(request)
    snapshot = build_policy_snapshot(identity)
    decision = PolicyEngine.decide(snapshot, permission)
    if not decision.allowed:
        return False, _permission_denied(request, permission)
    return True, None


def sync_user_directory_context(request: HttpRequest):
    from apps.core.contracts.identity import resolve_identity_context

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    return identity


def _normalize_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in REPORT_RUN_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(REPORT_RUN_STATUSES)}")
    return normalized


@require_http_methods(["GET"])
def index(request: HttpRequest) -> HttpResponse:
    identity = sync_user_directory_context(request)
    snapshot = build_policy_snapshot(identity)
    can_read_reports = PolicyEngine.decide(snapshot, "report.read").allowed
    can_run_report = PolicyEngine.decide(snapshot, "report.run").allowed

    runs = ReportRun.objects.all().order_by("-created_at")[:50] if can_read_reports else ReportRun.objects.none()  # type: ignore[attr-defined]
    return render(
        request,
        "reports/index.html",
        {
            "page_title": "Reports",
            "section_name": "Reports",
            "items": [_serialize_report_run(run) for run in runs],
            "can_read_reports": can_read_reports,
            "can_run_report": can_run_report,
        },
    )


@require_http_methods(["GET"])
def report_runs_partial(request: HttpRequest) -> HttpResponse:
    runs = ReportRun.objects.all().order_by("-created_at")[:50]  # type: ignore[attr-defined]
    return render(
        request,
        "reports/_runs_table.html",
        {
            "items": [_serialize_report_run(run) for run in runs],
        },
    )


@require_http_methods(["GET"])
def report_detail_page(request: HttpRequest, run_id: str) -> HttpResponse:
    identity = sync_user_directory_context(request)
    snapshot = build_policy_snapshot(identity)
    can_read_reports = PolicyEngine.decide(snapshot, "report.read").allowed

    record = get_object_or_404(ReportRun, report_run_id=run_id)
    return render(
        request,
        "reports/detail.html",
        {
            "page_title": "Report Run",
            "item": _serialize_report_run(record) if can_read_reports else None,
            "can_read_reports": can_read_reports,
        },
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def report_runs_collection_endpoint(request: HttpRequest) -> JsonResponse:
    identity = sync_user_directory_context(request)
    snapshot = build_policy_snapshot(identity)

    if request.method == "GET":
        read_decision = PolicyEngine.decide(snapshot, "report.read")
        if not read_decision.allowed:
            return _permission_denied(request, "report.read")

        items = [
            _serialize_report_run(record)
            for record in ReportRun.objects.all().order_by("-created_at")  # type: ignore[attr-defined]
        ]
        return api_json({"items": items})

    decision = authorize_mutation(snapshot, "POST", "/api/v1/reports/runs")
    if not decision.allowed:
        return _permission_denied(request, "report.run")

    try:
        body = parse_json_body(request)
    except ValueError as exc:
        return api_error(request, code="invalid_request", message=str(exc), status=400)

    output_format = str(body.get("output_format", "preview")).strip().lower() or "preview"
    requested_by = str(body.get("requested_by", identity.user_principal)).strip() or identity.user_principal
    filters_raw = body.get("filters", {})
    if not isinstance(filters_raw, dict):
        return api_error(request, code="invalid_request", message="filters must be an object", status=400)
    if output_format not in REPORT_OUTPUT_FORMATS:
        return api_error(
            request,
            code="invalid_request",
            message=f"output_format must be one of: {', '.join(REPORT_OUTPUT_FORMATS)}",
            status=400,
        )

    request_dto = ReportRunRequest(
        report_code=str(body.get("report_code", "")).strip(),
        filters={str(k): v for k, v in filters_raw.items()},
        output_format=cast(Literal["preview", "csv"], output_format),
        requested_by=requested_by,
    )

    try:
        request_dto.validate()
    except ValueError as exc:
        return api_error(request, code="invalid_request", message=str(exc), status=400)

    run_id = str(uuid.uuid4())
    status = _normalize_status(str(body.get("status", "completed" if output_format == "preview" else "queued")))
    warnings = body.get("warnings", [])
    warning_values = [str(item) for item in warnings] if isinstance(warnings, list) else []

    record = ReportRun.objects.create(  # type: ignore[attr-defined]
        report_run_id=run_id,
        report_code=request_dto.report_code,
        report_type=request_dto.report_code,
        report_name=str(body.get("report_name", request_dto.report_code or "Report Run")),
        report_format=request_dto.output_format,
        status=status,
        triggered_by=request_dto.requested_by,
        scheduled_time=timezone.now(),
        filters_json=json.dumps(request_dto.filters, sort_keys=True),
        warnings_json=json.dumps(warning_values),
        file_path=f"/api/v1/reports/runs/{run_id}/download" if output_format == "csv" else "",
    )

    return api_json(_serialize_report_run(record), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def report_run_detail_endpoint(request: HttpRequest, report_run_id: str) -> JsonResponse:
    identity = sync_user_directory_context(request)
    snapshot = build_policy_snapshot(identity)

    try:
        record = ReportRun.objects.get(report_run_id=report_run_id)  # type: ignore[attr-defined]
    except ReportRun.DoesNotExist:  # type: ignore[attr-defined]
        return api_error(request, code="not_found", message=f"report run {report_run_id} not found", status=404)

    if request.method == "GET":
        read_decision = PolicyEngine.decide(snapshot, "report.read")
        if not read_decision.allowed:
            return _permission_denied(request, "report.read")
        return api_json(_serialize_report_run(record))

    decision = authorize_mutation(snapshot, "PATCH", "/api/v1/reports/runs/{report_run_id}")
    if not decision.allowed:
        return _permission_denied(request, "report.run")

    try:
        body = parse_json_body(request)
    except ValueError as exc:
        return api_error(request, code="invalid_request", message=str(exc), status=400)

    if "status" in body:
        try:
            record.status = _normalize_status(str(body["status"]))
        except ValueError as exc:
            return api_error(request, code="invalid_request", message=str(exc), status=400)

    if "row_count" in body:
        try:
            record.row_count = int(body["row_count"])
        except (TypeError, ValueError):
            return api_error(request, code="invalid_request", message="row_count must be an integer", status=400)

    if "download_url" in body:
        record.file_path = str(body["download_url"]).strip()

    if "warnings" in body:
        warnings = body["warnings"]
        if not isinstance(warnings, Iterable) or isinstance(warnings, (str, bytes)):
            return api_error(request, code="invalid_request", message="warnings must be a list", status=400)
        record.warnings_json = json.dumps([str(item) for item in warnings])

    record.save()
    return api_json(_serialize_report_run(record))


@require_http_methods(["GET"])
def report_run_download_endpoint(request: HttpRequest, run_id: str) -> HttpResponse:
    identity = sync_user_directory_context(request)
    snapshot = build_policy_snapshot(identity)
    read_decision = PolicyEngine.decide(snapshot, "report.read")
    if not read_decision.allowed:
        payload = api_error(request, code="forbidden", message="Missing permission: report.read", status=403)
        return HttpResponse(payload.content, status=payload.status_code, content_type=payload.headers.get("Content-Type"))

    record = get_object_or_404(ReportRun, report_run_id=run_id)
    if record.status != "completed":
        payload = api_error(request, code="invalid_state", message="report run is not completed", status=409)
        return HttpResponse(payload.content, status=payload.status_code, content_type=payload.headers.get("Content-Type"))

    if record.report_format != "csv":
        payload = api_error(request, code="invalid_state", message="report output format is not csv", status=400)
        return HttpResponse(payload.content, status=payload.status_code, content_type=payload.headers.get("Content-Type"))

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["run_id", "report_code", "status", "row_count"])
    writer.writerow([record.report_run_id, record.report_code, record.status, str(record.row_count)])

    filters: dict[str, Any]
    try:
        filters = json.loads(record.filters_json or "{}")
    except json.JSONDecodeError:
        filters = {}

    if filters:
        writer.writerow([])
        writer.writerow(["filter_key", "filter_value"])
        for key in sorted(filters.keys()):
            writer.writerow([key, filters[key]])

    response = HttpResponse(csv_buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="report-{run_id}.csv"'
    return response


@csrf_exempt
@require_http_methods(["POST"])
def report_email_request_endpoint(request: HttpRequest) -> JsonResponse:
    identity = sync_user_directory_context(request)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/reports/email-requests")
    if not decision.allowed:
        return _permission_denied(request, "report.email_request")

    try:
        body = parse_json_body(request)
    except ValueError as exc:
        return api_error(request, code="invalid_request", message=str(exc), status=400)

    run_id = str(body.get("run_id", "")).strip()
    requested_by = str(body.get("requested_by", identity.user_principal)).strip() or identity.user_principal
    email_to = _parse_email_list(body.get("email_to", ()))

    dto = ReportEmailRequest(run_id=run_id, email_to=email_to, requested_by=requested_by)
    try:
        dto.validate()
    except ValueError as exc:
        return api_error(request, code="invalid_request", message=str(exc), status=400)

    if not ReportRun.objects.filter(report_run_id=run_id).exists():  # type: ignore[attr-defined]
        return api_error(request, code="not_found", message=f"report run {run_id} not found", status=404)

    record = ReportEmailRequestRecord.objects.create(  # type: ignore[attr-defined]
        run_id=dto.run_id,
        email_to_csv=",".join(dto.email_to),
        requested_by=dto.requested_by,
    )

    return api_json(
        {
            "email_request_id": int(record.id),
            "run_id": dto.run_id,
            "email_to": list(dto.email_to),
            "requested_by": dto.requested_by,
        },
        status=201,
    )
