from __future__ import annotations

# pyright: reportAttributeAccessIssue=false

import json
import uuid

from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.core.contracts.identity import resolve_identity_context
from apps.core.services.permission_registry import authorize_mutation
from apps.identity.services import build_policy_snapshot, sync_user_directory
from apps.imports.constants import IMPORT_FILE_FORMAT_OPTIONS, IMPORT_JOB_STATUS_OPTIONS
from apps.imports.contracts import ImportJobRequest
from apps.imports.models import ImportJob


def _normalize_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in IMPORT_JOB_STATUS_OPTIONS:
        raise ValueError(f"status must be one of: {', '.join(IMPORT_JOB_STATUS_OPTIONS)}")
    return normalized


def _normalize_format(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        return ""
    if normalized not in IMPORT_FILE_FORMAT_OPTIONS:
        raise ValueError(f"file_format must be one of: {', '.join(IMPORT_FILE_FORMAT_OPTIONS)}")
    return normalized


def _serialize_import_job(record: ImportJob) -> dict[str, object]:
    workflow_context = _load_workflow_context(record)
    return {
        "import_job_id": record.import_job_id,
        "source_system": record.source_system,
        "source_object": record.source_object,
        "file_name": record.file_name,
        "file_format": record.file_format,
        "status": record.status,
        "submitted_by": record.submitted_by,
        "row_count": str(record.row_count),
        "staged_count": str(record.staged_count),
        "error_count": str(record.error_count),
        "review_note": record.review_note,
        "workflow_context": workflow_context,
    }


def _load_workflow_context(record: ImportJob) -> dict[str, object]:
    try:
        payload = json.loads(record.workflow_context_json or "{}")
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return payload


def _save_workflow_context(record: ImportJob, context_payload: dict[str, object]) -> None:
    record.workflow_context_json = json.dumps(context_payload)


def _authorize_import_v4_mutation(request: HttpRequest, path_template: str) -> JsonResponse | None:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", path_template)
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    return None


def index(request: HttpRequest) -> HttpResponse:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    can_create_import_job = authorize_mutation(snapshot, "POST", "/api/v1/imports/jobs").allowed

    import_jobs = ImportJob.objects.all().order_by("import_job_id")  # type: ignore[attr-defined]
    return render(
        request,
        "imports/index.html",
        {
            "import_jobs": import_jobs,
            "can_create_import_job": can_create_import_job,
        },
    )


def import_job_detail_page(request: HttpRequest, import_job_id: str) -> HttpResponse:
    try:
        job = ImportJob.objects.get(import_job_id=import_job_id)  # type: ignore[attr-defined]
    except ImportJob.DoesNotExist:  # type: ignore[attr-defined]
        return render(request, "imports/detail.html", {"error": f"Import job {import_job_id} not found"}, status=404)
    return render(request, "imports/detail.html", {"job": job})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def import_jobs_collection_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        items = [
            _serialize_import_job(record)
            for record in ImportJob.objects.all().order_by("import_job_id")  # type: ignore[attr-defined]
        ]
        return JsonResponse({"items": items})

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/imports/jobs")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    import_job_id = str(body.get("import_job_id", "")).strip() or f"imp-{uuid.uuid4().hex[:12]}"
    source_system = str(body.get("source_system", "")).strip()
    source_object = str(body.get("source_object", "")).strip()
    file_name = str(body.get("file_name", "")).strip()
    file_format = str(body.get("file_format", "")).strip() or ""

    if not source_system:
        return JsonResponse({"error": "source_system is required"}, status=400)
    if not file_name:
        return JsonResponse({"error": "file_name is required"}, status=400)

    try:
        if file_format:
            file_format = _normalize_format(file_format)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    request_contract = ImportJobRequest(
        source_system=source_system,
        source_object=source_object,
        file_name=file_name,
        submitted_by=identity.user_principal,
        mapping_profile=str(body.get("mapping_profile", "")).strip() or None,
    )
    try:
        request_contract.validate()
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if ImportJob.objects.filter(import_job_id=import_job_id).exists():  # type: ignore[attr-defined]
        return JsonResponse({"error": f"import job {import_job_id} already exists"}, status=409)

    try:
        record = ImportJob.objects.create(
            import_job_id=import_job_id,
            source_system=source_system,
            source_object=source_object,
            file_name=file_name,
            file_format=file_format,
            status="submitted",
            submitted_by=identity.user_principal,
        )  # type: ignore[attr-defined]
    except IntegrityError:
        return JsonResponse({"error": f"import job {import_job_id} already exists"}, status=409)

    return JsonResponse(_serialize_import_job(record), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def import_job_detail_endpoint(request: HttpRequest, import_job_id: str) -> JsonResponse:
    try:
        record = ImportJob.objects.get(import_job_id=import_job_id)  # type: ignore[attr-defined]
    except ImportJob.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"import job {import_job_id} not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(_serialize_import_job(record))

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "PATCH", "/api/v1/imports/jobs/{import_job_id}")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    updated = False
    for field_name in ["status", "file_format", "row_count", "staged_count", "error_count", "error_message"]:
        if field_name in body:
            value = body[field_name]
            try:
                if field_name == "status":
                    value = _normalize_status(str(value).strip())
                elif field_name == "file_format":
                    value = _normalize_format(str(value).strip())
                elif field_name in ["row_count", "staged_count", "error_count"]:
                    value = int(value)
                else:
                    value = str(value).strip()
            except (ValueError, TypeError) as exc:
                return JsonResponse({"error": str(exc)}, status=400)
            setattr(record, field_name, value)
            updated = True

    if updated:
        record.save()

    return JsonResponse(_serialize_import_job(record))


@csrf_exempt
@require_http_methods(["POST"])
def import_job_preview_endpoint(request: HttpRequest, import_job_id: str) -> JsonResponse:
    try:
        record = ImportJob.objects.get(import_job_id=import_job_id)  # type: ignore[attr-defined]
    except ImportJob.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"import job {import_job_id} not found"}, status=404)

    forbidden = _authorize_import_v4_mutation(request, "/api/v1/imports/jobs/{import_job_id}/preview")
    if forbidden is not None:
        return forbidden

    body = json.loads(request.body.decode("utf-8") or "{}")
    blocked_rows = int(body.get("blocked_rows", 0) or 0)
    warning_count = int(body.get("warning_count", 0) or 0)

    context_payload = _load_workflow_context(record)
    context_payload["preview"] = {
        "blocked_rows": blocked_rows,
        "warning_count": warning_count,
    }
    _save_workflow_context(record, context_payload)
    record.error_count = max(0, blocked_rows)
    record.status = "previewed"
    record.save(update_fields=["workflow_context_json", "error_count", "status", "updated_at"])
    return JsonResponse(_serialize_import_job(record))


