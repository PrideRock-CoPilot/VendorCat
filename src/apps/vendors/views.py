from __future__ import annotations

import json
from django.db import transaction

from django.contrib import messages
from django.db import IntegrityError, models
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator

from apps.core.contracts.identity import resolve_identity_context
from apps.core.services.permission_registry import authorize_mutation
from apps.core.services.lob_authorization import (
    can_view_contracts,
    has_lob_scope,
    has_vendor_level_scope,
    is_scope_restricted,
)
from apps.identity.services import build_policy_snapshot, sync_user_directory
from apps.vendors.constants import LIFECYCLE_STATES, RISK_TIERS
from apps.vendors.models import Vendor, VendorContact, VendorIdentifier, OnboardingWorkflow, VendorWarning
from apps.vendors.models import VendorNote, VendorTicket, VendorDemo, VendorBusinessOwner, VendorOrgAssignment
from apps.vendors.serializers import (
    VendorContactSerializer,
    VendorIdentifierSerializer,
    VendorDetailSerializer,
    OnboardingWorkflowSerializer,
    OnboardingWorkflowStateChangeSerializer,
)
from apps.projects.models import Project
from apps.contracts.models import Contract
from apps.offerings.models import Offering
from apps.identity.models import UserDirectory


def _normalize_lifecycle(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in LIFECYCLE_STATES:
        raise ValueError(f"lifecycle_state must be one of: {', '.join(LIFECYCLE_STATES)}")
    return normalized


def _normalize_risk_tier(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in RISK_TIERS:
        raise ValueError(f"risk_tier must be one of: {', '.join(RISK_TIERS)}")
    return normalized


def _serialize_vendor(record: Vendor) -> dict[str, str]:
    return {
        "vendor_id": record.vendor_id,
        "legal_name": record.legal_name,
        "display_name": record.display_name,
        "lifecycle_state": record.lifecycle_state,
        "owner_org_id": record.owner_org_id,
        "risk_tier": record.risk_tier,
    }


def _normalize_limit(raw_limit: str | None, *, default: int = 10, maximum: int = 50) -> int:
    try:
        value = int(str(raw_limit or "").strip() or default)
    except ValueError:
        value = default
    return max(1, min(value, maximum))


def _search_term(request: HttpRequest) -> str:
    return str(request.GET.get("q", "")).strip()


def _parse_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if not normalized:
        return default
    return normalized in {"1", "true", "on", "yes", "y"}


def _resolve_contact_payload(body: dict[str, object]) -> tuple[dict[str, object], str | None]:
    contact_source = str(body.get("contact_source", "external")).strip().lower() or "external"
    payload: dict[str, object] = {
        "full_name": str(body.get("full_name", "")).strip(),
        "contact_type": str(body.get("contact_type", "primary")).strip() or "primary",
        "email": str(body.get("email", "")).strip(),
        "phone": str(body.get("phone", "")).strip(),
        "title": str(body.get("title", "")).strip(),
        "is_primary": _parse_bool(body.get("is_primary"), default=False),
        "is_active": _parse_bool(body.get("is_active"), default=True),
        "notes": str(body.get("notes", "")).strip(),
    }

    if contact_source == "internal":
        principal = str(body.get("internal_user_principal", "")).strip().lower()
        if not principal:
            return payload, "internal_user_principal is required for internal contacts"
        record = UserDirectory.objects.filter(user_principal=principal, active_flag=True).first()
        if not record:
            return payload, "internal contact must map to an active user"
        payload["full_name"] = (record.display_name or record.user_principal).strip()
        payload["email"] = str(record.email or record.user_principal).strip()
        payload["title"] = str(body.get("contact_role", payload["title"]))
    else:
        raw_contact_id = str(body.get("external_contact_id", "")).strip()
        if raw_contact_id:
            try:
                source_contact = VendorContact.objects.filter(id=int(raw_contact_id), is_active=True).first()
            except (TypeError, ValueError):
                source_contact = None
            if source_contact:
                payload["full_name"] = payload["full_name"] or source_contact.full_name
                payload["email"] = payload["email"] or (source_contact.email or "")
                payload["phone"] = payload["phone"] or (source_contact.phone or "")
                payload["title"] = payload["title"] or (source_contact.title or "")

    if not str(payload.get("full_name", "")).strip():
        return payload, "full_name is required"
    return payload, None


@require_http_methods(["GET"])
def search_vendors_endpoint(request: HttpRequest) -> JsonResponse:
    term = _search_term(request)
    limit = _normalize_limit(request.GET.get("limit"), default=10)
    queryset = Vendor.objects.all().order_by("display_name")  # type: ignore[attr-defined]
    if term:
        queryset = queryset.filter(
            models.Q(vendor_id__icontains=term)
            | models.Q(display_name__icontains=term)
            | models.Q(legal_name__icontains=term)
        )
    items = [
        {
            "type": "vendor",
            "id": record.vendor_id,
            "label": record.display_name,
            "subtitle": record.legal_name,
        }
        for record in queryset[:limit]
    ]
    return JsonResponse({"items": items})


@require_http_methods(["GET"])
def search_offerings_endpoint(request: HttpRequest) -> JsonResponse:
    term = _search_term(request)
    limit = _normalize_limit(request.GET.get("limit"), default=10)
    queryset = Offering.objects.select_related("vendor").all().order_by("offering_name")  # type: ignore[attr-defined]
    if term:
        queryset = queryset.filter(
            models.Q(offering_id__icontains=term)
            | models.Q(offering_name__icontains=term)
            | models.Q(vendor__display_name__icontains=term)
        )
    items = [
        {
            "type": "offering",
            "id": record.offering_id,
            "label": record.offering_name,
            "subtitle": f"{record.vendor.display_name} ({record.vendor.vendor_id})",
        }
        for record in queryset[:limit]
    ]
    return JsonResponse({"items": items})


@require_http_methods(["GET"])
def search_projects_endpoint(request: HttpRequest) -> JsonResponse:
    term = _search_term(request)
    limit = _normalize_limit(request.GET.get("limit"), default=10)
    queryset = Project.objects.all().order_by("project_name")  # type: ignore[attr-defined]
    if term:
        queryset = queryset.filter(
            models.Q(project_id__icontains=term)
            | models.Q(project_name__icontains=term)
            | models.Q(owner_principal__icontains=term)
        )
    items = [
        {
            "type": "project",
            "id": record.project_id,
            "label": record.project_name,
            "subtitle": record.owner_principal,
        }
        for record in queryset[:limit]
    ]
    return JsonResponse({"items": items})


@require_http_methods(["GET"])
def search_contracts_endpoint(request: HttpRequest) -> JsonResponse:
    term = _search_term(request)
    limit = _normalize_limit(request.GET.get("limit"), default=10)
    queryset = Contract.objects.select_related("vendor").all().order_by("contract_id")  # type: ignore[attr-defined]
    if term:
        queryset = queryset.filter(
            models.Q(contract_id__icontains=term)
            | models.Q(contract_number__icontains=term)
            | models.Q(vendor__display_name__icontains=term)
        )
    items = [
        {
            "type": "contract",
            "id": record.contract_id,
            "label": record.contract_number or record.contract_id,
            "subtitle": f"{record.vendor.display_name} ({record.vendor.vendor_id})",
        }
        for record in queryset[:limit]
    ]
    return JsonResponse({"items": items})


@require_http_methods(["GET"])
def search_users_endpoint(request: HttpRequest) -> JsonResponse:
    term = _search_term(request)
    limit = _normalize_limit(request.GET.get("limit"), default=10)
    include_inactive = _parse_bool(request.GET.get("include_inactive"), default=False)
    queryset = UserDirectory.objects.all()
    if not include_inactive:
        queryset = queryset.filter(active_flag=True)
    queryset = queryset.order_by("display_name")
    if term:
        queryset = queryset.filter(
            models.Q(user_principal__icontains=term)
            | models.Q(display_name__icontains=term)
            | models.Q(email__icontains=term)
        )
    items = [
        {
            "type": "user",
            "id": record.user_principal,
            "label": record.display_name or record.user_principal,
            "subtitle": record.email,
        }
        for record in queryset[:limit]
    ]
    return JsonResponse({"items": items})


@require_http_methods(["GET"])
def search_contacts_endpoint(request: HttpRequest) -> JsonResponse:
    term = _search_term(request)
    limit = _normalize_limit(request.GET.get("limit"), default=10)
    queryset = VendorContact.objects.select_related("vendor").filter(is_active=True).order_by("full_name")
    if term:
        queryset = queryset.filter(
            models.Q(full_name__icontains=term)
            | models.Q(email__icontains=term)
            | models.Q(vendor__display_name__icontains=term)
        )
    items = [
        {
            "type": "contact",
            "id": str(record.id),
            "label": record.full_name,
            "subtitle": f"{record.vendor.display_name} ({record.vendor.vendor_id})",
            "email": record.email or "",
            "phone": record.phone or "",
            "title": record.title or "",
        }
        for record in queryset[:limit]
    ]
    return JsonResponse({"items": items})


def _validate_merge_request(payload: dict[str, object]) -> tuple[str, list[str]]:
    survivor_vendor_id = str(payload.get("survivor_vendor_id", "")).strip()
    merged_vendor_ids_raw = payload.get("merged_vendor_ids", [])
    if not isinstance(merged_vendor_ids_raw, list):
        raise ValueError("merged_vendor_ids must be a list")
    merged_vendor_ids = [str(item).strip() for item in merged_vendor_ids_raw if str(item).strip()]
    merged_vendor_ids = [item for item in merged_vendor_ids if item != survivor_vendor_id]
    merged_vendor_ids = list(dict.fromkeys(merged_vendor_ids))
    if not survivor_vendor_id:
        raise ValueError("survivor_vendor_id is required")
    if not merged_vendor_ids:
        raise ValueError("merged_vendor_ids must include at least one donor vendor")
    return survivor_vendor_id, merged_vendor_ids


def _build_merge_preview(survivor: Vendor, donors: list[Vendor]) -> dict[str, object]:
    donor_ids = [donor.vendor_id for donor in donors]
    conflicts: list[dict[str, object]] = []
    for field_name in ["legal_name", "display_name", "owner_org_id", "risk_tier", "lifecycle_state"]:
        differing = [
            {"vendor_id": donor.vendor_id, "value": getattr(donor, field_name)}
            for donor in donors
            if str(getattr(donor, field_name)) != str(getattr(survivor, field_name))
        ]
        if differing:
            conflicts.append(
                {
                    "field": field_name,
                    "survivor_value": getattr(survivor, field_name),
                    "donor_values": differing,
                }
            )

    impact = {
        "donor_vendor_count": len(donors),
        "donor_vendor_ids": donor_ids,
        "contacts_to_reassign": VendorContact.objects.filter(vendor__vendor_id__in=donor_ids).count(),
        "identifiers_to_reassign": VendorIdentifier.objects.filter(vendor__vendor_id__in=donor_ids).count(),
        "offerings_to_reassign": Offering.objects.filter(vendor__vendor_id__in=donor_ids).count(),
        "contracts_to_reassign": Contract.objects.filter(vendor__vendor_id__in=donor_ids).count(),
        "notes_to_reassign": Vendor.objects.filter(vendor_id__in=donor_ids).aggregate(
            note_count=models.Count("vendor_notes"),
            warning_count=models.Count("vendor_warnings"),
            ticket_count=models.Count("vendor_tickets"),
            owner_count=models.Count("business_owners"),
            org_count=models.Count("org_assignments"),
            demo_count=models.Count("vendor_demos"),
        ),
    }
    return {"conflicts": conflicts, "impact": impact}


@csrf_exempt
@require_http_methods(["POST"])
def merge_vendors_preview_endpoint(request: HttpRequest) -> JsonResponse:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/vendors/merge/preview")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    try:
        survivor_vendor_id, merged_vendor_ids = _validate_merge_request(body)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        survivor = Vendor.objects.get(vendor_id=survivor_vendor_id)
    except Vendor.DoesNotExist:
        return JsonResponse({"error": f"survivor vendor {survivor_vendor_id} not found"}, status=404)

    donors = list(Vendor.objects.filter(vendor_id__in=merged_vendor_ids).order_by("vendor_id"))
    if len(donors) != len(merged_vendor_ids):
        found_ids = {donor.vendor_id for donor in donors}
        missing = [item for item in merged_vendor_ids if item not in found_ids]
        return JsonResponse({"error": "one or more donor vendors not found", "missing_vendor_ids": missing}, status=404)

    preview = _build_merge_preview(survivor, donors)
    return JsonResponse(
        {
            "survivor_vendor_id": survivor.vendor_id,
            "merged_vendor_ids": [donor.vendor_id for donor in donors],
            **preview,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def merge_vendors_execute_endpoint(request: HttpRequest) -> JsonResponse:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/vendors/merge/execute")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    try:
        survivor_vendor_id, merged_vendor_ids = _validate_merge_request(body)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        survivor = Vendor.objects.get(vendor_id=survivor_vendor_id)
    except Vendor.DoesNotExist:
        return JsonResponse({"error": f"survivor vendor {survivor_vendor_id} not found"}, status=404)

    donors = list(Vendor.objects.filter(vendor_id__in=merged_vendor_ids).order_by("vendor_id"))
    if len(donors) != len(merged_vendor_ids):
        found_ids = {donor.vendor_id for donor in donors}
        missing = [item for item in merged_vendor_ids if item not in found_ids]
        return JsonResponse({"error": "one or more donor vendors not found", "missing_vendor_ids": missing}, status=404)

    donor_ids = [donor.vendor_id for donor in donors]
    summary: dict[str, int | str | list[str]] = {
        "survivor_vendor_id": survivor.vendor_id,
        "merged_vendor_ids": donor_ids,
        "contacts_reassigned": 0,
        "identifiers_reassigned": 0,
        "identifiers_deduplicated": 0,
        "offerings_reassigned": 0,
        "contracts_reassigned": 0,
        "workflows_deleted": 0,
        "workflows_moved": 0,
        "donor_vendors_deleted": 0,
    }

    with transaction.atomic():
        summary["contacts_reassigned"] = VendorContact.objects.filter(vendor__vendor_id__in=donor_ids).update(vendor=survivor)

        donor_identifiers = VendorIdentifier.objects.filter(vendor__vendor_id__in=donor_ids)
        reassigned_count = 0
        deduplicated_count = 0
        for identifier in donor_identifiers.select_for_update():
            exists_on_survivor = VendorIdentifier.objects.filter(
                vendor=survivor,
                identifier_type=identifier.identifier_type,
                identifier_value=identifier.identifier_value,
            ).exists()
            if exists_on_survivor:
                identifier.delete()
                deduplicated_count += 1
            else:
                identifier.vendor = survivor
                identifier.save(update_fields=["vendor"])
                reassigned_count += 1
        summary["identifiers_reassigned"] = reassigned_count
        summary["identifiers_deduplicated"] = deduplicated_count

        summary["offerings_reassigned"] = Offering.objects.filter(vendor__vendor_id__in=donor_ids).update(vendor=survivor)
        summary["contracts_reassigned"] = Contract.objects.filter(vendor__vendor_id__in=donor_ids).update(vendor=survivor)
        VendorWarning.objects.filter(vendor__vendor_id__in=donor_ids).update(vendor=survivor)
        Vendor.objects.filter(vendor_id__in=donor_ids).update(owner_org_id=survivor.owner_org_id)

        VendorNote.objects.filter(vendor__vendor_id__in=donor_ids).update(vendor=survivor)
        VendorTicket.objects.filter(vendor__vendor_id__in=donor_ids).update(vendor=survivor)
        VendorDemo.objects.filter(vendor__vendor_id__in=donor_ids).update(vendor=survivor)
        VendorBusinessOwner.objects.filter(vendor__vendor_id__in=donor_ids).update(vendor=survivor)
        VendorOrgAssignment.objects.filter(vendor__vendor_id__in=donor_ids).update(vendor=survivor)

        for donor in donors:
            donor_workflow = OnboardingWorkflow.objects.filter(vendor=donor).first()
            if donor_workflow is None:
                continue
            survivor_has_workflow = OnboardingWorkflow.objects.filter(vendor=survivor).exists()
            if survivor_has_workflow:
                donor_workflow.delete()
                summary["workflows_deleted"] = int(summary["workflows_deleted"]) + 1
            else:
                donor_workflow.vendor = survivor
                donor_workflow.save(update_fields=["vendor"])
                summary["workflows_moved"] = int(summary["workflows_moved"]) + 1

        deleted_count, _ = Vendor.objects.filter(vendor_id__in=donor_ids).delete()
        summary["donor_vendors_deleted"] = deleted_count

    return JsonResponse(summary)


@require_http_methods(["GET"])
def index(request: HttpRequest) -> HttpResponse:
    items = [
        _serialize_vendor(record)
        for record in Vendor.objects.all().order_by("vendor_id")[:50]  # type: ignore[attr-defined]
    ]
    return render(
        request,
        "vendors/index.html",
        {
            "page_title": "Vendor 360",
            "section_name": "Vendor 360",
            "items": items,
        },
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def vendor_collection_endpoint(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        items = [
            _serialize_vendor(record)
            for record in Vendor.objects.all().order_by("vendor_id")  # type: ignore[attr-defined]
        ]
        return JsonResponse({"items": items})

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/vendors")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    vendor_id = str(body.get("vendor_id", "")).strip()
    legal_name = str(body.get("legal_name", "")).strip() or vendor_id
    display_name = str(body.get("display_name", "")).strip() or legal_name
    lifecycle_state = str(body.get("lifecycle_state", "active")).strip() or "active"
    owner_org_id = str(body.get("owner_org_id", "default-org")).strip() or "default-org"
    risk_tier = str(body.get("risk_tier", "medium")).strip() or "medium"

    if not vendor_id:
        return JsonResponse({"error": "vendor_id is required"}, status=400)

    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, owner_org_id, minimum_level="edit"):
        return JsonResponse(
            {
                "error": "forbidden",
                "reason": f"scoped user is missing edit scope for owner_org_id={owner_org_id}",
            },
            status=403,
        )
    try:
        lifecycle_state = _normalize_lifecycle(lifecycle_state)
        risk_tier = _normalize_risk_tier(risk_tier)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if Vendor.objects.filter(vendor_id=vendor_id).exists():  # type: ignore[attr-defined]
        return JsonResponse({"error": f"vendor {vendor_id} already exists"}, status=409)

    try:
        record = Vendor.objects.create(
            vendor_id=vendor_id,
            legal_name=legal_name,
            display_name=display_name,
            lifecycle_state=lifecycle_state,
            owner_org_id=owner_org_id,
            risk_tier=risk_tier,
        )  # type: ignore[attr-defined]
    except IntegrityError:
        return JsonResponse({"error": f"vendor {vendor_id} already exists"}, status=409)

    return JsonResponse(_serialize_vendor(record), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def update_vendor_endpoint(request: HttpRequest, vendor_id: str) -> JsonResponse:
    try:
        record = Vendor.objects.get(vendor_id=vendor_id)  # type: ignore[attr-defined]
    except Vendor.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"vendor {vendor_id} not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(_serialize_vendor(record))

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "PATCH", "/api/v1/vendors/{vendor_id}")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    if is_scope_restricted(snapshot):
        offering_lobs = list(
            Offering.objects.filter(vendor=record)  # type: ignore[attr-defined]
            .exclude(lob="")
            .values_list("lob", flat=True)
            .distinct()
        )
        if not has_vendor_level_scope(
            snapshot,
            owner_org_id=record.owner_org_id,
            offering_lobs=offering_lobs,
            minimum_level="edit",
        ):
            return JsonResponse(
                {
                    "error": "forbidden",
                    "reason": "scoped user is missing edit scope for one or more vendor LOBs",
                },
                status=403,
            )

    body = json.loads(request.body.decode("utf-8") or "{}")
    updated = False
    for field_name in ["legal_name", "display_name", "lifecycle_state", "owner_org_id", "risk_tier"]:
        if field_name in body:
            value = str(body[field_name]).strip()
            if field_name == "lifecycle_state":
                try:
                    value = _normalize_lifecycle(value)
                except ValueError as exc:
                    return JsonResponse({"error": str(exc)}, status=400)
            if field_name == "risk_tier":
                try:
                    value = _normalize_risk_tier(value)
                except ValueError as exc:
                    return JsonResponse({"error": str(exc)}, status=400)
            setattr(record, field_name, value)
            updated = True

    if updated:
        record.save()
    return JsonResponse(_serialize_vendor(record))


# ===== HTML Pages (UI Views) =====

# Category mapping for vendor organization
VENDOR_CATEGORY_MAP = {
    "ORG-123": "Enterprise",
    "TEST-ORG": "Communication",
    "default-org": "Enterprise",
}

def _get_vendor_category(owner_org_id: str) -> str:
    """Get business category for a vendor based on their org ID."""
    return VENDOR_CATEGORY_MAP.get(owner_org_id, "Enterprise")


@require_http_methods(["GET"])
def vendor_list_page(request: HttpRequest) -> HttpResponse:
    """Render vendor list page with split-view sidebar and detail panel."""
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    can_create_vendor = authorize_mutation(snapshot, "POST", "/api/v1/vendors").allowed

    queryset = Vendor.objects.prefetch_related('offerings').all().order_by("display_name")
    
    # Apply filters if provided
    search_query = request.GET.get("q", "").strip()
    if search_query:
        queryset = queryset.filter(
            models.Q(vendor_id__icontains=search_query) |
            models.Q(display_name__icontains=search_query) |
            models.Q(legal_name__icontains=search_query)
        )
    
    status = request.GET.get("status", "").strip()
    if status and status in LIFECYCLE_STATES:
        queryset = queryset.filter(lifecycle_state=status)
    
    risk = request.GET.get("risk", "").strip()
    if risk and risk in RISK_TIERS:
        queryset = queryset.filter(risk_tier=risk)
    
    # Annotate vendors with categories for grouping
    vendors_with_categories = []
    for vendor in queryset:
        vendor.category = _get_vendor_category(vendor.owner_org_id)
        vendors_with_categories.append(vendor)
    
    # Sort by category first, then display name
    vendors_with_categories.sort(key=lambda v: (v.category, v.display_name))
    
    # Return all vendors for split-view (no pagination)
    return render(
        request,
        "vendors/index.html",
        {
            "items": vendors_with_categories,
            "search_query": search_query,
            "can_create_vendor": can_create_vendor,
        },
    )


@require_http_methods(["GET"])
def vendor_detail_page(request: HttpRequest, vendor_id: str) -> HttpResponse:
    """Render vendor detail page."""
    from datetime import datetime
    
    vendor = get_object_or_404(Vendor, vendor_id=vendor_id)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)

    vendor_offering_lobs = list(
        Offering.objects.filter(vendor=vendor)  # type: ignore[attr-defined]
        .exclude(lob="")
        .values_list("lob", flat=True)
        .distinct()
    )
    has_vendor_edit_scope = not is_scope_restricted(snapshot) or has_vendor_level_scope(
        snapshot,
        owner_org_id=vendor.owner_org_id,
        offering_lobs=vendor_offering_lobs,
        minimum_level="edit",
    )

    can_edit_vendor = has_vendor_edit_scope and authorize_mutation(
        snapshot,
        "PATCH",
        "/api/v1/vendors/{vendor_id}",
    ).allowed
    can_manage_vendor_contacts = has_vendor_edit_scope and authorize_mutation(
        snapshot,
        "POST",
        "/api/v1/vendors/{vendor_id}/contacts",
    ).allowed
    can_manage_vendor_identifiers = has_vendor_edit_scope and authorize_mutation(
        snapshot,
        "POST",
        "/api/v1/vendors/{vendor_id}/identifiers",
    ).allowed
    can_manage_vendor_offerings = has_vendor_edit_scope and authorize_mutation(
        snapshot,
        "POST",
        "/api/v1/vendors/{vendor_id}/offerings",
    ).allowed
    can_manage_vendor_contracts = has_vendor_edit_scope and authorize_mutation(
        snapshot,
        "POST",
        "/api/v1/vendors/{vendor_id}/contracts",
    ).allowed
    contracts_visible = can_view_contracts(snapshot)
    
    # Get related contracts (Project model has no vendor relationship)
    vendor_contracts = Contract.objects.filter(vendor=vendor).order_by("-created_at")
    
    # Calculate contract statistics
    from django.db.models import Sum, Count, Q
    from decimal import Decimal
    
    contract_stats = vendor_contracts.aggregate(
        total_contracts=Count("id"),
        active_contracts=Count("id", filter=Q(contract_status="active")),
        total_value=Sum("annual_value"),
        cancelled_count=Count("id", filter=Q(cancelled_flag=True))
    )
    
    # Get recent contracts (last 5) with expiry calculations
    recent_contracts_list = []
    today = datetime.now().date()
    expiring_contracts_list = []
    
    for contract in vendor_contracts[:5]:
        contract_dict = {
            "contract_id": contract.contract_id,
            "contract_number": contract.contract_number,
            "offering_id": contract.offering_id,
            "contract_status": contract.contract_status,
            "start_date": contract.start_date,
            "end_date": contract.end_date,
            "annual_value": contract.annual_value,
            "cancelled_flag": contract.cancelled_flag,
        }
        
        # Calculate days until expiry
        if contract.end_date:
            days_until_expiry = (contract.end_date - today).days
            contract_dict["days_until_expiry"] = days_until_expiry
            
            # Calculate contract term in months
            if contract.start_date and contract.end_date:
                months = (contract.end_date.year - contract.start_date.year) * 12 + \
                        (contract.end_date.month - contract.start_date.month)
                contract_dict["contract_months"] = max(months, 1)
        
        recent_contracts_list.append(contract_dict)

    # Track expiring contracts (within 60 days) across all contracts
    for contract in vendor_contracts:
        if not contract.end_date or contract.cancelled_flag:
            continue
        days_until_expiry = (contract.end_date - today).days
        if 0 < days_until_expiry <= 60:
            expiring_contracts_list.append(
                {
                    "contract_id": contract.contract_id,
                    "contract_number": contract.contract_number,
                    "end_date": contract.end_date,
                    "days_until_expiry": days_until_expiry,
                }
            )
    
    # Contract value by status
    contracts_by_status = list(
        vendor_contracts.values("contract_status")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    
    # Get key contacts (primary + active first)
    key_contacts = VendorContact.objects.filter(
        vendor=vendor,
        is_active=True,
    ).order_by(
        '-is_primary',  # Primary contacts first
        'full_name'
    )[:4]
    
    key_contacts_data = [
        {
            "full_name": contact.full_name,
            "email": contact.email,
            "phone": contact.phone,
            "title": contact.title,
            "contact_type": contact.contact_type,
            "is_primary": contact.is_primary,
            "is_active": contact.is_active,
        }
        for contact in key_contacts
    ]
    
    context = {
        "vendor": vendor,
        "vendor_contracts": recent_contracts_list,
        "all_contracts_count": vendor_contracts.count(),
        "expiring_contracts": expiring_contracts_list,
        "key_contacts": key_contacts_data,
        "total_contracts": contract_stats["total_contracts"] or 0,
        "active_contracts": contract_stats["active_contracts"] or 0,
        "cancelled_contracts": contract_stats["cancelled_count"] or 0,
        "total_contract_value": contract_stats["total_value"] or Decimal("0"),
        "contracts_by_status": contracts_by_status,
        "contracts_visible": contracts_visible,
        "can_edit_vendor": can_edit_vendor,
        "can_manage_vendor_contacts": can_manage_vendor_contacts,
        "can_manage_vendor_identifiers": can_manage_vendor_identifiers,
        "can_manage_vendor_offerings": can_manage_vendor_offerings,
        "can_manage_vendor_contracts": can_manage_vendor_contracts,
    }
    
    return render(request, "vendors/detail.html", context)


@require_http_methods(["GET"])
def vendor_detail_api(request: HttpRequest, vendor_id: str) -> JsonResponse:
    """Return vendor details as JSON for AJAX loading."""
    from datetime import datetime

    vendor = get_object_or_404(Vendor, vendor_id=vendor_id)
    today = datetime.now().date()

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    contracts_visible = can_view_contracts(snapshot)

    vendor_offering_lobs = list(
        Offering.objects.filter(vendor=vendor)  # type: ignore[attr-defined]
        .exclude(lob="")
        .values_list("lob", flat=True)
        .distinct()
    )
    has_vendor_edit_scope = not is_scope_restricted(snapshot) or has_vendor_level_scope(
        snapshot,
        owner_org_id=vendor.owner_org_id,
        offering_lobs=vendor_offering_lobs,
        minimum_level="edit",
    )
    can_edit_vendor = has_vendor_edit_scope and authorize_mutation(
        snapshot,
        "PATCH",
        "/api/v1/vendors/{vendor_id}",
    ).allowed
    can_manage_vendor_contacts = has_vendor_edit_scope and authorize_mutation(
        snapshot,
        "POST",
        "/api/v1/vendors/{vendor_id}/contacts",
    ).allowed
    can_manage_vendor_identifiers = has_vendor_edit_scope and authorize_mutation(
        snapshot,
        "POST",
        "/api/v1/vendors/{vendor_id}/identifiers",
    ).allowed
    can_manage_vendor_offerings = has_vendor_edit_scope and authorize_mutation(
        snapshot,
        "POST",
        "/api/v1/vendors/{vendor_id}/offerings",
    ).allowed
    can_manage_vendor_contracts = contracts_visible and has_vendor_edit_scope and authorize_mutation(
        snapshot,
        "POST",
        "/api/v1/vendors/{vendor_id}/contracts",
    ).allowed
    
    # Get related contracts
    vendor_contracts = Contract.objects.filter(vendor=vendor).order_by("-created_at") if contracts_visible else Contract.objects.none()
    
    # Calculate contract statistics
    from django.db.models import Sum, Count, Q
    from decimal import Decimal
    
    contract_stats = vendor_contracts.aggregate(
        total_contracts=Count("id"),
        active_contracts=Count("id", filter=Q(contract_status="active")),
        total_value=Sum("annual_value"),
        cancelled_count=Count("id", filter=Q(cancelled_flag=True))
    )
    
    # Get recent contracts (last 5)
    recent_contracts = vendor_contracts[:5]

    # Compute expiring contracts and contract detail enrichments
    expiring_contracts = []
    recent_contracts_payload = []
    for contract in recent_contracts:
        days_until_expiry = None
        contract_months = None
        if contract.end_date:
            days_until_expiry = (contract.end_date - today).days
        if contract.start_date and contract.end_date:
            month_delta = (contract.end_date.year - contract.start_date.year) * 12 + (contract.end_date.month - contract.start_date.month)
            contract_months = max(month_delta, 1)

        if days_until_expiry is not None and 0 < days_until_expiry <= 60 and not contract.cancelled_flag:
            expiring_contracts.append(
                {
                    "contract_id": contract.contract_id,
                    "contract_number": contract.contract_number or "",
                    "end_date": contract.end_date.isoformat() if contract.end_date else None,
                    "days_until_expiry": days_until_expiry,
                }
            )

        recent_contracts_payload.append(
            {
                "contract_id": contract.contract_id,
                "contract_number": contract.contract_number or "",
                "offering_id": contract.offering_id or "",
                "contract_status": contract.contract_status,
                "cancelled_flag": contract.cancelled_flag,
                "start_date": contract.start_date.isoformat() if contract.start_date else None,
                "end_date": contract.end_date.isoformat() if contract.end_date else None,
                "days_until_expiry": days_until_expiry,
                "contract_months": contract_months,
                "annual_value": float(contract.annual_value) if contract.annual_value else 0,
            }
        )

    key_contacts = VendorContact.objects.filter(vendor=vendor, is_active=True).order_by("-is_primary", "full_name")[:4]
    key_contacts_payload = [
        {
            "id": contact.id,
            "full_name": contact.full_name,
            "contact_type": contact.contact_type,
            "email": contact.email or "",
            "phone": contact.phone or "",
            "title": contact.title or "",
            "is_primary": contact.is_primary,
        }
        for contact in key_contacts
    ]

    identifiers = VendorIdentifier.objects.filter(vendor=vendor).order_by("-is_primary", "identifier_type")
    identifiers_payload = [
        {
            "id": identifier.id,
            "identifier_type": identifier.identifier_type,
            "identifier_value": identifier.identifier_value,
            "is_primary": identifier.is_primary,
            "is_verified": identifier.is_verified,
        }
        for identifier in identifiers[:4]
    ]

    workflow = OnboardingWorkflow.objects.filter(vendor=vendor).first()
    active_warning_count = VendorWarning.objects.filter(vendor=vendor, status="active").count()
    
    # Serialize data
    data = {
        "vendor": {
            "vendor_id": vendor.vendor_id,
            "legal_name": vendor.legal_name,
            "display_name": vendor.display_name,
            "lifecycle_state": vendor.lifecycle_state,
            "owner_org_id": vendor.owner_org_id,
            "risk_tier": vendor.risk_tier,
            "created_at": vendor.created_at.isoformat(),
            "updated_at": vendor.updated_at.isoformat(),
        },
        "stats": {
            "total_contracts": contract_stats["total_contracts"] or 0,
            "active_contracts": contract_stats["active_contracts"] or 0,
            "cancelled_contracts": contract_stats["cancelled_count"] or 0,
            "total_contract_value": float(contract_stats["total_value"] or Decimal("0")),
        },
        "contracts": recent_contracts_payload,
        "all_contracts_count": vendor_contracts.count(),
        "expiring_contracts": expiring_contracts,
        "key_contacts": key_contacts_payload,
        "identifiers": identifiers_payload,
        "contact_summary": {
            "total": VendorContact.objects.filter(vendor=vendor).count(),
            "active": VendorContact.objects.filter(vendor=vendor, is_active=True).count(),
        },
        "identifier_summary": {
            "total": identifiers.count(),
            "verified": identifiers.filter(is_verified=True).count(),
        },
        "workflow": {
            "exists": workflow is not None,
            "current_state": workflow.current_state if workflow else "draft",
            "days_in_state": workflow.get_days_in_state() if workflow else 0,
        },
        "warnings": {
            "active_count": active_warning_count,
        },
        "permissions": {
            "contracts_visible": contracts_visible,
            "can_edit_vendor": can_edit_vendor,
            "can_manage_vendor_contacts": can_manage_vendor_contacts,
            "can_manage_vendor_identifiers": can_manage_vendor_identifiers,
            "can_manage_vendor_offerings": can_manage_vendor_offerings,
            "can_manage_vendor_contracts": can_manage_vendor_contracts,
        },
    }
    
    return JsonResponse(data)


@require_http_methods(["GET", "POST"])
def vendor_form_page(request: HttpRequest, vendor_id: str | None = None) -> HttpResponse:
    """Render vendor form page (create or edit)."""
    vendor = None
    form_errors = {}
    
    if vendor_id:
        vendor = get_object_or_404(Vendor, vendor_id=vendor_id)
    
    if request.method == "POST":
        # Check permissions
        identity = resolve_identity_context(request)
        sync_user_directory(identity)
        snapshot = build_policy_snapshot(identity)
        decision = authorize_mutation(snapshot, "POST" if not vendor else "PATCH", "/api/v1/vendors")
        if not decision.allowed:
            messages.error(request, f"Permission denied: {decision.reason}")
            if vendor:
                return redirect(f"/vendor-360/{vendor.vendor_id}")
            return redirect("/vendor-360")
        
        # Extract form data
        vendor_id_val = request.POST.get("vendor_id", "").strip()
        legal_name = request.POST.get("legal_name", "").strip()
        display_name = request.POST.get("display_name", "").strip()
        owner_org_id = request.POST.get("owner_org_id", "").strip()
        lifecycle_state = request.POST.get("lifecycle_state", "").strip()
        risk_tier = request.POST.get("risk_tier", "").strip()
        
        # Validation
        if not vendor_id_val:
            form_errors["vendor_id"] = ["Vendor ID is required"]
        if not legal_name:
            form_errors["legal_name"] = ["Legal name is required"]
        if not display_name:
            form_errors["display_name"] = ["Display name is required"]
        if not owner_org_id:
            form_errors["owner_org_id"] = ["Owner organization is required"]
        
        try:
            lifecycle_state = _normalize_lifecycle(lifecycle_state)
        except ValueError as e:
            form_errors["lifecycle_state"] = [str(e)]
        
        try:
            risk_tier = _normalize_risk_tier(risk_tier)
        except ValueError as e:
            form_errors["risk_tier"] = [str(e)]
        
        if form_errors:
            return render(
                request,
                "vendors/form.html",
                {
                    "vendor": vendor,
                    "form_errors": form_errors,
                },
            )
        
        # Create or update
        if vendor:
            # Update existing
            vendor.legal_name = legal_name
            vendor.display_name = display_name
            vendor.owner_org_id = owner_org_id
            vendor.lifecycle_state = lifecycle_state
            vendor.risk_tier = risk_tier
            vendor.save()
            messages.success(request, f"Vendor {vendor.vendor_id} updated successfully")
            return redirect(f"/vendor-360/{vendor.vendor_id}")
        else:
            # Create new
            if Vendor.objects.filter(vendor_id=vendor_id_val).exists():
                form_errors["vendor_id"] = ["Vendor ID already exists"]
                return render(
                    request,
                    "vendors/form.html",
                    {
                        "vendor": None,
                        "form_errors": form_errors,
                    },
                )
            
            try:
                vendor = Vendor.objects.create(
                    vendor_id=vendor_id_val,
                    legal_name=legal_name,
                    display_name=display_name,
                    owner_org_id=owner_org_id,
                    lifecycle_state=lifecycle_state,
                    risk_tier=risk_tier,
                )
                messages.success(request, f"Vendor {vendor_id_val} created successfully")
                return redirect(f"/vendor-360/{vendor.vendor_id}")
            except IntegrityError:
                form_errors["vendor_id"] = ["Vendor ID already exists"]
                return render(
                    request,
                    "vendors/form.html",
                    {
                        "vendor": None,
                        "form_errors": form_errors,
                    },
                )
    
    return render(
        request,
        "vendors/form.html",
        {
            "vendor": vendor,
            "form_errors": form_errors,
        },
    )


# ===== Vendor Contacts API =====

@csrf_exempt
@require_http_methods(["GET", "POST"])
def vendor_contacts_endpoint(request: HttpRequest, vendor_id: str) -> JsonResponse:
    """Get or create contacts for a vendor."""
    try:
        vendor = Vendor.objects.get(vendor_id=vendor_id)
    except Vendor.DoesNotExist:
        return JsonResponse({"error": f"vendor {vendor_id} not found"}, status=404)

    if request.method == "GET":
        contacts = vendor.contacts.all()
        serializer = VendorContactSerializer(contacts, many=True)
        return JsonResponse({"contacts": serializer.data})

    # POST: Create new contact
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/vendors/{vendor_id}/contacts")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    payload, payload_error = _resolve_contact_payload(body)
    if payload_error:
        return JsonResponse({"error": payload_error}, status=400)
    payload = {**payload, "vendor": vendor.id}
    serializer = VendorContactSerializer(data=payload)
    
    if serializer.is_valid():
        contact = serializer.save()
        return JsonResponse(VendorContactSerializer(contact).data, status=201)
    
    return JsonResponse(serializer.errors, status=400)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
def vendor_contact_detail_endpoint(
    request: HttpRequest, vendor_id: str, contact_id: int
) -> JsonResponse:
    """Get, update, or delete a specific contact."""
    try:
        vendor = Vendor.objects.get(vendor_id=vendor_id)
        contact = vendor.contacts.get(id=contact_id)
    except Vendor.DoesNotExist:
        return JsonResponse({"error": f"vendor {vendor_id} not found"}, status=404)
    except VendorContact.DoesNotExist:
        return JsonResponse({"error": f"contact {contact_id} not found"}, status=404)

    if request.method == "GET":
        serializer = VendorContactSerializer(contact)
        return JsonResponse(serializer.data)

    # PATCH/DELETE require authorization
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(
        snapshot, request.method, "/api/v1/vendors/{vendor_id}/contacts/{contact_id}"
    )
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    if request.method == "PATCH":
        body = json.loads(request.body.decode("utf-8") or "{}")
        serializer = VendorContactSerializer(contact, data=body, partial=True)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data)
        return JsonResponse(serializer.errors, status=400)

    if request.method == "DELETE":
        contact.delete()
        return JsonResponse({"status": "deleted"}, status=204)


# ===== Vendor Identifiers API =====

@csrf_exempt
@require_http_methods(["GET", "POST"])
def vendor_identifiers_endpoint(request: HttpRequest, vendor_id: str) -> JsonResponse:
    """Get or create identifiers for a vendor."""
    try:
        vendor = Vendor.objects.get(vendor_id=vendor_id)
    except Vendor.DoesNotExist:
        return JsonResponse({"error": f"vendor {vendor_id} not found"}, status=404)

    if request.method == "GET":
        identifiers = vendor.identifiers.all()
        serializer = VendorIdentifierSerializer(identifiers, many=True)
        return JsonResponse({"identifiers": serializer.data})

    # POST: Create new identifier
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/vendors/{vendor_id}/identifiers")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    serializer = VendorIdentifierSerializer(data=body)
    
    if serializer.is_valid():
        # Set vendor on the identifier
        serializer.validated_data["vendor"] = vendor
        identifier = serializer.save()
        return JsonResponse(VendorIdentifierSerializer(identifier).data, status=201)
    
    return JsonResponse(serializer.errors, status=400)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
def vendor_identifier_detail_endpoint(
    request: HttpRequest, vendor_id: str, identifier_id: int
) -> JsonResponse:
    """Get, update, or delete a specific identifier."""
    try:
        vendor = Vendor.objects.get(vendor_id=vendor_id)
        identifier = vendor.identifiers.get(id=identifier_id)
    except Vendor.DoesNotExist:
        return JsonResponse({"error": f"vendor {vendor_id} not found"}, status=404)
    except VendorIdentifier.DoesNotExist:
        return JsonResponse({"error": f"identifier {identifier_id} not found"}, status=404)

    if request.method == "GET":
        serializer = VendorIdentifierSerializer(identifier)
        return JsonResponse(serializer.data)

    # PATCH/DELETE require authorization
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(
        snapshot, request.method, "/api/v1/vendors/{vendor_id}/identifiers/{identifier_id}"
    )
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    if request.method == "PATCH":
        body = json.loads(request.body.decode("utf-8") or "{}")
        serializer = VendorIdentifierSerializer(identifier, data=body, partial=True)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data)
        return JsonResponse(serializer.errors, status=400)

    if request.method == "DELETE":
        identifier.delete()
        return JsonResponse({"status": "deleted"}, status=204)


# ============================================================================
# HTML Pages: Vendor Contacts
# ============================================================================

@require_http_methods(["GET"])
def vendor_contact_list_page(request: HttpRequest, vendor_id: str) -> HttpResponse:
    """Render vendor contacts list page."""
    vendor = get_object_or_404(Vendor, vendor_id=vendor_id)
    contacts = VendorContact.objects.filter(vendor=vendor).order_by('-is_primary', 'full_name')
    
    # Calculate summary stats
    active_count = contacts.filter(is_active=True).count()
    primary_contact = contacts.filter(is_primary=True).first()
    email_count = contacts.exclude(email__isnull=True).exclude(email='').count()
    
    return render(
        request,
        "vendors/contact_list.html",
        {
            "vendor": vendor,
            "contacts": contacts,
            "active_count": active_count,
            "primary_contact": primary_contact,
            "email_count": email_count,
        },
    )


@require_http_methods(["GET", "POST"])
def vendor_contact_form_page(request: HttpRequest, vendor_id: str, contact_id: int | None = None) -> HttpResponse:
    """Render vendor contact form page (create or edit)."""
    from apps.vendors.forms import VendorContactForm
    
    vendor = get_object_or_404(Vendor, vendor_id=vendor_id)
    contact = None
    
    if contact_id:
        contact = get_object_or_404(VendorContact, id=contact_id, vendor=vendor)
    
    if request.method == "POST":
        form = VendorContactForm(request.POST, instance=contact, vendor=vendor)
        if form.is_valid():
            contact = form.save()
            action = "updated" if contact_id else "created"
            messages.success(request, f"Contact '{contact.full_name}' has been {action} successfully.")
            return redirect("vendor_contact_list", vendor_id=vendor_id)
    else:
        form = VendorContactForm(instance=contact, vendor=vendor)
    
    return render(
        request,
        "vendors/contact_form.html",
        {
            "vendor": vendor,
            "form": form,
        },
    )


@require_http_methods(["GET", "POST"])
def vendor_contact_delete_page(request: HttpRequest, vendor_id: str, contact_id: int) -> HttpResponse:
    """Render vendor contact delete confirmation page."""
    vendor = get_object_or_404(Vendor, vendor_id=vendor_id)
    contact = get_object_or_404(VendorContact, id=contact_id, vendor=vendor)
    
    if request.method == "POST":
        contact_name = contact.full_name
        contact.delete()
        messages.success(request, f"Contact '{contact_name}' has been deleted.")
        return redirect("vendor_contact_list", vendor_id=vendor_id)
    
    return render(
        request,
        "vendors/contact_confirm_delete.html",
        {
            "vendor": vendor,
            "contact": contact,
        },
    )


# ============================================================================
# HTML Pages: Vendor Identifiers
# ============================================================================

@require_http_methods(["GET"])
def vendor_identifier_list_page(request: HttpRequest, vendor_id: str) -> HttpResponse:
    """Render vendor identifiers list page."""
    vendor = get_object_or_404(Vendor, vendor_id=vendor_id)
    identifiers = VendorIdentifier.objects.filter(vendor=vendor).order_by('-is_primary', 'identifier_type')
    
    # Calculate summary stats
    verified_count = identifiers.filter(is_verified=True).count()
    unverified_count = identifiers.filter(is_verified=False).count()
    primary_identifier = identifiers.filter(is_primary=True).first()
    
    return render(
        request,
        "vendors/identifier_list.html",
        {
            "vendor": vendor,
            "identifiers": identifiers,
            "verified_count": verified_count,
            "unverified_count": unverified_count,
            "primary_identifier": primary_identifier,
        },
    )


@require_http_methods(["GET", "POST"])
def vendor_identifier_form_page(request: HttpRequest, vendor_id: str, identifier_id: int | None = None) -> HttpResponse:
    """Render vendor identifier form page (create or edit)."""
    from apps.vendors.forms import VendorIdentifierForm
    
    vendor = get_object_or_404(Vendor, vendor_id=vendor_id)
    identifier = None
    
    if identifier_id:
        identifier = get_object_or_404(VendorIdentifier, id=identifier_id, vendor=vendor)
    
    if request.method == "POST":
        form = VendorIdentifierForm(request.POST, instance=identifier, vendor=vendor)
        if form.is_valid():
            identifier = form.save()
            action = "updated" if identifier_id else "created"
            messages.success(
                request,
                f"Identifier '{identifier.get_identifier_type_display()}' has been {action} successfully."
            )
            return redirect("vendor_identifier_list", vendor_id=vendor_id)
    else:
        form = VendorIdentifierForm(instance=identifier, vendor=vendor)
    
    return render(
        request,
        "vendors/identifier_form.html",
        {
            "vendor": vendor,
            "form": form,
        },
    )


@require_http_methods(["GET", "POST"])
def vendor_identifier_delete_page(request: HttpRequest, vendor_id: str, identifier_id: int) -> HttpResponse:
    """Render vendor identifier delete confirmation page."""
    vendor = get_object_or_404(Vendor, vendor_id=vendor_id)
    identifier = get_object_or_404(VendorIdentifier, id=identifier_id, vendor=vendor)
    
    if request.method == "POST":
        identifier_type = identifier.get_identifier_type_display()
        identifier.delete()
        messages.success(request, f"Identifier '{identifier_type}' has been deleted.")
        return redirect("vendor_identifier_list", vendor_id=vendor_id)
    
    return render(
        request,
        "vendors/identifier_confirm_delete.html",
        {
            "vendor": vendor,
            "identifier": identifier,
        },
    )


# ============================================================================
# API: Workflow State Machine
# ============================================================================

@csrf_exempt
@require_http_methods(["GET", "POST"])
def onboarding_workflow_endpoint(request: HttpRequest, vendor_id: str) -> JsonResponse:
    """
    Get or create/transition vendor onboarding workflow.

    GET: Returns current workflow state and available transitions
    POST: Performs a state transition with the provided action
    """
    try:
        vendor = Vendor.objects.get(vendor_id=vendor_id)
    except Vendor.DoesNotExist:
        return JsonResponse({"error": f"vendor {vendor_id} not found"}, status=404)

    if request.method == "GET":
        # Get or create workflow
        workflow, created = OnboardingWorkflow.objects.get_or_create(vendor=vendor)
        serializer = OnboardingWorkflowSerializer(workflow)
        return JsonResponse(serializer.data)

    # POST: State transition
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/vendors/{vendor_id}/workflow")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    state_change_serializer = OnboardingWorkflowStateChangeSerializer(data=body)

    if not state_change_serializer.is_valid():
        return JsonResponse(state_change_serializer.errors, status=400)

    # Get or create workflow
    workflow, _ = OnboardingWorkflow.objects.get_or_create(vendor=vendor)

    # Validate the transition is possible
    action = state_change_serializer.validated_data["action"]
    if action not in workflow.get_next_states():
        available = ", ".join(workflow.get_next_states().keys())
        return JsonResponse(
            {
                "error": "invalid_transition",
                "message": f"Cannot transition to '{action}' from state '{workflow.current_state}'",
                "available_transitions": available,
            },
            status=400,
        )

    # Execute the state transition
    try:
        if action == "request_information":
            workflow.request_information(
                reason=state_change_serializer.validated_data.get("reason"),
                notes=state_change_serializer.validated_data.get("notes"),
            )
        elif action == "mark_information_received":
            workflow.mark_information_received()

        elif action == "assign_for_review":
            reviewer = state_change_serializer.validated_data.get("reviewer")
            if not reviewer:
                return JsonResponse(
                    {"error": "reviewer is required for assign_for_review"},
                    status=400,
                )
            workflow.assign_for_review(
                reviewer=reviewer,
                reason=state_change_serializer.validated_data.get("reason"),
                notes=state_change_serializer.validated_data.get("notes"),
            )

        elif action == "approve_vendor":
            reviewer = state_change_serializer.validated_data.get("reviewer")
            if not reviewer:
                return JsonResponse(
                    {"error": "reviewer is required for approve_vendor"},
                    status=400,
                )
            workflow.approve_vendor(
                reviewer=reviewer,
                notes=state_change_serializer.validated_data.get("notes"),
            )

        elif action == "reject_vendor":
            reviewer = state_change_serializer.validated_data.get("reviewer")
            if not reviewer:
                return JsonResponse(
                    {"error": "reviewer is required for reject_vendor"},
                    status=400,
                )
            workflow.reject_vendor(
                reviewer=reviewer,
                notes=state_change_serializer.validated_data.get("notes"),
            )

        elif action == "activate_vendor":
            workflow.activate_vendor(
                notes=state_change_serializer.validated_data.get("notes"),
            )

        elif action == "archive_workflow":
            workflow.archive_workflow(
                notes=state_change_serializer.validated_data.get("notes"),
            )

        elif action == "reopen_draft":
            workflow.reopen_draft(
                notes=state_change_serializer.validated_data.get("notes"),
            )

    except Exception as exc:
        return JsonResponse(
            {
                "error": "transition_failed",
                "message": str(exc),
            },
            status=400,
        )

    # Return updated workflow
    serializer = OnboardingWorkflowSerializer(workflow)
    return JsonResponse(serializer.data, status=200)


@csrf_exempt
@require_http_methods(["GET"])
def onboarding_workflow_detail_endpoint(request: HttpRequest, vendor_id: str) -> JsonResponse:
    """Get workflow status and timeline for a vendor."""
    try:
        vendor = Vendor.objects.get(vendor_id=vendor_id)
    except Vendor.DoesNotExist:
        return JsonResponse({"error": f"vendor {vendor_id} not found"}, status=404)

    try:
        workflow = OnboardingWorkflow.objects.get(vendor=vendor)
    except OnboardingWorkflow.DoesNotExist:
        return JsonResponse({"error": f"workflow not found for vendor {vendor_id}"}, status=404)

    serializer = OnboardingWorkflowSerializer(workflow)
    return JsonResponse(serializer.data)


# ============================================================================
# DRF REST API ViewSets - Comprehensive API Layer
# ============================================================================

from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from apps.vendors.models import (
    VendorNote,
    VendorWarning,
    VendorTicket,
    OfferingNote,
    OfferingTicket,
    ContractEvent,
    VendorDemo,
    DemoScore,
    DemoNote,
    VendorBusinessOwner,
    VendorOrgAssignment,
)
from apps.vendors.serializers import (
    VendorNoteSerializer,
    VendorWarningSerializer,
    VendorTicketSerializer,
    OfferingNoteSerializer,
    OfferingTicketSerializer,
    ContractEventSerializer,
    VendorDemoSerializer,
    DemoScoreSerializer,
    DemoNoteSerializer,
    VendorBusinessOwnerSerializer,
    VendorOrgAssignmentSerializer,
    VendorDetailedSerializer,
    VendorListSerializer,
    VendorCreateUpdateSerializer,
)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for API responses."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class VendorAPIViewSet(viewsets.ModelViewSet):
    """
    API ViewSet for Vendor management (REST framework version).
    
    Features:
    - List, create, retrieve, update, delete vendors
    - Filter by lifecycle_state, risk_tier, owner_org_id
    - Search by vendor_id, legal_name, display_name
    - Nested routes for contacts, identifiers, notes, warnings, tickets
    - Summary statistics
    """
    
    queryset = Vendor.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['lifecycle_state', 'risk_tier', 'owner_org_id']
    search_fields = ['vendor_id', 'legal_name', 'display_name']
    ordering_fields = ['vendor_id', 'created_at', 'updated_at', 'risk_tier']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return VendorListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return VendorCreateUpdateSerializer
        else:
            return VendorDetailedSerializer

    @action(detail=True, methods=['get'])
    def contacts(self, request, pk=None):
        """Get all contacts for a vendor."""
        vendor = self.get_object()
        contacts = vendor.contacts.all()
        serializer = VendorContactSerializer(
            contacts, many=True, context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def identifiers(self, request, pk=None):
        """Get all identifiers for a vendor."""
        vendor = self.get_object()
        identifiers = vendor.identifiers.all()
        serializer = VendorIdentifierSerializer(
            identifiers, many=True, context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def notes(self, request, pk=None):
        """Get all notes for a vendor."""
        vendor = self.get_object()
        notes = vendor.vendor_notes.all()
        serializer = VendorNoteSerializer(
            notes, many=True, context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def warnings(self, request, pk=None):
        """Get all warnings for a vendor."""
        vendor = self.get_object()
        warnings = vendor.vendor_warnings.all()
        serializer = VendorWarningSerializer(
            warnings, many=True, context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def tickets(self, request, pk=None):
        """Get all tickets for a vendor."""
        vendor = self.get_object()
        tickets = vendor.vendor_tickets.all()
        serializer = VendorTicketSerializer(
            tickets, many=True, context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get summary statistics for a vendor."""
        vendor = self.get_object()
        from django.db.models import Count
        data = {
            'vendor_id': vendor.vendor_id,
            'display_name': vendor.display_name,
            'contact_count': vendor.contacts.count(),
            'identifier_count': vendor.identifiers.count(),
            'note_count': vendor.vendor_notes.count(),
            'warning_count': vendor.vendor_warnings.filter(status='active').count(),
            'open_ticket_count': vendor.vendor_tickets.filter(status__in=['open', 'in_progress']).count(),
            'business_owner_count': vendor.business_owners.count(),
            'org_assignment_count': vendor.org_assignments.count(),
        }
        return Response(data)


class VendorContactAPIViewSet(viewsets.ModelViewSet):
    """ViewSet for vendor contacts."""
    serializer_class = VendorContactSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['vendor', 'contact_type', 'is_active', 'is_primary']
    search_fields = ['full_name', 'email']

    def get_queryset(self):
        """Filter contacts by vendor if provided."""
        queryset = VendorContact.objects.all()
        vendor_id = self.request.query_params.get('vendor_id')
        if vendor_id:
            queryset = queryset.filter(vendor__vendor_id=vendor_id)
        return queryset


class VendorIdentifierAPIViewSet(viewsets.ModelViewSet):
    """ViewSet for vendor identifiers."""
    serializer_class = VendorIdentifierSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['vendor', 'identifier_type', 'is_verified']
    search_fields = ['identifier_value']

    def get_queryset(self):
        """Filter identifiers by vendor if provided."""
        queryset = VendorIdentifier.objects.all()
        vendor_id = self.request.query_params.get('vendor_id')
        if vendor_id:
            queryset = queryset.filter(vendor__vendor_id=vendor_id)
        return queryset


class OnboardingWorkflowAPIViewSet(viewsets.ModelViewSet):
    """ViewSet for onboarding workflows with state transitions."""
    serializer_class = OnboardingWorkflowSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['current_state', 'vendor']
    ordering = ['-initiated_at']

    def get_queryset(self):
        return OnboardingWorkflow.objects.all()

    @action(detail=True, methods=['post'])
    def change_state(self, request, pk=None):
        """Perform a state transition."""
        workflow = self.get_object()
        serializer = OnboardingWorkflowStateChangeSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        action_name = serializer.validated_data.get('action')
        reviewer = serializer.validated_data.get('reviewer')
        reason = serializer.validated_data.get('reason')
        notes = serializer.validated_data.get('notes')

        try:
            if action_name == 'request_information':
                workflow.request_information(reason=reason, notes=notes)
            elif action_name == 'mark_information_received':
                workflow.mark_information_received()
            elif action_name == 'assign_for_review':
                workflow.assign_for_review(reviewer=reviewer, reason=reason, notes=notes)
            elif action_name == 'approve_vendor':
                workflow.approve_vendor(reviewer=reviewer, notes=notes)
            elif action_name == 'reject_vendor':
                workflow.reject_vendor(reviewer=reviewer, notes=notes)
            elif action_name == 'activate_vendor':
                workflow.activate_vendor(notes=notes)
            elif action_name == 'archive_workflow':
                workflow.archive_workflow(notes=notes)
            elif action_name == 'reopen_draft':
                workflow.reopen_draft(notes=notes)
            else:
                return Response(
                    {'error': f'Unknown action: {action_name}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            workflow.save()
            serializer = OnboardingWorkflowSerializer(
                workflow, context={'request': request}
            )
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class VendorNoteAPIViewSet(viewsets.ModelViewSet):
    """ViewSet for vendor notes."""
    serializer_class = VendorNoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['vendor', 'note_type']
    search_fields = ['note_text']

    def get_queryset(self):
        queryset = VendorNote.objects.all()
        vendor_id = self.request.query_params.get('vendor_id')
        if vendor_id:
            queryset = queryset.filter(vendor__vendor_id=vendor_id)
        return queryset


class VendorWarningAPIViewSet(viewsets.ModelViewSet):
    """ViewSet for vendor warnings."""
    serializer_class = VendorWarningSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['vendor', 'severity', 'status']
    search_fields = ['title', 'warning_category']
    ordering_fields = ['severity', 'detected_at']
    ordering = ['-severity', '-detected_at']

    def get_queryset(self):
        queryset = VendorWarning.objects.all()
        vendor_id = self.request.query_params.get('vendor_id')
        if vendor_id:
            queryset = queryset.filter(vendor__vendor_id=vendor_id)
        return queryset


class VendorTicketAPIViewSet(viewsets.ModelViewSet):
    """ViewSet for vendor tickets."""
    serializer_class = VendorTicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['vendor', 'status', 'priority']
    search_fields = ['title', 'external_ticket_id']
    ordering_fields = ['priority', 'opened_date']
    ordering = ['-priority', '-opened_date']

    def get_queryset(self):
        queryset = VendorTicket.objects.all()
        vendor_id = self.request.query_params.get('vendor_id')
        if vendor_id:
            queryset = queryset.filter(vendor__vendor_id=vendor_id)
        return queryset


class OfferingNoteAPIViewSet(viewsets.ModelViewSet):
    """ViewSet for offering notes."""
    serializer_class = OfferingNoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['offering_id', 'note_type']
    search_fields = ['note_text']

    def get_queryset(self):
        return OfferingNote.objects.all()


class OfferingTicketAPIViewSet(viewsets.ModelViewSet):
    """ViewSet for offering tickets."""
    serializer_class = OfferingTicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['offering_id', 'status', 'priority']
    search_fields = ['title', 'external_ticket_id']
    ordering = ['-opened_date']

    def get_queryset(self):
        return OfferingTicket.objects.all()


class ContractEventAPIViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only ViewSet for contract events."""
    serializer_class = ContractEventSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['contract_id', 'event_type']
    search_fields = ['contract_id']
    ordering = ['-event_date']

    def get_queryset(self):
        return ContractEvent.objects.all()


class VendorDemoAPIViewSet(viewsets.ModelViewSet):
    """ViewSet for vendor demos."""
    serializer_class = VendorDemoSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['vendor', 'selection_outcome']
    search_fields = ['demo_id']
    ordering = ['-demo_date']

    def get_queryset(self):
        queryset = VendorDemo.objects.all()
        vendor_id = self.request.query_params.get('vendor_id')
        if vendor_id:
            queryset = queryset.filter(vendor__vendor_id=vendor_id)
        return queryset


class DemoScoreAPIViewSet(viewsets.ModelViewSet):
    """ViewSet for demo scores."""
    serializer_class = DemoScoreSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['demo', 'score_category']
    search_fields = ['score_category']

    def get_queryset(self):
        queryset = DemoScore.objects.all()
        demo_id = self.request.query_params.get('demo_id')
        if demo_id:
            queryset = queryset.filter(demo_id=demo_id)
        return queryset


class DemoNoteAPIViewSet(viewsets.ModelViewSet):
    """ViewSet for demo notes."""
    serializer_class = DemoNoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['demo', 'note_type']
    search_fields = ['note_text']

    def get_queryset(self):
        queryset = DemoNote.objects.all()
        demo_id = self.request.query_params.get('demo_id')
        if demo_id:
            queryset = queryset.filter(demo_id=demo_id)
        return queryset


class VendorBusinessOwnerAPIViewSet(viewsets.ModelViewSet):
    """ViewSet for vendor business owners."""
    serializer_class = VendorBusinessOwnerSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['vendor', 'is_primary']
    search_fields = ['owner_user_principal', 'owner_name']

    def get_queryset(self):
        queryset = VendorBusinessOwner.objects.all()
        vendor_id = self.request.query_params.get('vendor_id')
        if vendor_id:
            queryset = queryset.filter(vendor__vendor_id=vendor_id)
        return queryset


class VendorOrgAssignmentAPIViewSet(viewsets.ModelViewSet):
    """ViewSet for vendor organization assignments."""
    serializer_class = VendorOrgAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['vendor', 'org_id', 'is_primary']
    search_fields = ['org_id', 'org_name']

    def get_queryset(self):
        queryset = VendorOrgAssignment.objects.all()
        vendor_id = self.request.query_params.get('vendor_id')
        if vendor_id:
            queryset = queryset.filter(vendor__vendor_id=vendor_id)
        return queryset
