from __future__ import annotations

import json

from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.core.contracts.identity import resolve_identity_context
from apps.core.services.permission_registry import authorize_mutation
from apps.demos.constants import DEMO_OUTCOMES, DEMO_TYPES
from apps.demos.models import Demo
from apps.identity.services import build_policy_snapshot, sync_user_directory
from apps.vendors.constants import LIFECYCLE_STATES


def _normalize_choice(value: str, allowed: list[str], field_name: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        return ""
    canonical_by_lower = {item.lower(): item for item in allowed}
    canonical = canonical_by_lower.get(normalized)
    if canonical:
        return canonical
    raise ValueError(f"{field_name} must be one of: {', '.join(allowed)}")


def _normalize_lifecycle(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in LIFECYCLE_STATES:
        raise ValueError(f"lifecycle_state must be one of: {', '.join(LIFECYCLE_STATES)}")
    return normalized


def _serialize_demo(record: Demo) -> dict[str, str]:
    return {
        "demo_id": record.demo_id,
        "demo_name": record.demo_name,
        "demo_type": record.demo_type,
        "demo_outcome": record.demo_outcome,
        "lifecycle_state": record.lifecycle_state,
        "project_id": record.project_id,
    }


def index(request: HttpRequest) -> HttpResponse:
    demos = Demo.objects.all().order_by("demo_id")  # type: ignore[attr-defined]
    return render(request, "demos/index.html", {"demos": demos})


def demo_detail_page(request: HttpRequest, demo_id: str) -> HttpResponse:
    try:
        demo = Demo.objects.get(demo_id=demo_id)  # type: ignore[attr-defined]
    except Demo.DoesNotExist:  # type: ignore[attr-defined]
        return render(request, "demos/detail.html", {"error": f"Demo {demo_id} not found"}, status=404)
    return render(request, "demos/detail.html", {"demo": demo})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def demos_collection_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        items = [
            _serialize_demo(record)
            for record in Demo.objects.all().order_by("demo_id")  # type: ignore[attr-defined]
        ]
        return JsonResponse({"items": items})

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/demos")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    demo_id = str(body.get("demo_id", "")).strip()
    demo_name = str(body.get("demo_name", "")).strip()
    demo_type = str(body.get("demo_type", "")).strip()
    demo_outcome = str(body.get("demo_outcome", "")).strip()
    lifecycle_state = str(body.get("lifecycle_state", "draft")).strip() or "draft"
    project_id = str(body.get("project_id", "")).strip()

    if not demo_id:
        return JsonResponse({"error": "demo_id is required"}, status=400)
    if not demo_name:
        return JsonResponse({"error": "demo_name is required"}, status=400)

    try:
        lifecycle_state = _normalize_lifecycle(lifecycle_state)
        demo_type = _normalize_choice(demo_type, DEMO_TYPES, "demo_type")
        demo_outcome = _normalize_choice(demo_outcome, DEMO_OUTCOMES, "demo_outcome")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if Demo.objects.filter(demo_id=demo_id).exists():  # type: ignore[attr-defined]
        return JsonResponse({"error": f"demo {demo_id} already exists"}, status=409)

    try:
        record = Demo.objects.create(
            demo_id=demo_id,
            demo_name=demo_name,
            demo_type=demo_type,
            demo_outcome=demo_outcome,
            lifecycle_state=lifecycle_state,
            project_id=project_id,
        )  # type: ignore[attr-defined]
    except IntegrityError:
        return JsonResponse({"error": f"demo {demo_id} already exists"}, status=409)

    return JsonResponse(_serialize_demo(record), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def demo_detail_endpoint(request: HttpRequest, demo_id: str) -> JsonResponse:
    try:
        record = Demo.objects.get(demo_id=demo_id)  # type: ignore[attr-defined]
    except Demo.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"demo {demo_id} not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(_serialize_demo(record))

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "PATCH", "/api/v1/demos/{demo_id}")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    updated = False
    for field_name in ["demo_name", "demo_type", "demo_outcome", "lifecycle_state", "project_id"]:
        if field_name in body:
            value = str(body[field_name]).strip()
            try:
                if field_name == "demo_type":
                    value = _normalize_choice(value, DEMO_TYPES, "demo_type")
                if field_name == "demo_outcome":
                    value = _normalize_choice(value, DEMO_OUTCOMES, "demo_outcome")
                if field_name == "lifecycle_state":
                    value = _normalize_lifecycle(value)
            except ValueError as exc:
                return JsonResponse({"error": str(exc)}, status=400)
            setattr(record, field_name, value)
            updated = True

    if updated:
        record.save()

    return JsonResponse(_serialize_demo(record))
