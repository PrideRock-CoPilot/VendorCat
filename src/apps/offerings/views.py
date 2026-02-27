from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import IntegrityError, models
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.core.contracts.identity import resolve_identity_context
from apps.core.services.lob_authorization import can_view_contracts, has_lob_scope, is_scope_restricted
from apps.core.services.permission_registry import authorize_mutation
from apps.contracts.constants import CONTRACT_STATUS_OPTIONS
from apps.contracts.models import Contract
from apps.identity.services import build_policy_snapshot, sync_user_directory
from apps.identity.models import UserDirectory
from apps.offerings.constants import (
    CRITICALITY_TIERS,
    OFFERING_LOB_OPTIONS,
    OFFERING_SERVICE_TYPES,
    OFFERING_TYPES,
)
from apps.offerings.models import Offering
from apps.offerings.models import OfferingContact
from apps.offerings.models import OfferingDataFlow
from apps.offerings.models import OfferingDocument
from apps.offerings.models import OfferingEntitlement
from apps.offerings.models import OfferingProgramProfile
from apps.offerings.models import OfferingServiceTicket
from apps.vendors.constants import LIFECYCLE_STATES
from apps.vendors.models import Vendor, VendorContact


def _normalize_choice(value: str, allowed: list[str], field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""
    canonical_by_lower = {item.lower(): item for item in allowed}
    canonical = canonical_by_lower.get(normalized.lower())
    if canonical:
        return canonical
    raise ValueError(f"{field_name} must be one of: {', '.join(allowed)}")


def _normalize_lifecycle(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in LIFECYCLE_STATES:
        raise ValueError(f"lifecycle_state must be one of: {', '.join(LIFECYCLE_STATES)}")
    return normalized


def _normalize_criticality(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        return ""
    if normalized not in CRITICALITY_TIERS:
        raise ValueError(f"criticality_tier must be one of: {', '.join(CRITICALITY_TIERS)}")
    return normalized


def _serialize_offering(record: Offering) -> dict[str, str]:
    return {
        "offering_id": record.offering_id,
        "vendor_id": record.vendor.vendor_id,
        "vendor_display_name": record.vendor.display_name,
        "offering_name": record.offering_name,
        "offering_type": record.offering_type,
        "lob": record.lob,
        "service_type": record.service_type,
        "lifecycle_state": record.lifecycle_state,
        "criticality_tier": record.criticality_tier,
    }


def _parse_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if not normalized:
        return default
    return normalized in {"1", "true", "on", "yes", "y"}


def _resolve_contact_submission(
    *,
    full_name: str,
    role: str,
    email: str,
    phone: str,
    notes: str,
    is_primary: bool,
    is_active: bool,
    contact_source: str,
    internal_user_principal: str,
    external_contact_id: str,
    internal_contact_role: str,
) -> tuple[dict[str, object], str | None]:
    resolved: dict[str, object] = {
        "full_name": full_name.strip(),
        "role": role.strip(),
        "email": email.strip(),
        "phone": phone.strip(),
        "notes": notes.strip(),
        "is_primary": is_primary,
        "is_active": is_active,
    }

    source = contact_source.strip().lower() or "external"
    if source == "internal":
        principal = internal_user_principal.strip().lower()
        if not principal:
            return resolved, "internal_user_principal is required for internal contacts"
        user = UserDirectory.objects.filter(user_principal=principal, active_flag=True).first()
        if not user:
            return resolved, "internal contact must map to an active user"
        resolved["full_name"] = (user.display_name or user.user_principal).strip()
        resolved["email"] = str(user.email or user.user_principal).strip()
        resolved["role"] = internal_contact_role.strip() or str(resolved.get("role", "")).strip()
    else:
        if external_contact_id.strip():
            try:
                source_contact = VendorContact.objects.filter(id=int(external_contact_id.strip()), is_active=True).first()
            except (TypeError, ValueError):
                source_contact = None
            if source_contact:
                resolved["full_name"] = str(resolved.get("full_name", "")).strip() or source_contact.full_name
                resolved["email"] = str(resolved.get("email", "")).strip() or str(source_contact.email or "")
                resolved["phone"] = str(resolved.get("phone", "")).strip() or str(source_contact.phone or "")
                resolved["role"] = str(resolved.get("role", "")).strip() or str(source_contact.title or "")

    if not str(resolved.get("full_name", "")).strip():
        return resolved, "Contact name is required"
    return resolved, None


def _parse_date(value: str) -> date | None:
    raw = value.strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("date must be in YYYY-MM-DD format") from exc


def _parse_decimal(value: str) -> Decimal | None:
    raw = value.strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("annual_value must be a decimal number") from exc


def _serialize_offering_contact(record: OfferingContact) -> dict[str, object]:
    return {
        "id": record.id,
        "offering_id": record.offering.offering_id,
        "full_name": record.full_name,
        "role": record.role,
        "email": record.email,
        "phone": record.phone,
        "is_primary": record.is_primary,
        "is_active": record.is_active,
        "notes": record.notes,
    }


def _serialize_offering_contract(record: Contract) -> dict[str, object]:
    return {
        "contract_id": record.contract_id,
        "offering_id": record.offering_id,
        "vendor_id": record.vendor.vendor_id,
        "contract_number": record.contract_number,
        "contract_status": record.contract_status,
        "start_date": record.start_date.isoformat() if record.start_date else "",
        "end_date": record.end_date.isoformat() if record.end_date else "",
        "annual_value": record.annual_value_display,
        "cancelled_flag": record.cancelled_flag,
    }


def _serialize_offering_data_flow(record: OfferingDataFlow) -> dict[str, object]:
    return {
        "id": record.id,
        "offering_id": record.offering.offering_id,
        "flow_name": record.flow_name,
        "source_system": record.source_system,
        "target_system": record.target_system,
        "direction": record.direction,
        "status": record.status,
        "frequency": record.frequency,
        "notes": record.notes,
    }


def _serialize_offering_service_ticket(record: OfferingServiceTicket) -> dict[str, object]:
    return {
        "id": record.id,
        "offering_id": record.offering.offering_id,
        "ticket_system": record.ticket_system,
        "external_ticket_id": record.external_ticket_id,
        "title": record.title,
        "status": record.status,
        "priority": record.priority,
        "notes": record.notes,
        "created_by": record.created_by,
    }


def _serialize_offering_document(record: OfferingDocument) -> dict[str, object]:
    return {
        "id": record.id,
        "offering_id": record.offering.offering_id,
        "doc_title": record.doc_title,
        "doc_url": record.doc_url,
        "doc_type": record.doc_type,
        "owner_principal": record.owner_principal,
        "tags": record.tags,
        "notes": record.notes,
        "is_active": record.is_active,
    }


def _serialize_offering_program_profile(record: OfferingProgramProfile) -> dict[str, object]:
    return {
        "offering_id": record.offering.offering_id,
        "internal_owner": record.internal_owner,
        "vendor_success_manager": record.vendor_success_manager,
        "sla_target_pct": str(record.sla_target_pct) if record.sla_target_pct is not None else "",
        "rto_hours": record.rto_hours if record.rto_hours is not None else "",
        "data_residency": record.data_residency,
        "compliance_tags": record.compliance_tags,
        "budget_annual": str(record.budget_annual) if record.budget_annual is not None else "",
        "roadmap_notes": record.roadmap_notes,
    }


def _serialize_offering_entitlement(record: OfferingEntitlement) -> dict[str, object]:
    return {
        "id": record.id,
        "offering_id": record.offering.offering_id,
        "entitlement_name": record.entitlement_name,
        "license_type": record.license_type,
        "purchased_units": record.purchased_units,
        "assigned_units": record.assigned_units,
        "available_units": max(0, record.purchased_units - record.assigned_units),
        "renewal_date": record.renewal_date.isoformat() if record.renewal_date else "",
        "true_up_date": record.true_up_date.isoformat() if record.true_up_date else "",
        "notes": record.notes,
    }


def index(request: HttpRequest) -> HttpResponse:
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)

    queryset = Offering.objects.select_related("vendor").order_by("offering_id")  # type: ignore[attr-defined]

    search_query = str(request.GET.get("q", "")).strip()
    status_filter = str(request.GET.get("status", "")).strip().lower()
    criticality_filter = str(request.GET.get("criticality", "")).strip().lower()
    health_filter = str(request.GET.get("health", "")).strip().lower()

    if search_query:
        queryset = queryset.filter(
            models.Q(offering_id__icontains=search_query)
            | models.Q(offering_name__icontains=search_query)
            | models.Q(vendor__vendor_id__icontains=search_query)
            | models.Q(vendor__display_name__icontains=search_query)
        )

    if status_filter in set(LIFECYCLE_STATES):
        queryset = queryset.filter(lifecycle_state=status_filter)

    if criticality_filter in set(CRITICALITY_TIERS):
        queryset = queryset.filter(criticality_tier=criticality_filter)

    open_or_in_progress_ticket_offering_ids = set(
        OfferingServiceTicket.objects.filter(status__in=["open", "in_progress"])  # type: ignore[attr-defined]
        .values_list("offering_id", flat=True)
    )

    if health_filter == "needs_attention":
        queryset = queryset.filter(
            models.Q(offering_id__istartswith="tmp-")
            | models.Q(id__in=open_or_in_progress_ticket_offering_ids)
        )

    records = list(queryset[:100])
    offering_ids = [record.offering_id for record in records]

    active_contract_counts = {
        offering_id: count
        for offering_id, count in Contract.objects.filter(  # type: ignore[attr-defined]
            offering_id__in=offering_ids,
            contract_status="active",
        )
        .values("offering_id")
        .annotate(count=Count("id"))
        .values_list("offering_id", "count")
    }

    open_ticket_counts = {
        offering_id: count
        for offering_id, count in OfferingServiceTicket.objects.filter(  # type: ignore[attr-defined]
            offering__offering_id__in=offering_ids,
            status__in=["open", "in_progress"],
        )
        .values("offering__offering_id")
        .annotate(count=Count("id"))
        .values_list("offering__offering_id", "count")
    }

    items: list[dict[str, object]] = []
    can_create_offering = authorize_mutation(snapshot, "POST", "/api/v1/vendors/{vendor_id}/offerings").allowed
    can_edit_offering_global = authorize_mutation(snapshot, "PATCH", "/api/v1/offerings/{offering_id}").allowed
    scoped = is_scope_restricted(snapshot)
    for record in records:
        entry: dict[str, object] = _serialize_offering(record)
        active_contract_count = int(active_contract_counts.get(record.offering_id, 0))
        open_ticket_count = int(open_ticket_counts.get(record.offering_id, 0))
        is_tmp = record.offering_id.lower().startswith("tmp-")
        needs_attention = open_ticket_count > 0 or is_tmp
        entry["active_contract_count"] = active_contract_count
        entry["open_ticket_count"] = open_ticket_count
        entry["needs_attention"] = needs_attention
        entry["is_tmp"] = is_tmp
        entry["can_edit"] = can_edit_offering_global and (
            (not scoped) or has_lob_scope(snapshot, record.lob, minimum_level="edit")
        )
        items.append(entry)

    summary = {
        "total": len(items),
        "active": sum(1 for item in items if item["lifecycle_state"] == "active"),
        "high_criticality": sum(1 for item in items if item["criticality_tier"] in {"tier_1", "tier_2"}),
        "needs_attention": sum(1 for item in items if item["needs_attention"]),
    }

    return render(
        request,
        "offerings/index.html",
        {
            "page_title": "Offerings",
            "section_name": "Offerings",
            "items": items,
            "search_query": search_query,
            "current_status": status_filter,
            "current_criticality": criticality_filter,
            "current_health": health_filter,
            "summary": summary,
            "can_create_offering": can_create_offering,
        },
    )


@require_http_methods(["GET"])
def offering_detail_page(request: HttpRequest, offering_id: str) -> HttpResponse:
    try:
        record = Offering.objects.select_related("vendor").get(offering_id=offering_id)  # type: ignore[attr-defined]
    except Offering.DoesNotExist:  # type: ignore[attr-defined]
        return render(
            request,
            "shared/error.html",
            {
                "page_title": "Offering Not Found",
                "error_message": f"Offering {offering_id} was not found.",
                "request_id": getattr(request, "request_id", ""),
            },
            status=404,
        )

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    contracts_visible = can_view_contracts(snapshot)
    has_lob_edit_scope = not is_scope_restricted(snapshot) or has_lob_scope(
        snapshot,
        record.lob,
        minimum_level="edit",
    )

    can_manage_program_profile = has_lob_edit_scope and authorize_mutation(
        snapshot,
        "PATCH",
        "/api/v1/offerings/{offering_id}/program-profile",
    ).allowed
    can_manage_entitlements = has_lob_edit_scope and authorize_mutation(
        snapshot,
        "POST",
        "/api/v1/offerings/{offering_id}/entitlements",
    ).allowed
    can_manage_contacts = has_lob_edit_scope and authorize_mutation(
        snapshot,
        "POST",
        "/api/v1/offerings/{offering_id}/contacts",
    ).allowed
    can_manage_contracts = contracts_visible and has_lob_edit_scope and authorize_mutation(
        snapshot,
        "POST",
        "/api/v1/offerings/{offering_id}/contracts",
    ).allowed
    can_manage_data_flows = has_lob_edit_scope and authorize_mutation(
        snapshot,
        "POST",
        "/api/v1/offerings/{offering_id}/data-flows",
    ).allowed
    can_manage_service_tickets = has_lob_edit_scope and authorize_mutation(
        snapshot,
        "POST",
        "/api/v1/offerings/{offering_id}/service-tickets",
    ).allowed
    can_manage_documents = has_lob_edit_scope and authorize_mutation(
        snapshot,
        "POST",
        "/api/v1/offerings/{offering_id}/documents",
    ).allowed

    contracts = []
    if contracts_visible:
        contracts = list(
            Contract.objects.select_related("vendor")  # type: ignore[attr-defined]
            .filter(vendor=record.vendor, offering_id=record.offering_id)
            .order_by("contract_id")
        )
    service_tickets = list(
        OfferingServiceTicket.objects.filter(offering=record).order_by("-id")  # type: ignore[attr-defined]
    )
    documents = list(OfferingDocument.objects.filter(offering=record).order_by("-id"))  # type: ignore[attr-defined]
    entitlements = list(OfferingEntitlement.objects.filter(offering=record).order_by("id"))  # type: ignore[attr-defined]

    profile, _ = OfferingProgramProfile.objects.get_or_create(offering=record)  # type: ignore[attr-defined]
    today = date.today()
    active_contracts = [
        contract
        for contract in contracts
        if contract.contract_status == "active" and not contract.cancelled_flag
    ]
    annual_spend_total = sum((contract.annual_value or Decimal("0")) for contract in active_contracts)

    renewal_dates = [
        contract.end_date
        for contract in active_contracts
        if contract.end_date is not None and contract.end_date >= today
    ]
    next_renewal_date = min(renewal_dates) if renewal_dates else None
    renewal_days = (next_renewal_date - today).days if next_renewal_date else None

    open_ticket_count = sum(1 for ticket in service_tickets if ticket.status in {"open", "in_progress"})
    health_score = max(0, 100 - (open_ticket_count * 15))

    return render(
        request,
        "offerings/detail.html",
        {
            "page_title": f"Offering {record.offering_name}",
            "offering": _serialize_offering(record),
            "contacts": list(OfferingContact.objects.filter(offering=record).order_by("id")),  # type: ignore[attr-defined]
            "contracts": contracts,
            "data_flows": list(OfferingDataFlow.objects.filter(offering=record).order_by("id")),  # type: ignore[attr-defined]
            "service_tickets": service_tickets,
            "documents": documents,
            "program_profile": _serialize_offering_program_profile(profile),
            "entitlements": entitlements,
            "portfolio": {
                "annual_spend_total": str(annual_spend_total),
                "next_renewal_date": next_renewal_date.isoformat() if next_renewal_date else "",
                "renewal_days": renewal_days if renewal_days is not None else "",
                "open_ticket_count": open_ticket_count,
                "health_score": health_score,
                "document_count": len(documents),
            },
            "contracts_visible": contracts_visible,
            "lob_scoped": is_scope_restricted(snapshot),
            "can_manage_program_profile": can_manage_program_profile,
            "can_manage_entitlements": can_manage_entitlements,
            "can_manage_contacts": can_manage_contacts,
            "can_manage_contracts": can_manage_contracts,
            "can_manage_data_flows": can_manage_data_flows,
            "can_manage_service_tickets": can_manage_service_tickets,
            "can_manage_documents": can_manage_documents,
        },
    )


@require_http_methods(["GET", "POST"])
def offering_form_page(request: HttpRequest, offering_id: str | None = None) -> HttpResponse:
    offering = None
    form_errors: dict[str, list[str]] = {}

    if offering_id:
        offering = get_object_or_404(Offering.objects.select_related("vendor"), offering_id=offering_id)

    if request.method == "POST":
        identity = resolve_identity_context(request)
        sync_user_directory(identity)
        snapshot = build_policy_snapshot(identity)
        decision = authorize_mutation(
            snapshot,
            "POST" if not offering else "PATCH",
            "/api/v1/vendors/{vendor_id}/offerings" if not offering else "/api/v1/offerings/{offering_id}",
        )
        if not decision.allowed:
            messages.error(request, f"Permission denied: {decision.reason}")
            if offering:
                return redirect(f"/offerings/{offering.offering_id}")
            return redirect("/offerings")

        if offering and is_scope_restricted(snapshot) and not has_lob_scope(
            snapshot,
            offering.lob,
            minimum_level="edit",
        ):
            messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
            return redirect(f"/offerings/{offering.offering_id}")

        offering_id_val = request.POST.get("offering_id", "").strip()
        vendor_id = request.POST.get("vendor_id", "").strip()
        offering_name = request.POST.get("offering_name", "").strip()
        lifecycle_state = request.POST.get("lifecycle_state", "").strip()
        offering_type = request.POST.get("offering_type", "").strip()
        lob = request.POST.get("lob", "").strip()
        service_type = request.POST.get("service_type", "").strip()
        criticality_tier = request.POST.get("criticality_tier", "").strip()

        if not offering and not offering_id_val:
            form_errors["offering_id"] = ["Offering ID is required"]
        if not vendor_id:
            form_errors["vendor_id"] = ["Vendor is required"]
        if not offering_name:
            form_errors["offering_name"] = ["Offering name is required"]

        try:
            lifecycle_state = _normalize_lifecycle(lifecycle_state) if lifecycle_state else "draft"
        except ValueError as exc:
            form_errors["lifecycle_state"] = [str(exc)]

        try:
            offering_type = _normalize_choice(offering_type, OFFERING_TYPES, "offering_type")
        except ValueError as exc:
            form_errors["offering_type"] = [str(exc)]

        try:
            lob = _normalize_choice(lob, OFFERING_LOB_OPTIONS, "lob")
        except ValueError as exc:
            form_errors["lob"] = [str(exc)]

        try:
            service_type = _normalize_choice(service_type, OFFERING_SERVICE_TYPES, "service_type")
        except ValueError as exc:
            form_errors["service_type"] = [str(exc)]

        try:
            criticality_tier = _normalize_criticality(criticality_tier)
        except ValueError as exc:
            form_errors["criticality_tier"] = [str(exc)]

        vendor = None
        if vendor_id:
            try:
                vendor = Vendor.objects.get(vendor_id=vendor_id)
            except Vendor.DoesNotExist:
                form_errors["vendor_id"] = ["Vendor not found"]

        if not offering and offering_id_val and Offering.objects.filter(offering_id=offering_id_val).exists():
            form_errors["offering_id"] = ["Offering ID already exists"]

        if form_errors:
            return render(
                request,
                "offerings/form.html",
                {
                    "offering": offering,
                    "form_errors": form_errors,
                    "vendors": Vendor.objects.order_by("display_name"),
                    "offering_types": OFFERING_TYPES,
                    "lifecycle_states": LIFECYCLE_STATES,
                    "lob_options": OFFERING_LOB_OPTIONS,
                    "service_type_options": OFFERING_SERVICE_TYPES,
                    "criticality_tiers": CRITICALITY_TIERS,
                },
            )

        if offering:
            offering.vendor = vendor
            offering.offering_name = offering_name
            offering.offering_type = offering_type
            offering.lob = lob
            offering.service_type = service_type
            offering.lifecycle_state = lifecycle_state
            offering.criticality_tier = criticality_tier
            offering.save()
            messages.success(request, f"Offering {offering.offering_id} updated successfully")
            return redirect(f"/offerings/{offering.offering_id}")

        created = Offering.objects.create(
            offering_id=offering_id_val,
            vendor=vendor,
            offering_name=offering_name,
            offering_type=offering_type,
            lob=lob,
            service_type=service_type,
            lifecycle_state=lifecycle_state,
            criticality_tier=criticality_tier,
        )
        messages.success(request, f"Offering {created.offering_id} created successfully")
        return redirect(f"/offerings/{created.offering_id}")

    prefill_vendor_id = request.GET.get("vendor", "").strip()
    return render(
        request,
        "offerings/form.html",
        {
            "offering": offering,
            "prefill_vendor_id": prefill_vendor_id,
            "vendors": Vendor.objects.order_by("display_name"),
            "offering_types": OFFERING_TYPES,
            "lifecycle_states": LIFECYCLE_STATES,
            "lob_options": OFFERING_LOB_OPTIONS,
            "service_type_options": OFFERING_SERVICE_TYPES,
            "criticality_tiers": CRITICALITY_TIERS,
            "form_errors": form_errors,
        },
    )


@require_http_methods(["POST"])
def offering_program_profile_form_submit(request: HttpRequest, offering_id: str) -> HttpResponse:
    offering = get_object_or_404(Offering, offering_id=offering_id)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "PATCH", "/api/v1/offerings/{offering_id}/program-profile")
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    profile, _ = OfferingProgramProfile.objects.get_or_create(offering=offering)  # type: ignore[attr-defined]
    profile.internal_owner = request.POST.get("internal_owner", "").strip()
    profile.vendor_success_manager = request.POST.get("vendor_success_manager", "").strip()
    profile.data_residency = request.POST.get("data_residency", "").strip()
    profile.compliance_tags = request.POST.get("compliance_tags", "").strip()
    profile.roadmap_notes = request.POST.get("roadmap_notes", "").strip()

    try:
        sla_raw = request.POST.get("sla_target_pct", "").strip()
        profile.sla_target_pct = Decimal(sla_raw) if sla_raw else None
        rto_raw = request.POST.get("rto_hours", "").strip()
        profile.rto_hours = int(rto_raw) if rto_raw else None
        budget_raw = request.POST.get("budget_annual", "").strip()
        profile.budget_annual = Decimal(budget_raw) if budget_raw else None
    except (ValueError, InvalidOperation):
        messages.error(request, "Invalid numeric value in program profile fields")
        return redirect(f"/offerings/{offering_id}")

    profile.save()
    messages.success(request, "Program profile updated")
    return redirect(f"/offerings/{offering_id}")


@require_http_methods(["POST"])
def offering_entitlement_form_submit(request: HttpRequest, offering_id: str) -> HttpResponse:
    offering = get_object_or_404(Offering, offering_id=offering_id)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/offerings/{offering_id}/entitlements")
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    entitlement_name = request.POST.get("entitlement_name", "").strip()
    if not entitlement_name:
        messages.error(request, "Entitlement name is required")
        return redirect(f"/offerings/{offering_id}")

    try:
        purchased_units = int(request.POST.get("purchased_units", "0").strip() or "0")
        assigned_units = int(request.POST.get("assigned_units", "0").strip() or "0")
    except ValueError:
        messages.error(request, "Purchased/assigned units must be integers")
        return redirect(f"/offerings/{offering_id}")

    if purchased_units < 0 or assigned_units < 0:
        messages.error(request, "Purchased/assigned units must be non-negative")
        return redirect(f"/offerings/{offering_id}")
    if assigned_units > purchased_units:
        messages.error(request, "Assigned units cannot exceed purchased units")
        return redirect(f"/offerings/{offering_id}")

    try:
        renewal_date = _parse_date(request.POST.get("renewal_date", ""))
        true_up_date = _parse_date(request.POST.get("true_up_date", ""))
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(f"/offerings/{offering_id}")

    OfferingEntitlement.objects.create(  # type: ignore[attr-defined]
        offering=offering,
        entitlement_name=entitlement_name,
        license_type=request.POST.get("license_type", "").strip(),
        purchased_units=purchased_units,
        assigned_units=assigned_units,
        renewal_date=renewal_date,
        true_up_date=true_up_date,
        notes=request.POST.get("notes", "").strip(),
    )
    messages.success(request, "Entitlement added")
    return redirect(f"/offerings/{offering_id}")


@require_http_methods(["POST"])
def offering_entitlement_delete_form_submit(
    request: HttpRequest,
    offering_id: str,
    entitlement_id: int,
) -> HttpResponse:
    offering = get_object_or_404(Offering, offering_id=offering_id)
    entitlement = get_object_or_404(OfferingEntitlement, id=entitlement_id, offering=offering)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(
        snapshot,
        "DELETE",
        "/api/v1/offerings/{offering_id}/entitlements/{entitlement_id}",
    )
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    entitlement.delete()
    messages.success(request, "Entitlement removed")
    return redirect(f"/offerings/{offering_id}")


@require_http_methods(["POST"])
def offering_contact_form_submit(request: HttpRequest, offering_id: str) -> HttpResponse:
    offering = get_object_or_404(Offering, offering_id=offering_id)
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/offerings/{offering_id}/contacts")
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    payload, payload_error = _resolve_contact_submission(
        full_name=request.POST.get("full_name", ""),
        role=request.POST.get("role", ""),
        email=request.POST.get("email", ""),
        phone=request.POST.get("phone", ""),
        notes=request.POST.get("notes", ""),
        is_primary=_parse_bool(request.POST.get("is_primary"), default=False),
        is_active=True,
        contact_source=request.POST.get("contact_source", "external"),
        internal_user_principal=request.POST.get("internal_user_principal", ""),
        external_contact_id=request.POST.get("external_contact_id", ""),
        internal_contact_role=request.POST.get("internal_contact_role", ""),
    )
    if payload_error:
        messages.error(request, payload_error)
        return redirect(f"/offerings/{offering_id}")

    OfferingContact.objects.create(  # type: ignore[attr-defined]
        offering=offering,
        full_name=str(payload["full_name"]),
        role=str(payload["role"]),
        email=str(payload["email"]),
        phone=str(payload["phone"]),
        is_primary=bool(payload["is_primary"]),
        is_active=bool(payload["is_active"]),
        notes=str(payload["notes"]),
    )
    messages.success(request, "Contact added")
    return redirect(f"/offerings/{offering_id}")


@require_http_methods(["POST"])
def offering_contact_edit_form_submit(request: HttpRequest, offering_id: str, contact_id: int) -> HttpResponse:
    offering = get_object_or_404(Offering, offering_id=offering_id)
    record = get_object_or_404(OfferingContact, id=contact_id, offering=offering)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "PATCH", "/api/v1/offerings/{offering_id}/contacts/{contact_id}")
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    full_name = request.POST.get("full_name", "").strip()
    if not full_name:
        messages.error(request, "Contact name is required")
        return redirect(f"/offerings/{offering_id}")

    record.full_name = full_name
    record.role = request.POST.get("role", "").strip()
    record.email = request.POST.get("email", "").strip()
    record.phone = request.POST.get("phone", "").strip()
    record.notes = request.POST.get("notes", "").strip()
    record.is_primary = str(request.POST.get("is_primary", "0")).strip().lower() in {"1", "true", "on", "yes"}
    record.is_active = str(request.POST.get("is_active", "1")).strip().lower() in {"1", "true", "on", "yes"}
    record.save()
    messages.success(request, "Contact updated")
    return redirect(f"/offerings/{offering_id}")


