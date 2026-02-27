from __future__ import annotations

import json
import uuid

from django.contrib import messages
from django.db import IntegrityError, models
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator

from apps.core.contracts.identity import resolve_identity_context
from apps.core.services.permission_registry import authorize_mutation
from apps.identity.services import build_policy_snapshot, sync_user_directory
from apps.projects.constants import PROJECT_SECTIONS, PROJECT_STATUSES
from apps.projects.models import Project
from apps.workflows.models import WorkflowDecision


def _normalize_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in PROJECT_STATUSES:
        raise ValueError(f"lifecycle_state must be one of: {', '.join(PROJECT_STATUSES)}")
    return normalized


def _serialize_project(record: Project) -> dict[str, str]:
    return {
        "project_id": record.project_id,
        "project_name": record.project_name,
        "owner_principal": record.owner_principal,
        "lifecycle_state": record.lifecycle_state,
    }


def _serialize_project_section(project_id: str, key: str, label: str) -> dict[str, str]:
    return {
        "project_id": project_id,
        "section_key": key,
        "section_label": label,
    }


@require_http_methods(["GET"])
def index(request: HttpRequest) -> HttpResponse:
    items = [
        _serialize_project(record)
        for record in Project.objects.all().order_by("project_id")[:50]  # type: ignore[attr-defined]
    ]
    return render(
        request,
        "projects/index.html",
        {
            "page_title": "Projects",
            "section_name": "Projects",
            "items": items,
        },
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def project_collection_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        items = [
            _serialize_project(record)
            for record in Project.objects.all().order_by("project_id")  # type: ignore[attr-defined]
        ]
        return JsonResponse({"items": items})

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/projects")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    project_id = str(body.get("project_id", "")).strip()
    project_name = str(body.get("project_name", "")).strip() or project_id
    owner_principal = str(body.get("owner_principal", identity.user_principal)).strip()
    lifecycle_state = str(body.get("lifecycle_state", "active")).strip() or "active"

    if not project_id:
        return JsonResponse({"error": "project_id is required"}, status=400)
    try:
        lifecycle_state = _normalize_status(lifecycle_state)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        record = Project.objects.create(
            project_id=project_id,
            project_name=project_name,
            owner_principal=owner_principal,
            lifecycle_state=lifecycle_state,
        )  # type: ignore[attr-defined]
    except IntegrityError:
        return JsonResponse({"error": f"project {project_id} already exists"}, status=409)

    return JsonResponse(_serialize_project(record), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def update_project_endpoint(request: HttpRequest, project_id: str) -> JsonResponse:
    try:
        record = Project.objects.get(project_id=project_id)  # type: ignore[attr-defined]
    except Project.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"project {project_id} not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(_serialize_project(record))

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "PATCH", "/api/v1/projects/{project_id}")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    updated = False
    for field_name in ["project_name", "owner_principal", "lifecycle_state"]:
        if field_name in body:
            value = str(body[field_name]).strip()
            if field_name == "lifecycle_state":
                try:
                    value = _normalize_status(value)
                except ValueError as exc:
                    return JsonResponse({"error": str(exc)}, status=400)
            setattr(record, field_name, value)
            updated = True

    if updated:
        record.save()
    return JsonResponse(_serialize_project(record))


@require_http_methods(["GET"])
def project_sections_endpoint(request: HttpRequest, project_id: str) -> JsonResponse:
    try:
        Project.objects.get(project_id=project_id)  # type: ignore[attr-defined]
    except Project.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"project {project_id} not found"}, status=404)

    items = [_serialize_project_section(project_id, key, label) for key, label in PROJECT_SECTIONS]
    return JsonResponse({"items": items})


@csrf_exempt
@require_http_methods(["POST"])
def project_section_change_request_endpoint(
    request: HttpRequest,
    project_id: str,
    section_key: str,
) -> JsonResponse:
    try:
        Project.objects.get(project_id=project_id)  # type: ignore[attr-defined]
    except Project.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"project {project_id} not found"}, status=404)

    allowed_sections = {key for key, _ in PROJECT_SECTIONS}
    normalized_section = section_key.strip().lower()
    if normalized_section not in allowed_sections:
        return JsonResponse({"error": f"invalid section '{section_key}'"}, status=400)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/projects/{project_id}/sections/{section_key}/requests")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    payload = body.get("payload", {})
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return JsonResponse({"error": "payload must be an object"}, status=400)

    record = WorkflowDecision.objects.create(  # type: ignore[attr-defined]
        decision_id=f"dec-proj-{uuid.uuid4().hex[:10]}",
        workflow_name="project_section_change",
        submitted_by=identity.user_principal,
        status="pending",
        action="update_project_section",
        context_json=json.dumps(
            {
                "project_id": project_id,
                "section_key": normalized_section,
                "payload": payload,
            }
        ),
    )
    return JsonResponse(
        {
            "decision_id": record.decision_id,
            "status": record.status,
            "workflow_name": record.workflow_name,
            "project_id": project_id,
            "section_key": normalized_section,
        },
        status=201,
    )


