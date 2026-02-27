from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from apps.core.contracts.identity import resolve_identity_context
from apps.core.services.permission_registry import authorize_mutation
from apps.identity.services import (
    accept_terms,
    bootstrap_first_admin,
    build_policy_snapshot,
    create_access_request,
    list_access_requests,
    list_pending_approvals,
    open_next_pending_approval,
    review_access_request,
    list_role_assignments,
    list_group_role_assignments,
    list_scope_grants,
    sync_user_directory,
)


def home(request: HttpRequest) -> JsonResponse:
    identity = resolve_identity_context(request)
    user_record = sync_user_directory(identity)
    return JsonResponse(
        {
            "user_principal": identity.user_principal,
            "display_name": identity.display_name,
            "groups": list(identity.groups),
            "auth_source": identity.auth_source,
            "is_anonymous": identity.is_anonymous,
            "user_directory": user_record,
        }
    )


@require_http_methods(["POST"])
def create_access_request_endpoint(request: HttpRequest) -> JsonResponse:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/access/requests")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    requested_role = str(body.get("requested_role", "")).strip()
    justification = str(body.get("justification", "")).strip()
    try:
        payload = create_access_request(identity, requested_role=requested_role, justification=justification)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(payload, status=201)


@require_http_methods(["GET"])
def list_access_requests_endpoint(request: HttpRequest) -> JsonResponse:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/access/requests/review")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    pending_only = str(request.GET.get("pending", "1")).strip() != "0"
    payload = {"items": list_access_requests(pending_only=pending_only)}
    return JsonResponse(payload)


@require_http_methods(["POST"])
def review_access_request_endpoint(request: HttpRequest, request_id: int) -> JsonResponse:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/access/requests/review")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    review_decision = str(body.get("decision", "")).strip()
    review_note = str(body.get("note", "")).strip()
    try:
        payload = review_access_request(identity, request_id=request_id, decision=review_decision, note=review_note)
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(payload)


@require_http_methods(["POST"])
def accept_terms_endpoint(request: HttpRequest) -> JsonResponse:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/access/terms/accept")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    terms_version = str(body.get("terms_version", "")).strip()
    client_ip = request.META.get("REMOTE_ADDR", "")
    try:
        payload = accept_terms(identity, terms_version=terms_version, ip_address=client_ip)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(payload, status=201)


@require_http_methods(["POST"])
def bootstrap_first_admin_endpoint(request: HttpRequest) -> JsonResponse:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)

    try:
        payload = bootstrap_first_admin(identity)
    except PermissionError as exc:
        return JsonResponse({"error": "forbidden", "reason": str(exc)}, status=403)
    return JsonResponse(payload, status=201)


@require_http_methods(["GET"])
def access_home_page(request: HttpRequest):
    return render(
        request,
        "identity/access_home.html",
        {
            "page_title": "Access",
        },
    )


@require_http_methods(["GET", "POST"])
def terms_acceptance_page(request: HttpRequest):
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    message = ""
    status_code = 200

    if request.method == "POST":
        terms_version = str(request.POST.get("terms_version", "")).strip()
        snapshot = build_policy_snapshot(identity)
        decision = authorize_mutation(snapshot, "POST", "/api/v1/access/terms/accept")
        if not decision.allowed:
            message = "Terms acceptance is not allowed for this identity."
            status_code = 403
        else:
            try:
                result = accept_terms(
                    identity,
                    terms_version=terms_version,
                    ip_address=request.META.get("REMOTE_ADDR", ""),
                )
                message = (
                    "Terms accepted successfully."
                    if result["created"]
                    else "Terms already accepted for this version."
                )
            except ValueError as exc:
                message = str(exc)
                status_code = 400

    return render(
        request,
        "identity/terms_acceptance.html",
        {
            "page_title": "Terms Acceptance",
            "message": message,
            "default_terms_version": "2026-02",
            "user_principal": identity.user_principal,
        },
        status=status_code,
    )


@require_http_methods(["GET", "POST"])
def bootstrap_first_admin_page(request: HttpRequest):
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    message = ""
    status_code = 200

    if request.method == "POST":
        try:
            bootstrap_first_admin(identity)
            message = "First admin bootstrap completed."
        except PermissionError as exc:
            message = str(exc)
            status_code = 403

    return render(
        request,
        "identity/bootstrap_first_admin.html",
        {
            "page_title": "Bootstrap First Admin",
            "message": message,
            "user_principal": identity.user_principal,
        },
        status=status_code,
    )