@require_http_methods(["POST"])
def offering_contact_delete_form_submit(request: HttpRequest, offering_id: str, contact_id: int) -> HttpResponse:
    offering = get_object_or_404(Offering, offering_id=offering_id)
    record = get_object_or_404(OfferingContact, id=contact_id, offering=offering)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "DELETE", "/api/v1/offerings/{offering_id}/contacts/{contact_id}")
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    record.delete()
    messages.success(request, "Contact removed")
    return redirect(f"/offerings/{offering_id}")


@require_http_methods(["POST"])
def offering_contract_form_submit(request: HttpRequest, offering_id: str) -> HttpResponse:
    offering = get_object_or_404(Offering.objects.select_related("vendor"), offering_id=offering_id)
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/offerings/{offering_id}/contracts")
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    contract_id = request.POST.get("contract_id", "").strip()
    if not contract_id:
        messages.error(request, "Contract ID is required")
        return redirect(f"/offerings/{offering_id}")
    if Contract.objects.filter(contract_id=contract_id).exists():  # type: ignore[attr-defined]
        messages.error(request, f"Contract {contract_id} already exists")
        return redirect(f"/offerings/{offering_id}")

    contract_status = request.POST.get("contract_status", "draft").strip().lower() or "draft"
    if contract_status not in CONTRACT_STATUS_OPTIONS:
        messages.error(request, f"Contract status must be one of: {', '.join(CONTRACT_STATUS_OPTIONS)}")
        return redirect(f"/offerings/{offering_id}")

    try:
        start_date = _parse_date(request.POST.get("start_date", ""))
        end_date = _parse_date(request.POST.get("end_date", ""))
        annual_value = _parse_decimal(request.POST.get("annual_value", ""))
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(f"/offerings/{offering_id}")

    Contract.objects.create(  # type: ignore[attr-defined]
        contract_id=contract_id,
        vendor=offering.vendor,
        offering_id=offering_id,
        contract_number=request.POST.get("contract_number", "").strip(),
        contract_status=contract_status,
        start_date=start_date,
        end_date=end_date,
        annual_value=annual_value,
        cancelled_flag=False,
    )
    messages.success(request, "Contract added")
    return redirect(f"/offerings/{offering_id}")