# ===== HTML Pages (UI Views) =====

@require_http_methods(["GET"])
def project_list_page(request: HttpRequest) -> HttpResponse:
    """Render project list page with filtering and pagination."""
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    can_create_project = authorize_mutation(snapshot, "POST", "/api/v1/projects").allowed
    can_edit_project = authorize_mutation(snapshot, "PATCH", "/api/v1/projects/{project_id}").allowed

    queryset = Project.objects.all().order_by("-updated_at")
    
    # Apply filters
    search_query = request.GET.get("q", "").strip()
    if search_query:
        queryset = queryset.filter(
            models.Q(project_id__icontains=search_query) |
            models.Q(project_name__icontains=search_query)
        )
    
    status = request.GET.get("status", "").strip()
    if status and status in PROJECT_STATUSES:
        queryset = queryset.filter(lifecycle_state=status)
    
    # Pagination
    paginator = Paginator(queryset, 25)
    page_num = request.GET.get("page", 1)
    page = paginator.get_page(page_num)
    
    return render(
        request,
        "projects/index.html",
        {
            "items": page.object_list,
            "page": page,
            "paginator": paginator,
            "search_query": search_query,
            "can_create_project": can_create_project,
            "can_edit_project": can_edit_project,
        },
    )


@require_http_methods(["GET"])
def project_detail_page(request: HttpRequest, project_id: str) -> HttpResponse:
    """Render project detail page."""
    project = get_object_or_404(Project, project_id=project_id)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    can_edit_project = authorize_mutation(snapshot, "PATCH", "/api/v1/projects/{project_id}").allowed
    
    return render(
        request,
        "projects/detail.html",
        {
            "project": project,
            "can_edit_project": can_edit_project,
        },
    )


@require_http_methods(["GET", "POST"])
def project_form_page(request: HttpRequest, project_id: str | None = None) -> HttpResponse:
    """Render project form page (create or edit)."""
    project = None
    form_errors = {}
    
    if project_id:
        project = get_object_or_404(Project, project_id=project_id)
    
    if request.method == "POST":
        # Check permissions
        identity = resolve_identity_context(request)
        sync_user_directory(identity)
        snapshot = build_policy_snapshot(identity)
        decision = authorize_mutation(snapshot, "POST" if not project else "PATCH", "/api/v1/projects")
        if not decision.allowed:
            messages.error(request, f"Permission denied: {decision.reason}")
            if project:
                return redirect(f"/projects/{project.project_id}")
            return redirect("/projects")
        
        # Extract form data
        project_id_val = request.POST.get("project_id", "").strip()
        project_name = request.POST.get("project_name", "").strip()
        owner_principal = request.POST.get("owner_principal", "").strip()
        lifecycle_state = request.POST.get("lifecycle_state", "").strip()
        
        # Validation
        if not project_id_val:
            form_errors["project_id"] = ["Project ID is required"]
        if not project_name:
            form_errors["project_name"] = ["Project name is required"]
        if not owner_principal:
            form_errors["owner_principal"] = ["Owner principal is required"]
        
        try:
            lifecycle_state = _normalize_status(lifecycle_state)
        except ValueError as e:
            form_errors["lifecycle_state"] = [str(e)]
        
        if form_errors:
            return render(
                request,
                "projects/form.html",
                {
                    "project": project,
                    "form_errors": form_errors,
                },
            )
        
        # Create or update
        if project:
            # Update existing
            project.project_name = project_name
            project.owner_principal = owner_principal
            project.lifecycle_state = lifecycle_state
            project.save()
            messages.success(request, f"Project {project.project_id} updated successfully")
            return redirect(f"/projects/{project.project_id}")
        else:
            # Create new
            if Project.objects.filter(project_id=project_id_val).exists():
                form_errors["project_id"] = ["Project ID already exists"]
                return render(
                    request,
                    "projects/form.html",
                    {
                        "project": None,
                        "form_errors": form_errors,
                    },
                )
            
            try:
                project = Project.objects.create(
                    project_id=project_id_val,
                    project_name=project_name,
                    owner_principal=owner_principal,
                    lifecycle_state=lifecycle_state,
                )
                messages.success(request, f"Project {project_id_val} created successfully")
                return redirect(f"/projects/{project.project_id}")
            except IntegrityError:
                form_errors["project_id"] = ["Project ID already exists"]
                return render(
                    request,
                    "projects/form.html",
                    {
                        "project": None,
                        "form_errors": form_errors,
                    },
                )
    
    return render(
        request,
        "projects/form.html",
        {
            "project": project,
            "form_errors": form_errors,
        },
    )