@csrf_exempt
@require_http_methods(["POST"])
def import_job_mapping_endpoint(request: HttpRequest, import_job_id: str) -> JsonResponse:
    try:
        record = ImportJob.objects.get(import_job_id=import_job_id)  # type: ignore[attr-defined]
    except ImportJob.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"import job {import_job_id} not found"}, status=404)

    forbidden = _authorize_import_v4_mutation(request, "/api/v1/imports/jobs/{import_job_id}/mapping")
    if forbidden is not None:
        return forbidden

    body = json.loads(request.body.decode("utf-8") or "{}")
    mapping_profile_id = str(body.get("mapping_profile_id", "")).strip()
    source_target_mapping = body.get("source_target_mapping", {})

    if not mapping_profile_id:
        return JsonResponse({"error": "mapping_profile_id is required"}, status=400)
    if not isinstance(source_target_mapping, dict):
        return JsonResponse({"error": "source_target_mapping must be an object"}, status=400)

    context_payload = _load_workflow_context(record)
    context_payload["mapping"] = {
        "mapping_profile_id": mapping_profile_id,
        "source_target_mapping": source_target_mapping,
    }
    _save_workflow_context(record, context_payload)
    record.mapping_profile_id = mapping_profile_id
    record.status = "mapped"
    record.save(update_fields=["workflow_context_json", "mapping_profile_id", "status", "updated_at"])
    return JsonResponse(_serialize_import_job(record))


@csrf_exempt
@require_http_methods(["POST"])
def import_job_stage_endpoint(request: HttpRequest, import_job_id: str) -> JsonResponse:
    try:
        record = ImportJob.objects.get(import_job_id=import_job_id)  # type: ignore[attr-defined]
    except ImportJob.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"import job {import_job_id} not found"}, status=404)

    forbidden = _authorize_import_v4_mutation(request, "/api/v1/imports/jobs/{import_job_id}/stage")
    if forbidden is not None:
        return forbidden

    body = json.loads(request.body.decode("utf-8") or "{}")
    staged_count = int(body.get("staged_count", record.row_count) or 0)
    context_payload = _load_workflow_context(record)
    context_payload["staging"] = {"staged_count": staged_count}
    _save_workflow_context(record, context_payload)
    record.staged_count = max(0, staged_count)
    record.status = "staged"
    record.save(update_fields=["workflow_context_json", "staged_count", "status", "updated_at"])
    return JsonResponse(_serialize_import_job(record))


@csrf_exempt
@require_http_methods(["POST"])
def import_job_review_endpoint(request: HttpRequest, import_job_id: str) -> JsonResponse:
    try:
        record = ImportJob.objects.get(import_job_id=import_job_id)  # type: ignore[attr-defined]
    except ImportJob.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"import job {import_job_id} not found"}, status=404)

    forbidden = _authorize_import_v4_mutation(request, "/api/v1/imports/jobs/{import_job_id}/review")
    if forbidden is not None:
        return forbidden

    body = json.loads(request.body.decode("utf-8") or "{}")
    approved = bool(body.get("approved", False))
    review_note = str(body.get("review_note", "")).strip()
    context_payload = _load_workflow_context(record)
    context_payload["review"] = {
        "approved": approved,
        "review_note": review_note,
    }
    _save_workflow_context(record, context_payload)
    record.review_note = review_note
    record.status = "approved" if approved else "in_review"
    record.save(update_fields=["workflow_context_json", "review_note", "status", "updated_at"])
    return JsonResponse(_serialize_import_job(record))


@csrf_exempt
@require_http_methods(["POST"])
def import_job_apply_endpoint(request: HttpRequest, import_job_id: str) -> JsonResponse:
    try:
        record = ImportJob.objects.get(import_job_id=import_job_id)  # type: ignore[attr-defined]
    except ImportJob.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"import job {import_job_id} not found"}, status=404)

    forbidden = _authorize_import_v4_mutation(request, "/api/v1/imports/jobs/{import_job_id}/apply")
    if forbidden is not None:
        return forbidden

    body = json.loads(request.body.decode("utf-8") or "{}")
    force_apply = bool(body.get("force_apply", False))
    if record.status != "approved" and not force_apply:
        return JsonResponse({"error": "import job must be approved before apply"}, status=409)

    context_payload = _load_workflow_context(record)
    context_payload["apply"] = {
        "force_apply": force_apply,
        "include_row_ids": body.get("include_row_ids", []),
    }
    _save_workflow_context(record, context_payload)
    record.status = "applied"
    record.save(update_fields=["workflow_context_json", "status", "updated_at"])
    return JsonResponse(_serialize_import_job(record))