@require_http_methods(["POST"])
def offering_data_flow_form_submit(request: HttpRequest, offering_id: str) -> HttpResponse:
    offering = get_object_or_404(Offering, offering_id=offering_id)
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/offerings/{offering_id}/data-flows")
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    flow_name = request.POST.get("flow_name", "").strip()
    source_system = request.POST.get("source_system", "").strip()
    target_system = request.POST.get("target_system", "").strip()
    if not flow_name or not source_system or not target_system:
        messages.error(request, "Flow name, source system, and target system are required")
        return redirect(f"/offerings/{offering_id}")

    direction = request.POST.get("direction", "bidirectional").strip().lower() or "bidirectional"
    if direction not in {"inbound", "outbound", "bidirectional"}:
        messages.error(request, "Direction must be one of inbound, outbound, bidirectional")
        return redirect(f"/offerings/{offering_id}")

    OfferingDataFlow.objects.create(  # type: ignore[attr-defined]
        offering=offering,
        flow_name=flow_name,
        source_system=source_system,
        target_system=target_system,
        direction=direction,
        status=request.POST.get("status", "active").strip() or "active",
        frequency=request.POST.get("frequency", "").strip(),
        notes=request.POST.get("notes", "").strip(),
    )
    messages.success(request, "Data flow added")
    return redirect(f"/offerings/{offering_id}")


