from __future__ import annotations

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
from apps.workflows.constants import WORKFLOW_DECISION_STATUS_OPTIONS
from apps.workflows.models import WorkflowDecision


def _normalize_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in WORKFLOW_DECISION_STATUS_OPTIONS:
        raise ValueError(f"status must be one of: {', '.join(WORKFLOW_DECISION_STATUS_OPTIONS)}")
    return normalized


def _serialize_decision(record: WorkflowDecision) -> dict[str, str]:
    try:
        context_payload = json.loads(record.context_json or "{}")
    except json.JSONDecodeError:
        context_payload = {}
    if not isinstance(context_payload, dict):
        context_payload = {}
    return {
        "decision_id": record.decision_id,
        "workflow_name": record.workflow_name,
        "submitted_by": record.submitted_by,
        "status": record.status,
        "action": record.action,
        "reviewed_by": record.reviewed_by,
        "review_note": record.review_note,
        "context": context_payload,
    }


def _transition_status(current_status: str, action: str) -> str:
    normalized_current = current_status.strip().lower()
    normalized_action = action.strip().lower()
    transitions: dict[tuple[str, str], str] = {
        ("pending", "approve"): "approved",
        ("pending", "reject"): "rejected",
        ("pending", "cancel"): "cancelled",
        ("approved", "reopen"): "pending",
        ("rejected", "reopen"): "pending",
        ("cancelled", "reopen"): "pending",
    }
    target = transitions.get((normalized_current, normalized_action))
    if target is None:
        raise ValueError(f"invalid transition '{normalized_action}' from status '{normalized_current}'")
    return target


def index(request: HttpRequest) -> HttpResponse:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    can_create_workflow_decision = authorize_mutation(snapshot, "POST", "/api/v1/workflows/decisions").allowed

    decisions = WorkflowDecision.objects.all().order_by("decision_id")  # type: ignore[attr-defined]
    return render(
        request,
        "workflows/index.html",
        {
            "decisions": decisions,
            "can_create_workflow_decision": can_create_workflow_decision,
        },
    )


def workflow_decision_detail_page(request: HttpRequest, decision_id: str) -> HttpResponse:
    try:
        decision = WorkflowDecision.objects.get(decision_id=decision_id)  # type: ignore[attr-defined]
    except WorkflowDecision.DoesNotExist:  # type: ignore[attr-defined]
        return render(request, "workflows/detail.html", {"error": f"Decision {decision_id} not found"}, status=404)
    return render(request, "workflows/detail.html", {"decision": decision})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def workflow_decisions_collection_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        items = [
            _serialize_decision(record)
            for record in WorkflowDecision.objects.all().order_by("decision_id")  # type: ignore[attr-defined]
        ]
        return JsonResponse({"items": items})

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/workflows/decisions")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    decision_id = str(body.get("decision_id", "")).strip() or f"dec-{uuid.uuid4().hex[:10]}"
    workflow_name = str(body.get("workflow_name", "")).strip() or "generic_workflow"
    action = str(body.get("action", "")).strip() or str(body.get("decision", "")).strip()

    if not action:
        return JsonResponse({"error": "action is required"}, status=400)

    if WorkflowDecision.objects.filter(decision_id=decision_id).exists():  # type: ignore[attr-defined]
        return JsonResponse({"error": f"decision {decision_id} already exists"}, status=409)

    try:
        record = WorkflowDecision.objects.create(
            decision_id=decision_id,
            workflow_name=workflow_name,
            submitted_by=identity.user_principal,
            action=action,
            status="pending",
            context_json=json.dumps(body.get("context", {})),
        )  # type: ignore[attr-defined]
    except IntegrityError:
        return JsonResponse({"error": f"decision {decision_id} already exists"}, status=409)

    return JsonResponse(_serialize_decision(record), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def workflow_decision_detail_endpoint(request: HttpRequest, decision_id: str) -> JsonResponse:
    try:
        record = WorkflowDecision.objects.get(decision_id=decision_id)  # type: ignore[attr-defined]
    except WorkflowDecision.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"decision {decision_id} not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(_serialize_decision(record))

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "PATCH", "/api/v1/workflows/decisions/{decision_id}")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    updated = False
    for field_name in ["status", "reviewed_by", "review_note", "action"]:
        if field_name in body:
            value = str(body[field_name]).strip()
            try:
                if field_name == "status":
                    value = _normalize_status(value)
            except ValueError as exc:
                return JsonResponse({"error": str(exc)}, status=400)
            setattr(record, field_name, value)
            updated = True

    if updated:
        record.save()

    return JsonResponse(_serialize_decision(record))


@require_http_methods(["GET"])
def workflow_decisions_open_next_endpoint(request: HttpRequest) -> JsonResponse:
    workflow_name = str(request.GET.get("workflow_name", "")).strip()
    queryset = WorkflowDecision.objects.filter(status="pending")  # type: ignore[attr-defined]
    if workflow_name:
        queryset = queryset.filter(workflow_name=workflow_name)

    record = queryset.order_by("created_at", "decision_id").first()
    if record is None:
        return JsonResponse({"error": "no pending workflow decisions"}, status=404)
    return JsonResponse(_serialize_decision(record))


@csrf_exempt
@require_http_methods(["POST"])
def workflow_decision_transition_endpoint(request: HttpRequest, decision_id: str) -> JsonResponse:
    try:
        record = WorkflowDecision.objects.get(decision_id=decision_id)  # type: ignore[attr-defined]
    except WorkflowDecision.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"decision {decision_id} not found"}, status=404)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/workflows/decisions/{decision_id}/transition")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    action = str(body.get("action", "")).strip()
    if not action:
        return JsonResponse({"error": "action is required"}, status=400)

    try:
        next_status = _transition_status(record.status, action)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    review_note = str(body.get("review_note", record.review_note)).strip()
    reviewed_by = str(body.get("reviewed_by", identity.user_principal)).strip() or identity.user_principal
    record.status = next_status
    record.review_note = review_note
    record.reviewed_by = reviewed_by
    record.save(update_fields=["status", "review_note", "reviewed_by", "updated_at"])
    return JsonResponse(_serialize_decision(record))
