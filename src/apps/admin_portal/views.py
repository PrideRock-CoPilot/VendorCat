from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponse
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.core.contracts.identity import resolve_identity_context
from apps.core.services.permission_registry import authorize_mutation
from apps.identity.services import (
    build_policy_snapshot,
    grant_group_role,
    grant_scope,
    grant_user_role,
    list_group_role_assignments,
    list_role_assignments,
    list_scope_grants,
    revoke_group_role,
    revoke_scope,
    revoke_user_role,
    sync_user_directory,
)
from apps.core.services.policy_engine import PolicyEngine


def index(request: HttpRequest) -> HttpResponse:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    can_manage_admin = PolicyEngine.decide(snapshot, "access.review").allowed

    return render(
        request,
        "admin_portal/index.html",
        {
            "page_title": "Admin Portal",
            "user_principal": identity.user_principal,
            "can_manage_admin": can_manage_admin,
            "role_assignments": list_role_assignments() if can_manage_admin else [],
            "group_role_assignments": list_group_role_assignments() if can_manage_admin else [],
            "scope_grants": list_scope_grants() if can_manage_admin else [],
        },
    )


def _forbidden_for_mutation(request: HttpRequest, path_template: str) -> JsonResponse | None:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", path_template)
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    return None


@csrf_exempt
@require_http_methods(["GET"])
def list_admin_assignments_endpoint(request: HttpRequest) -> JsonResponse:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/admin/roles/assign")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    return JsonResponse(
        {
            "role_assignments": list_role_assignments(),
            "group_role_assignments": list_group_role_assignments(),
            "scope_grants": list_scope_grants(),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def assign_user_role_endpoint(request: HttpRequest) -> JsonResponse:
    forbidden = _forbidden_for_mutation(request, "/api/v1/admin/roles/assign")
    if forbidden is not None:
        return forbidden
    identity = resolve_identity_context(request)

    body = json.loads(request.body.decode("utf-8") or "{}")
    try:
        payload = grant_user_role(
            identity,
            target_user=str(body.get("target_user", "")).strip(),
            role=str(body.get("role", "")).strip(),
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(payload, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def revoke_user_role_endpoint(request: HttpRequest) -> JsonResponse:
    forbidden = _forbidden_for_mutation(request, "/api/v1/admin/roles/revoke")
    if forbidden is not None:
        return forbidden

    body = json.loads(request.body.decode("utf-8") or "{}")
    try:
        payload = revoke_user_role(
            target_user=str(body.get("target_user", "")).strip(),
            role=str(body.get("role", "")).strip(),
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(payload)


@csrf_exempt
@require_http_methods(["POST"])
def assign_group_role_endpoint(request: HttpRequest) -> JsonResponse:
    forbidden = _forbidden_for_mutation(request, "/api/v1/admin/groups/assign")
    if forbidden is not None:
        return forbidden
    identity = resolve_identity_context(request)

    body = json.loads(request.body.decode("utf-8") or "{}")
    try:
        payload = grant_group_role(
            identity,
            target_group=str(body.get("target_group", "")).strip(),
            role=str(body.get("role", "")).strip(),
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(payload, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def revoke_group_role_endpoint(request: HttpRequest) -> JsonResponse:
    forbidden = _forbidden_for_mutation(request, "/api/v1/admin/groups/revoke")
    if forbidden is not None:
        return forbidden

    body = json.loads(request.body.decode("utf-8") or "{}")
    try:
        payload = revoke_group_role(
            target_group=str(body.get("target_group", "")).strip(),
            role=str(body.get("role", "")).strip(),
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(payload)


@csrf_exempt
@require_http_methods(["POST"])
def grant_scope_endpoint(request: HttpRequest) -> JsonResponse:
    forbidden = _forbidden_for_mutation(request, "/api/v1/admin/scopes/grant")
    if forbidden is not None:
        return forbidden
    identity = resolve_identity_context(request)

    body = json.loads(request.body.decode("utf-8") or "{}")
    try:
        payload = grant_scope(
            identity,
            target_user=str(body.get("target_user", "")).strip(),
            org_id=str(body.get("org_id", "")).strip(),
            scope_level=str(body.get("scope_level", "")).strip(),
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(payload, status=201)


@csrf_exempt
@require_http_methods(["POST"])
def revoke_scope_endpoint(request: HttpRequest) -> JsonResponse:
    forbidden = _forbidden_for_mutation(request, "/api/v1/admin/scopes/revoke")
    if forbidden is not None:
        return forbidden

    body = json.loads(request.body.decode("utf-8") or "{}")
    try:
        payload = revoke_scope(
            target_user=str(body.get("target_user", "")).strip(),
            org_id=str(body.get("org_id", "")).strip(),
            scope_level=str(body.get("scope_level", "")).strip(),
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(payload)