@require_http_methods(["POST"])
def offering_data_flow_edit_form_submit(request: HttpRequest, offering_id: str, flow_id: int) -> HttpResponse:
    offering = get_object_or_404(Offering, offering_id=offering_id)
    record = get_object_or_404(OfferingDataFlow, id=flow_id, offering=offering)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "PATCH", "/api/v1/offerings/{offering_id}/data-flows/{flow_id}")
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    flow_name = request.POST.get("flow_name", "").strip()
    source_system = request.POST.get("source_system", "").strip()
    target_system = request.POST.get("target_system", "").strip()
    if not flow_name or not source_system or not target_system:
        messages.error(request, "Flow name, source system, and target system are required")
        return redirect(f"/offerings/{offering_id}")

    direction = request.POST.get("direction", "bidirectional").strip().lower() or "bidirectional"
    if direction not in {"inbound", "outbound", "bidirectional"}:
        messages.error(request, "Direction must be one of inbound, outbound, bidirectional")
        return redirect(f"/offerings/{offering_id}")

    record.flow_name = flow_name
    record.source_system = source_system
    record.target_system = target_system
    record.direction = direction
    record.status = request.POST.get("status", "active").strip() or "active"
    record.frequency = request.POST.get("frequency", "").strip()
    record.notes = request.POST.get("notes", "").strip()
    record.save()
    messages.success(request, "Data flow updated")
    return redirect(f"/offerings/{offering_id}")