@require_http_methods(["GET", "POST"])
def access_request_page(request: HttpRequest):
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    message = ""
    status_code = 200

    if request.method == "POST":
        snapshot = build_policy_snapshot(identity)
        decision = authorize_mutation(snapshot, "POST", "/api/v1/access/requests")
        if not decision.allowed:
            message = "Access request submission is not allowed for this identity."
            status_code = 403
        else:
            requested_role = str(request.POST.get("requested_role", "")).strip()
            justification = str(request.POST.get("justification", "")).strip()
            try:
                create_access_request(identity, requested_role=requested_role, justification=justification)
                message = "Access request submitted."
            except ValueError as exc:
                message = str(exc)
                status_code = 400

    return render(
        request,
        "identity/access_request.html",
        {
            "page_title": "Request Access",
            "message": message,
            "user_principal": identity.user_principal,
        },
        status=status_code,
    )


@require_http_methods(["GET", "POST"])
def access_review_page(request: HttpRequest):
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    message = ""
    status_code = 200
    snapshot = build_policy_snapshot(identity)
    review_permission = authorize_mutation(snapshot, "POST", "/api/v1/access/requests/review")

    if request.method == "POST":
        if not review_permission.allowed:
            message = "Access request review is not allowed for this identity."
            status_code = 403
        else:
            try:
                request_id = int(str(request.POST.get("request_id", "")).strip())
            except ValueError:
                request_id = 0

            review_decision = str(request.POST.get("decision", "")).strip()
            review_note = str(request.POST.get("note", "")).strip()
            try:
                review_access_request(identity, request_id=request_id, decision=review_decision, note=review_note)
                message = "Access request review submitted."
            except LookupError as exc:
                message = str(exc)
                status_code = 404
            except ValueError as exc:
                message = str(exc)
                status_code = 400

    items = list_access_requests(pending_only=True) if review_permission.allowed else []
    return render(
        request,
        "identity/access_review.html",
        {
            "page_title": "Review Access Requests",
            "message": message,
            "user_principal": identity.user_principal,
            "items": items,
            "can_review": review_permission.allowed,
        },
        status=status_code,
    )


@require_http_methods(["GET"])
def pending_approvals_queue_endpoint(request: HttpRequest) -> JsonResponse:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/pending-approvals/queue/decision")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    requested_role = str(request.GET.get("requested_role", "")).strip() or None
    limit_raw = str(request.GET.get("limit", "50")).strip()
    try:
        limit = int(limit_raw)
    except ValueError:
        limit = 50
    items = list_pending_approvals(requested_role=requested_role, limit=limit)
    return JsonResponse({"items": items, "count": len(items)})


@require_http_methods(["POST"])
def pending_approvals_open_next_endpoint(request: HttpRequest) -> JsonResponse:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/pending-approvals/queue/open-next")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    requested_role = str(body.get("requested_role", "")).strip() or None
    item = open_next_pending_approval(requested_role=requested_role)
    if item is None:
        return JsonResponse({"item": None}, status=404)
    return JsonResponse({"item": item})


@require_http_methods(["POST"])
def pending_approval_decision_endpoint(request: HttpRequest, request_id: int) -> JsonResponse:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/pending-approvals/queue/decision")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    review_decision = str(body.get("decision", "")).strip()
    review_note = str(body.get("note", "")).strip()
    try:
        payload = review_access_request(identity, request_id=request_id, decision=review_decision, note=review_note)
    except LookupError as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(payload)


@require_http_methods(["GET"])
def pending_approvals_queue_page(request: HttpRequest):
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    review_permission = authorize_mutation(snapshot, "POST", "/api/v1/pending-approvals/queue/decision")
    items = list_pending_approvals(limit=100) if review_permission.allowed else []
    return render(
        request,
        "identity/pending_approvals_queue.html",
        {
            "page_title": "Pending Approvals Queue",
            "user_principal": identity.user_principal,
            "items": items,
            "can_review": review_permission.allowed,
            "role_assignments": list_role_assignments() if review_permission.allowed else [],
            "group_role_assignments": list_group_role_assignments() if review_permission.allowed else [],
            "scope_grants": list_scope_grants(user_principal=identity.user_principal) if review_permission.allowed else [],
        },
    )