@require_http_methods(["POST"])
def offering_data_flow_delete_form_submit(request: HttpRequest, offering_id: str, flow_id: int) -> HttpResponse:
    offering = get_object_or_404(Offering, offering_id=offering_id)
    record = get_object_or_404(OfferingDataFlow, id=flow_id, offering=offering)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "DELETE", "/api/v1/offerings/{offering_id}/data-flows/{flow_id}")
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    record.delete()
    messages.success(request, "Data flow removed")
    return redirect(f"/offerings/{offering_id}")


@require_http_methods(["POST"])
def offering_service_ticket_form_submit(request: HttpRequest, offering_id: str) -> HttpResponse:
    offering = get_object_or_404(Offering, offering_id=offering_id)
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/offerings/{offering_id}/service-tickets")
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    title = request.POST.get("title", "").strip()
    if not title:
        messages.error(request, "Ticket title is required")
        return redirect(f"/offerings/{offering_id}")

    status = request.POST.get("status", "open").strip().lower() or "open"
    priority = request.POST.get("priority", "medium").strip().lower() or "medium"
    if status not in {"open", "in_progress", "closed"}:
        messages.error(request, "Status must be one of open, in_progress, closed")
        return redirect(f"/offerings/{offering_id}")
    if priority not in {"low", "medium", "high", "critical"}:
        messages.error(request, "Priority must be one of low, medium, high, critical")
        return redirect(f"/offerings/{offering_id}")

    OfferingServiceTicket.objects.create(  # type: ignore[attr-defined]
        offering=offering,
        ticket_system=request.POST.get("ticket_system", "").strip(),
        external_ticket_id=request.POST.get("external_ticket_id", "").strip(),
        title=title,
        status=status,
        priority=priority,
        notes=request.POST.get("notes", "").strip(),
        created_by=identity.user_principal,
    )
    messages.success(request, "Service ticket added")
    return redirect(f"/offerings/{offering_id}")


@require_http_methods(["POST"])
def offering_service_ticket_edit_form_submit(request: HttpRequest, offering_id: str, ticket_id: int) -> HttpResponse:
    offering = get_object_or_404(Offering, offering_id=offering_id)
    record = get_object_or_404(OfferingServiceTicket, id=ticket_id, offering=offering)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "PATCH", "/api/v1/offerings/{offering_id}/service-tickets/{ticket_id}")
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    title = request.POST.get("title", "").strip()
    if not title:
        messages.error(request, "Ticket title is required")
        return redirect(f"/offerings/{offering_id}")

    status = request.POST.get("status", "open").strip().lower() or "open"
    priority = request.POST.get("priority", "medium").strip().lower() or "medium"
    if status not in {"open", "in_progress", "closed"}:
        messages.error(request, "Status must be one of open, in_progress, closed")
        return redirect(f"/offerings/{offering_id}")
    if priority not in {"low", "medium", "high", "critical"}:
        messages.error(request, "Priority must be one of low, medium, high, critical")
        return redirect(f"/offerings/{offering_id}")

    record.ticket_system = request.POST.get("ticket_system", "").strip()
    record.external_ticket_id = request.POST.get("external_ticket_id", "").strip()
    record.title = title
    record.status = status
    record.priority = priority
    record.notes = request.POST.get("notes", "").strip()
    record.save()
    messages.success(request, "Service ticket updated")
    return redirect(f"/offerings/{offering_id}")


@require_http_methods(["POST"])
def offering_service_ticket_delete_form_submit(request: HttpRequest, offering_id: str, ticket_id: int) -> HttpResponse:
    offering = get_object_or_404(Offering, offering_id=offering_id)
    record = get_object_or_404(OfferingServiceTicket, id=ticket_id, offering=offering)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "DELETE", "/api/v1/offerings/{offering_id}/service-tickets/{ticket_id}")
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    record.delete()
    messages.success(request, "Service ticket removed")
    return redirect(f"/offerings/{offering_id}")


@require_http_methods(["POST"])
def offering_document_form_submit(request: HttpRequest, offering_id: str) -> HttpResponse:
    offering = get_object_or_404(Offering, offering_id=offering_id)
    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/offerings/{offering_id}/documents")
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    doc_title = request.POST.get("doc_title", "").strip()
    doc_url = request.POST.get("doc_url", "").strip()
    if not doc_title or not doc_url:
        messages.error(request, "Document title and URL are required")
        return redirect(f"/offerings/{offering_id}")

    OfferingDocument.objects.create(  # type: ignore[attr-defined]
        offering=offering,
        doc_title=doc_title,
        doc_url=doc_url,
        doc_type=request.POST.get("doc_type", "").strip(),
        owner_principal=request.POST.get("owner_principal", "").strip() or identity.user_principal,
        tags=request.POST.get("tags", "").strip(),
        notes=request.POST.get("notes", "").strip(),
        is_active=True,
    )
    messages.success(request, "Document added")
    return redirect(f"/offerings/{offering_id}")


@require_http_methods(["POST"])
def offering_document_edit_form_submit(request: HttpRequest, offering_id: str, document_id: int) -> HttpResponse:
    offering = get_object_or_404(Offering, offering_id=offering_id)
    record = get_object_or_404(OfferingDocument, id=document_id, offering=offering)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "PATCH", "/api/v1/offerings/{offering_id}/documents/{document_id}")
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    doc_title = request.POST.get("doc_title", "").strip()
    doc_url = request.POST.get("doc_url", "").strip()
    if not doc_title or not doc_url:
        messages.error(request, "Document title and URL are required")
        return redirect(f"/offerings/{offering_id}")

    record.doc_title = doc_title
    record.doc_url = doc_url
    record.doc_type = request.POST.get("doc_type", "").strip()
    record.owner_principal = request.POST.get("owner_principal", "").strip() or identity.user_principal
    record.tags = request.POST.get("tags", "").strip()
    record.notes = request.POST.get("notes", "").strip()
    record.is_active = str(request.POST.get("is_active", "1")).strip().lower() in {"1", "true", "on", "yes"}
    record.save()
    messages.success(request, "Document updated")
    return redirect(f"/offerings/{offering_id}")


@require_http_methods(["POST"])
def offering_document_delete_form_submit(request: HttpRequest, offering_id: str, document_id: int) -> HttpResponse:
    offering = get_object_or_404(Offering, offering_id=offering_id)
    record = get_object_or_404(OfferingDocument, id=document_id, offering=offering)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "DELETE", "/api/v1/offerings/{offering_id}/documents/{document_id}")
    if not decision.allowed:
        messages.error(request, f"Permission denied: {decision.reason}")
        return redirect(f"/offerings/{offering_id}")
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        messages.error(request, f"Permission denied: missing edit scope for offering LOB {offering.lob}")
        return redirect(f"/offerings/{offering_id}")

    record.delete()
    messages.success(request, "Document removed")
    return redirect(f"/offerings/{offering_id}")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def vendor_offerings_endpoint(request: HttpRequest, vendor_id: str) -> JsonResponse:
    try:
        vendor = Vendor.objects.get(vendor_id=vendor_id)  # type: ignore[attr-defined]
    except Vendor.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"vendor {vendor_id} not found"}, status=404)

    if request.method == "GET":
        items = [
            _serialize_offering(record)
            for record in Offering.objects.filter(vendor=vendor).order_by("offering_id")  # type: ignore[attr-defined]
        ]
        return JsonResponse({"items": items})

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/vendors/{vendor_id}/offerings")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    offering_id = str(body.get("offering_id", "")).strip() or f"offering-{uuid.uuid4().hex[:12]}"
    offering_name = str(body.get("offering_name", "")).strip()
    lifecycle_state = str(body.get("lifecycle_state", "draft")).strip() or "draft"
    offering_type = str(body.get("offering_type", "")).strip()
    lob = str(body.get("lob", "")).strip()
    service_type = str(body.get("service_type", "")).strip()
    criticality_tier = str(body.get("criticality_tier", "")).strip()

    if not offering_name:
        return JsonResponse({"error": "offering_name is required"}, status=400)

    try:
        lifecycle_state = _normalize_lifecycle(lifecycle_state)
        offering_type = _normalize_choice(offering_type, OFFERING_TYPES, "offering_type")
        lob = _normalize_choice(lob, OFFERING_LOB_OPTIONS, "lob")
        service_type = _normalize_choice(service_type, OFFERING_SERVICE_TYPES, "service_type")
        criticality_tier = _normalize_criticality(criticality_tier)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if Offering.objects.filter(offering_id=offering_id).exists():  # type: ignore[attr-defined]
        return JsonResponse({"error": f"offering {offering_id} already exists"}, status=409)

    try:
        record = Offering.objects.create(
            offering_id=offering_id,
            vendor=vendor,
            offering_name=offering_name,
            offering_type=offering_type,
            lob=lob,
            service_type=service_type,
            lifecycle_state=lifecycle_state,
            criticality_tier=criticality_tier,
        )  # type: ignore[attr-defined]
    except IntegrityError:
        return JsonResponse({"error": f"offering {offering_id} already exists"}, status=409)

    return JsonResponse(_serialize_offering(record), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def offering_detail_endpoint(request: HttpRequest, offering_id: str) -> JsonResponse:
    try:
        record = Offering.objects.select_related("vendor").get(offering_id=offering_id)  # type: ignore[attr-defined]
    except Offering.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"offering {offering_id} not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(_serialize_offering(record))

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "PATCH", "/api/v1/offerings/{offering_id}")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, record.lob, minimum_level="edit"):
        return JsonResponse(
            {"error": "forbidden", "reason": f"missing edit scope for offering LOB {record.lob}"},
            status=403,
        )

    body = json.loads(request.body.decode("utf-8") or "{}")
    updated = False
    for field_name in [
        "offering_name",
        "offering_type",
        "lob",
        "service_type",
        "lifecycle_state",
        "criticality_tier",
    ]:
        if field_name in body:
            value = str(body[field_name]).strip()
            try:
                if field_name == "lifecycle_state":
                    value = _normalize_lifecycle(value)
                if field_name == "offering_type":
                    value = _normalize_choice(value, OFFERING_TYPES, "offering_type")
                if field_name == "lob":
                    value = _normalize_choice(value, OFFERING_LOB_OPTIONS, "lob")
                if field_name == "service_type":
                    value = _normalize_choice(value, OFFERING_SERVICE_TYPES, "service_type")
                if field_name == "criticality_tier":
                    value = _normalize_criticality(value)
            except ValueError as exc:
                return JsonResponse({"error": str(exc)}, status=400)
            setattr(record, field_name, value)
            updated = True

    if updated:
        record.save()

    return JsonResponse(_serialize_offering(record))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def offering_contacts_endpoint(request: HttpRequest, offering_id: str) -> JsonResponse:
    try:
        offering = Offering.objects.get(offering_id=offering_id)  # type: ignore[attr-defined]
    except Offering.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"offering {offering_id} not found"}, status=404)

    if request.method == "GET":
        items = [
            _serialize_offering_contact(record)
            for record in OfferingContact.objects.filter(offering=offering).order_by("id")  # type: ignore[attr-defined]
        ]
        return JsonResponse({"items": items})

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/offerings/{offering_id}/contacts")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        return JsonResponse(
            {"error": "forbidden", "reason": f"missing edit scope for offering LOB {offering.lob}"},
            status=403,
        )

    body = json.loads(request.body.decode("utf-8") or "{}")
    payload, payload_error = _resolve_contact_submission(
        full_name=str(body.get("full_name", "")),
        role=str(body.get("role", "")),
        email=str(body.get("email", "")),
        phone=str(body.get("phone", "")),
        notes=str(body.get("notes", "")),
        is_primary=_parse_bool(body.get("is_primary"), default=False),
        is_active=_parse_bool(body.get("is_active"), default=True),
        contact_source=str(body.get("contact_source", "external")),
        internal_user_principal=str(body.get("internal_user_principal", "")),
        external_contact_id=str(body.get("external_contact_id", "")),
        internal_contact_role=str(body.get("internal_contact_role", "")),
    )
    if payload_error:
        return JsonResponse({"error": payload_error}, status=400)

    record = OfferingContact.objects.create(  # type: ignore[attr-defined]
        offering=offering,
        full_name=str(payload["full_name"]),
        role=str(payload["role"]),
        email=str(payload["email"]),
        phone=str(payload["phone"]),
        is_primary=bool(payload["is_primary"]),
        is_active=bool(payload["is_active"]),
        notes=str(payload["notes"]),
    )
    return JsonResponse(_serialize_offering_contact(record), status=201)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
def offering_contact_detail_endpoint(request: HttpRequest, offering_id: str, contact_id: int) -> JsonResponse:
    try:
        offering = Offering.objects.get(offering_id=offering_id)  # type: ignore[attr-defined]
        record = OfferingContact.objects.get(id=contact_id, offering=offering)  # type: ignore[attr-defined]
    except Offering.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"offering {offering_id} not found"}, status=404)
    except OfferingContact.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"contact {contact_id} not found"}, status=404)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(
        snapshot,
        request.method,
        "/api/v1/offerings/{offering_id}/contacts/{contact_id}",
    )
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        return JsonResponse(
            {"error": "forbidden", "reason": f"missing edit scope for offering LOB {offering.lob}"},
            status=403,
        )

    if request.method == "DELETE":
        record.delete()
        return JsonResponse({"status": "deleted"}, status=204)

    body = json.loads(request.body.decode("utf-8") or "{}")
    for field_name in ["full_name", "role", "email", "phone", "notes"]:
        if field_name in body:
            setattr(record, field_name, str(body[field_name]).strip())
    if "is_primary" in body:
        record.is_primary = bool(body["is_primary"])
    if "is_active" in body:
        record.is_active = bool(body["is_active"])
    if not record.full_name:
        return JsonResponse({"error": "full_name is required"}, status=400)
    record.save()
    return JsonResponse(_serialize_offering_contact(record))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def offering_contracts_endpoint(request: HttpRequest, offering_id: str) -> JsonResponse:
    try:
        offering = Offering.objects.select_related("vendor").get(offering_id=offering_id)  # type: ignore[attr-defined]
    except Offering.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"offering {offering_id} not found"}, status=404)

    if request.method == "GET":
        identity = resolve_identity_context(request)
        sync_user_directory(identity)
        snapshot = build_policy_snapshot(identity)
        if not can_view_contracts(snapshot):
            return JsonResponse({"error": "forbidden", "reason": "missing contract.read permission"}, status=403)
        items = [
            _serialize_offering_contract(record)
            for record in Contract.objects.select_related("vendor")  # type: ignore[attr-defined]
            .filter(vendor=offering.vendor, offering_id=offering_id)
            .order_by("contract_id")
        ]
        return JsonResponse({"items": items})

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/offerings/{offering_id}/contracts")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        return JsonResponse(
            {"error": "forbidden", "reason": f"missing edit scope for offering LOB {offering.lob}"},
            status=403,
        )

    body = json.loads(request.body.decode("utf-8") or "{}")
    contract_id = str(body.get("contract_id", "")).strip()
    if not contract_id:
        return JsonResponse({"error": "contract_id is required"}, status=400)
    if Contract.objects.filter(contract_id=contract_id).exists():  # type: ignore[attr-defined]
        return JsonResponse({"error": f"contract {contract_id} already exists"}, status=409)

    contract_status = str(body.get("contract_status", "draft")).strip().lower() or "draft"
    if contract_status not in CONTRACT_STATUS_OPTIONS:
        return JsonResponse({"error": f"contract_status must be one of: {', '.join(CONTRACT_STATUS_OPTIONS)}"}, status=400)

    try:
        start_date = _parse_date(str(body.get("start_date", "")))
        end_date = _parse_date(str(body.get("end_date", "")))
        annual_value = _parse_decimal(str(body.get("annual_value", "")))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    record = Contract.objects.create(  # type: ignore[attr-defined]
        contract_id=contract_id,
        vendor=offering.vendor,
        offering_id=offering_id,
        contract_number=str(body.get("contract_number", "")).strip(),
        contract_status=contract_status,
        start_date=start_date,
        end_date=end_date,
        annual_value=annual_value,
        cancelled_flag=bool(body.get("cancelled_flag", False)),
    )
    return JsonResponse(_serialize_offering_contract(record), status=201)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def offering_data_flows_endpoint(request: HttpRequest, offering_id: str) -> JsonResponse:
    try:
        offering = Offering.objects.get(offering_id=offering_id)  # type: ignore[attr-defined]
    except Offering.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"offering {offering_id} not found"}, status=404)

    if request.method == "GET":
        items = [
            _serialize_offering_data_flow(record)
            for record in OfferingDataFlow.objects.filter(offering=offering).order_by("id")  # type: ignore[attr-defined]
        ]
        return JsonResponse({"items": items})

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/offerings/{offering_id}/data-flows")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        return JsonResponse(
            {"error": "forbidden", "reason": f"missing edit scope for offering LOB {offering.lob}"},
            status=403,
        )

    body = json.loads(request.body.decode("utf-8") or "{}")
    flow_name = str(body.get("flow_name", "")).strip()
    source_system = str(body.get("source_system", "")).strip()
    target_system = str(body.get("target_system", "")).strip()
    if not flow_name or not source_system or not target_system:
        return JsonResponse({"error": "flow_name, source_system, and target_system are required"}, status=400)

    direction = str(body.get("direction", "bidirectional")).strip().lower() or "bidirectional"
    if direction not in {"inbound", "outbound", "bidirectional"}:
        return JsonResponse({"error": "direction must be one of: inbound, outbound, bidirectional"}, status=400)

    record = OfferingDataFlow.objects.create(  # type: ignore[attr-defined]
        offering=offering,
        flow_name=flow_name,
        source_system=source_system,
        target_system=target_system,
        direction=direction,
        status=str(body.get("status", "active")).strip() or "active",
        frequency=str(body.get("frequency", "")).strip(),
        notes=str(body.get("notes", "")).strip(),
    )
    return JsonResponse(_serialize_offering_data_flow(record), status=201)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
def offering_data_flow_detail_endpoint(request: HttpRequest, offering_id: str, flow_id: int) -> JsonResponse:
    try:
        offering = Offering.objects.get(offering_id=offering_id)  # type: ignore[attr-defined]
        record = OfferingDataFlow.objects.get(id=flow_id, offering=offering)  # type: ignore[attr-defined]
    except Offering.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"offering {offering_id} not found"}, status=404)
    except OfferingDataFlow.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"data flow {flow_id} not found"}, status=404)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(
        snapshot,
        request.method,
        "/api/v1/offerings/{offering_id}/data-flows/{flow_id}",
    )
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        return JsonResponse(
            {"error": "forbidden", "reason": f"missing edit scope for offering LOB {offering.lob}"},
            status=403,
        )

    if request.method == "DELETE":
        record.delete()
        return JsonResponse({"status": "deleted"}, status=204)

    body = json.loads(request.body.decode("utf-8") or "{}")
    for field_name in ["flow_name", "source_system", "target_system", "status", "frequency", "notes"]:
        if field_name in body:
            setattr(record, field_name, str(body[field_name]).strip())
    if "direction" in body:
        direction = str(body["direction"]).strip().lower()
        if direction not in {"inbound", "outbound", "bidirectional"}:
            return JsonResponse({"error": "direction must be one of: inbound, outbound, bidirectional"}, status=400)
        record.direction = direction
    if not record.flow_name or not record.source_system or not record.target_system:
        return JsonResponse({"error": "flow_name, source_system, and target_system are required"}, status=400)
    record.save()
    return JsonResponse(_serialize_offering_data_flow(record))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def offering_service_tickets_endpoint(request: HttpRequest, offering_id: str) -> JsonResponse:
    try:
        offering = Offering.objects.get(offering_id=offering_id)  # type: ignore[attr-defined]
    except Offering.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"offering {offering_id} not found"}, status=404)

    if request.method == "GET":
        items = [
            _serialize_offering_service_ticket(record)
            for record in OfferingServiceTicket.objects.filter(offering=offering).order_by("-id")  # type: ignore[attr-defined]
        ]
        return JsonResponse({"items": items})

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/offerings/{offering_id}/service-tickets")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        return JsonResponse(
            {"error": "forbidden", "reason": f"missing edit scope for offering LOB {offering.lob}"},
            status=403,
        )

    body = json.loads(request.body.decode("utf-8") or "{}")
    title = str(body.get("title", "")).strip()
    if not title:
        return JsonResponse({"error": "title is required"}, status=400)
    status = str(body.get("status", "open")).strip().lower() or "open"
    priority = str(body.get("priority", "medium")).strip().lower() or "medium"
    if status not in {"open", "in_progress", "closed"}:
        return JsonResponse({"error": "status must be one of: open, in_progress, closed"}, status=400)
    if priority not in {"low", "medium", "high", "critical"}:
        return JsonResponse({"error": "priority must be one of: low, medium, high, critical"}, status=400)

    record = OfferingServiceTicket.objects.create(  # type: ignore[attr-defined]
        offering=offering,
        ticket_system=str(body.get("ticket_system", "")).strip(),
        external_ticket_id=str(body.get("external_ticket_id", "")).strip(),
        title=title,
        status=status,
        priority=priority,
        notes=str(body.get("notes", "")).strip(),
        created_by=identity.user_principal,
    )
    return JsonResponse(_serialize_offering_service_ticket(record), status=201)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
def offering_service_ticket_detail_endpoint(request: HttpRequest, offering_id: str, ticket_id: int) -> JsonResponse:
    try:
        offering = Offering.objects.get(offering_id=offering_id)  # type: ignore[attr-defined]
        record = OfferingServiceTicket.objects.get(id=ticket_id, offering=offering)  # type: ignore[attr-defined]
    except Offering.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"offering {offering_id} not found"}, status=404)
    except OfferingServiceTicket.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"service ticket {ticket_id} not found"}, status=404)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(
        snapshot,
        request.method,
        "/api/v1/offerings/{offering_id}/service-tickets/{ticket_id}",
    )
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        return JsonResponse(
            {"error": "forbidden", "reason": f"missing edit scope for offering LOB {offering.lob}"},
            status=403,
        )

    if request.method == "DELETE":
        record.delete()
        return JsonResponse({"status": "deleted"}, status=204)

    body = json.loads(request.body.decode("utf-8") or "{}")
    for field_name in ["ticket_system", "external_ticket_id", "title", "notes"]:
        if field_name in body:
            setattr(record, field_name, str(body[field_name]).strip())
    if "status" in body:
        status = str(body["status"]).strip().lower()
        if status not in {"open", "in_progress", "closed"}:
            return JsonResponse({"error": "status must be one of: open, in_progress, closed"}, status=400)
        record.status = status
    if "priority" in body:
        priority = str(body["priority"]).strip().lower()
        if priority not in {"low", "medium", "high", "critical"}:
            return JsonResponse({"error": "priority must be one of: low, medium, high, critical"}, status=400)
        record.priority = priority
    if not record.title:
        return JsonResponse({"error": "title is required"}, status=400)
    record.save()
    return JsonResponse(_serialize_offering_service_ticket(record))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def offering_documents_endpoint(request: HttpRequest, offering_id: str) -> JsonResponse:
    try:
        offering = Offering.objects.get(offering_id=offering_id)  # type: ignore[attr-defined]
    except Offering.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"offering {offering_id} not found"}, status=404)

    if request.method == "GET":
        items = [
            _serialize_offering_document(record)
            for record in OfferingDocument.objects.filter(offering=offering).order_by("-id")  # type: ignore[attr-defined]
        ]
        return JsonResponse({"items": items})

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/offerings/{offering_id}/documents")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        return JsonResponse(
            {"error": "forbidden", "reason": f"missing edit scope for offering LOB {offering.lob}"},
            status=403,
        )

    body = json.loads(request.body.decode("utf-8") or "{}")
    doc_title = str(body.get("doc_title", "")).strip()
    doc_url = str(body.get("doc_url", "")).strip()
    if not doc_title or not doc_url:
        return JsonResponse({"error": "doc_title and doc_url are required"}, status=400)

    record = OfferingDocument.objects.create(  # type: ignore[attr-defined]
        offering=offering,
        doc_title=doc_title,
        doc_url=doc_url,
        doc_type=str(body.get("doc_type", "")).strip(),
        owner_principal=str(body.get("owner_principal", identity.user_principal)).strip() or identity.user_principal,
        tags=str(body.get("tags", "")).strip(),
        notes=str(body.get("notes", "")).strip(),
        is_active=bool(body.get("is_active", True)),
    )
    return JsonResponse(_serialize_offering_document(record), status=201)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
def offering_document_detail_endpoint(request: HttpRequest, offering_id: str, document_id: int) -> JsonResponse:
    try:
        offering = Offering.objects.get(offering_id=offering_id)  # type: ignore[attr-defined]
        record = OfferingDocument.objects.get(id=document_id, offering=offering)  # type: ignore[attr-defined]
    except Offering.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"offering {offering_id} not found"}, status=404)
    except OfferingDocument.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"document {document_id} not found"}, status=404)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(
        snapshot,
        request.method,
        "/api/v1/offerings/{offering_id}/documents/{document_id}",
    )
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        return JsonResponse(
            {"error": "forbidden", "reason": f"missing edit scope for offering LOB {offering.lob}"},
            status=403,
        )

    if request.method == "DELETE":
        record.delete()
        return JsonResponse({"status": "deleted"}, status=204)

    body = json.loads(request.body.decode("utf-8") or "{}")
    for field_name in ["doc_title", "doc_url", "doc_type", "owner_principal", "tags", "notes"]:
        if field_name in body:
            setattr(record, field_name, str(body[field_name]).strip())
    if "is_active" in body:
        record.is_active = bool(body["is_active"])
    if not record.doc_title or not record.doc_url:
        return JsonResponse({"error": "doc_title and doc_url are required"}, status=400)
    record.save()
    return JsonResponse(_serialize_offering_document(record))


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def offering_program_profile_endpoint(request: HttpRequest, offering_id: str) -> JsonResponse:
    try:
        offering = Offering.objects.get(offering_id=offering_id)  # type: ignore[attr-defined]
    except Offering.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"offering {offering_id} not found"}, status=404)

    record, _ = OfferingProgramProfile.objects.get_or_create(offering=offering)  # type: ignore[attr-defined]
    if request.method == "GET":
        return JsonResponse(_serialize_offering_program_profile(record))

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "PATCH", "/api/v1/offerings/{offering_id}/program-profile")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        return JsonResponse(
            {"error": "forbidden", "reason": f"missing edit scope for offering LOB {offering.lob}"},
            status=403,
        )

    body = json.loads(request.body.decode("utf-8") or "{}")
    for field_name in [
        "internal_owner",
        "vendor_success_manager",
        "data_residency",
        "compliance_tags",
        "roadmap_notes",
    ]:
        if field_name in body:
            setattr(record, field_name, str(body[field_name]).strip())

    try:
        if "sla_target_pct" in body:
            raw = str(body["sla_target_pct"]).strip()
            record.sla_target_pct = Decimal(raw) if raw else None
        if "rto_hours" in body:
            raw = str(body["rto_hours"]).strip()
            record.rto_hours = int(raw) if raw else None
        if "budget_annual" in body:
            raw = str(body["budget_annual"]).strip()
            record.budget_annual = Decimal(raw) if raw else None
    except (ValueError, InvalidOperation):
        return JsonResponse({"error": "invalid numeric value in profile fields"}, status=400)

    record.save()
    return JsonResponse(_serialize_offering_program_profile(record))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def offering_entitlements_endpoint(request: HttpRequest, offering_id: str) -> JsonResponse:
    try:
        offering = Offering.objects.get(offering_id=offering_id)  # type: ignore[attr-defined]
    except Offering.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"offering {offering_id} not found"}, status=404)

    if request.method == "GET":
        items = [
            _serialize_offering_entitlement(record)
            for record in OfferingEntitlement.objects.filter(offering=offering).order_by("id")  # type: ignore[attr-defined]
        ]
        return JsonResponse({"items": items})

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/offerings/{offering_id}/entitlements")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        return JsonResponse(
            {"error": "forbidden", "reason": f"missing edit scope for offering LOB {offering.lob}"},
            status=403,
        )

    body = json.loads(request.body.decode("utf-8") or "{}")
    entitlement_name = str(body.get("entitlement_name", "")).strip()
    if not entitlement_name:
        return JsonResponse({"error": "entitlement_name is required"}, status=400)

    purchased_units = int(body.get("purchased_units", 0) or 0)
    assigned_units = int(body.get("assigned_units", 0) or 0)
    if purchased_units < 0 or assigned_units < 0:
        return JsonResponse({"error": "purchased_units and assigned_units must be non-negative"}, status=400)
    if assigned_units > purchased_units:
        return JsonResponse({"error": "assigned_units cannot exceed purchased_units"}, status=400)

    try:
        renewal_date = _parse_date(str(body.get("renewal_date", "")))
        true_up_date = _parse_date(str(body.get("true_up_date", "")))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    record = OfferingEntitlement.objects.create(  # type: ignore[attr-defined]
        offering=offering,
        entitlement_name=entitlement_name,
        license_type=str(body.get("license_type", "")).strip(),
        purchased_units=purchased_units,
        assigned_units=assigned_units,
        renewal_date=renewal_date,
        true_up_date=true_up_date,
        notes=str(body.get("notes", "")).strip(),
    )
    return JsonResponse(_serialize_offering_entitlement(record), status=201)


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
def offering_entitlement_detail_endpoint(request: HttpRequest, offering_id: str, entitlement_id: int) -> JsonResponse:
    try:
        offering = Offering.objects.get(offering_id=offering_id)  # type: ignore[attr-defined]
        record = OfferingEntitlement.objects.get(id=entitlement_id, offering=offering)  # type: ignore[attr-defined]
    except Offering.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"offering {offering_id} not found"}, status=404)
    except OfferingEntitlement.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"entitlement {entitlement_id} not found"}, status=404)

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(
        snapshot,
        request.method,
        "/api/v1/offerings/{offering_id}/entitlements/{entitlement_id}",
    )
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)
    if is_scope_restricted(snapshot) and not has_lob_scope(snapshot, offering.lob, minimum_level="edit"):
        return JsonResponse(
            {"error": "forbidden", "reason": f"missing edit scope for offering LOB {offering.lob}"},
            status=403,
        )

    if request.method == "DELETE":
        record.delete()
        return JsonResponse({"status": "deleted"}, status=204)

    body = json.loads(request.body.decode("utf-8") or "{}")
    for field_name in ["entitlement_name", "license_type", "notes"]:
        if field_name in body:
            setattr(record, field_name, str(body[field_name]).strip())
    try:
        if "purchased_units" in body:
            record.purchased_units = int(body["purchased_units"])
        if "assigned_units" in body:
            record.assigned_units = int(body["assigned_units"])
    except ValueError:
        return JsonResponse({"error": "purchased_units and assigned_units must be integers"}, status=400)
    if record.purchased_units < 0 or record.assigned_units < 0:
        return JsonResponse({"error": "purchased_units and assigned_units must be non-negative"}, status=400)
    if record.assigned_units > record.purchased_units:
        return JsonResponse({"error": "assigned_units cannot exceed purchased_units"}, status=400)

    try:
        if "renewal_date" in body:
            record.renewal_date = _parse_date(str(body["renewal_date"]))
        if "true_up_date" in body:
            record.true_up_date = _parse_date(str(body["true_up_date"]))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if not record.entitlement_name:
        return JsonResponse({"error": "entitlement_name is required"}, status=400)
    record.save()
    return JsonResponse(_serialize_offering_entitlement(record))
