from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import IntegrityError, models
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator

from apps.contracts.constants import CONTRACT_STATUS_OPTIONS
from apps.contracts.models import Contract
from apps.core.contracts.identity import resolve_identity_context
from apps.core.services.permission_registry import authorize_mutation
from apps.identity.services import build_policy_snapshot, sync_user_directory
from apps.vendors.models import Vendor


def _normalize_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in CONTRACT_STATUS_OPTIONS:
        raise ValueError(f"contract_status must be one of: {', '.join(CONTRACT_STATUS_OPTIONS)}")
    return normalized


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


def _serialize_contract(record: Contract) -> dict[str, str | bool]:
    return {
        "contract_id": record.contract_id,
        "vendor_id": record.vendor.vendor_id,
        "offering_id": record.offering_id,
        "contract_number": record.contract_number,
        "contract_status": record.contract_status,
        "start_date": record.start_date.isoformat() if record.start_date else "",
        "end_date": record.end_date.isoformat() if record.end_date else "",
        "annual_value": record.annual_value_display,
        "cancelled_flag": record.cancelled_flag,
    }


@require_http_methods(["GET"])
def contract_list_page(request: HttpRequest) -> HttpResponse:
    """Render contracts list page with filtering and pagination."""
    queryset = Contract.objects.select_related("vendor").order_by("-updated_at")
    
    # Apply filters
    search_query = request.GET.get("q", "").strip()
    if search_query:
        queryset = queryset.filter(
            models.Q(contract_id__icontains=search_query) |
            models.Q(contract_number__icontains=search_query)
        )
    
    status = request.GET.get("status", "").strip()
    if status and status in CONTRACT_STATUS_OPTIONS:
        queryset = queryset.filter(contract_status=status)
    
    # Pagination
    paginator = Paginator(queryset, 25)
    page_num = request.GET.get("page", 1)
    page = paginator.get_page(page_num)
    
    return render(
        request,
        "contracts/index.html",
        {
            "items": page.object_list,
            "page": page,
            "paginator": paginator,
            "search_query": search_query,
        },
    )


@require_http_methods(["GET"])
def contract_detail_page(request: HttpRequest, contract_id: str) -> HttpResponse:
    """Render contract detail page."""
    contract = get_object_or_404(Contract.objects.select_related("vendor"), contract_id=contract_id)

    return render(
        request,
        "contracts/detail.html",
        {
            "contract": contract,
        },
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def vendor_contracts_endpoint(request: HttpRequest, vendor_id: str) -> JsonResponse:
    try:
        vendor = Vendor.objects.get(vendor_id=vendor_id)  # type: ignore[attr-defined]
    except Vendor.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"vendor {vendor_id} not found"}, status=404)

    if request.method == "GET":
        items = [
            _serialize_contract(record)
            for record in Contract.objects.filter(vendor=vendor).order_by("contract_id")  # type: ignore[attr-defined]
        ]
        return JsonResponse({"items": items})

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "POST", "/api/v1/vendors/{vendor_id}/contracts")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    contract_id = str(body.get("contract_id", "")).strip()
    contract_number = str(body.get("contract_number", "")).strip()
    offering_id = str(body.get("offering_id", "")).strip()
    contract_status = str(body.get("contract_status", "draft")).strip() or "draft"
    start_date_raw = str(body.get("start_date", "")).strip()
    end_date_raw = str(body.get("end_date", "")).strip()
    annual_value_raw = str(body.get("annual_value", "")).strip()
    cancelled_flag = bool(body.get("cancelled_flag", False))

    if not contract_id:
        return JsonResponse({"error": "contract_id is required"}, status=400)

    try:
        contract_status = _normalize_status(contract_status)
        start_date = _parse_date(start_date_raw)
        end_date = _parse_date(end_date_raw)
        annual_value = _parse_decimal(annual_value_raw)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if Contract.objects.filter(contract_id=contract_id).exists():  # type: ignore[attr-defined]
        return JsonResponse({"error": f"contract {contract_id} already exists"}, status=409)

    try:
        record = Contract.objects.create(
            contract_id=contract_id,
            vendor=vendor,
            offering_id=offering_id,
            contract_number=contract_number,
            contract_status=contract_status,
            start_date=start_date,
            end_date=end_date,
            annual_value=annual_value,
            cancelled_flag=cancelled_flag,
        )  # type: ignore[attr-defined]
    except IntegrityError:
        return JsonResponse({"error": f"contract {contract_id} already exists"}, status=409)

    return JsonResponse(_serialize_contract(record), status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
def contract_detail_endpoint(request: HttpRequest, contract_id: str) -> JsonResponse:
    try:
        record = Contract.objects.select_related("vendor").get(contract_id=contract_id)  # type: ignore[attr-defined]
    except Contract.DoesNotExist:  # type: ignore[attr-defined]
        return JsonResponse({"error": f"contract {contract_id} not found"}, status=404)

    if request.method == "GET":
        return JsonResponse(_serialize_contract(record))

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    snapshot = build_policy_snapshot(identity)
    decision = authorize_mutation(snapshot, "PATCH", "/api/v1/contracts/{contract_id}")
    if not decision.allowed:
        return JsonResponse({"error": "forbidden", "reason": decision.reason}, status=403)

    body = json.loads(request.body.decode("utf-8") or "{}")
    updated = False
    for field_name in [
        "contract_number",
        "offering_id",
        "contract_status",
        "start_date",
        "end_date",
        "annual_value",
        "cancelled_flag",
    ]:
        if field_name in body:
            value = body[field_name]
            try:
                if field_name == "contract_status":
                    value = _normalize_status(str(value))
                if field_name in {"start_date", "end_date"}:
                    value = _parse_date(str(value))
                if field_name == "annual_value":
                    value = _parse_decimal(str(value))
                if field_name in {"contract_number", "offering_id"}:
                    value = str(value).strip()
                if field_name == "cancelled_flag":
                    value = bool(value)
            except ValueError as exc:
                return JsonResponse({"error": str(exc)}, status=400)
            setattr(record, field_name, value)
            updated = True

    if updated:
        record.save()

    return JsonResponse(_serialize_contract(record))


# ===== HTML Pages (UI Views) =====

@require_http_methods(["GET", "POST"])
def contract_form_page(request: HttpRequest, contract_id: str | None = None) -> HttpResponse:
    """Render contract form page (create or edit)."""
    contract = None
    form_errors = {}
    
    if contract_id:
        contract = get_object_or_404(Contract, contract_id=contract_id)
    
    if request.method == "POST":
        # Check permissions
        identity = resolve_identity_context(request)
        sync_user_directory(identity)
        snapshot = build_policy_snapshot(identity)
        decision = authorize_mutation(snapshot, "POST" if not contract else "PATCH", "/api/v1/contracts")
        if not decision.allowed:
            messages.error(request, f"Permission denied: {decision.reason}")
            if contract:
                return redirect(f"/contracts/{contract.contract_id}")
            return redirect("/contracts")
        
        # Extract form data
        contract_id_val = request.POST.get("contract_id", "").strip()
        contract_number = request.POST.get("contract_number", "").strip()
        vendor_id = request.POST.get("vendor_id", "").strip()
        contract_status = request.POST.get("contract_status", "").strip()
        start_date_str = request.POST.get("start_date", "").strip()
        end_date_str = request.POST.get("end_date", "").strip()
        annual_value_str = request.POST.get("annual_value", "").strip()
        cancelled_flag = request.POST.get("cancelled_flag") == "on"
        
        # Validation
        if not contract_id_val:
            form_errors["contract_id"] = ["Contract ID is required"]
        if not vendor_id:
            form_errors["vendor_id"] = ["Vendor is required"]
        
        # Parse dates and decimal
        start_date = None
        if start_date_str:
            try:
                start_date = _parse_date(start_date_str)
            except ValueError as e:
                form_errors["start_date"] = [str(e)]
        
        end_date = None
        if end_date_str:
            try:
                end_date = _parse_date(end_date_str)
            except ValueError as e:
                form_errors["end_date"] = [str(e)]
        
        annual_value = None
        if annual_value_str:
            try:
                annual_value = _parse_decimal(annual_value_str)
            except ValueError as e:
                form_errors["annual_value"] = [str(e)]
        
        try:
            contract_status = _normalize_status(contract_status) if contract_status else "draft"
        except ValueError as e:
            form_errors["contract_status"] = [str(e)]
        
        if form_errors:
            return render(
                request,
                "contracts/form.html",
                {
                    "contract": contract,
                    "form_errors": form_errors,
                },
            )
        
        # Verify vendor exists
        try:
            vendor = Vendor.objects.get(vendor_id=vendor_id)
        except Vendor.DoesNotExist:
            form_errors["vendor_id"] = ["Vendor not found"]
            return render(
                request,
                "contracts/form.html",
                {
                    "contract": contract,
                    "form_errors": form_errors,
                },
            )
        
        # Create or update
        if contract:
            # Update existing
            contract.contract_number = contract_number
            contract.vendor = vendor
            contract.contract_status = contract_status
            contract.start_date = start_date
            contract.end_date = end_date
            contract.annual_value = annual_value
            contract.cancelled_flag = cancelled_flag
            contract.save()
            messages.success(request, f"Contract {contract.contract_id} updated successfully")
            return redirect(f"/contracts/{contract.contract_id}")
        else:
            # Create new
            if Contract.objects.filter(contract_id=contract_id_val).exists():
                form_errors["contract_id"] = ["Contract ID already exists"]
                return render(
                    request,
                    "contracts/form.html",
                    {
                        "contract": None,
                        "form_errors": form_errors,
                    },
                )
            
            try:
                contract = Contract.objects.create(
                    contract_id=contract_id_val,
                    vendor=vendor,
                    contract_number=contract_number,
                    contract_status=contract_status,
                    start_date=start_date,
                    end_date=end_date,
                    annual_value=annual_value,
                    cancelled_flag=cancelled_flag,
                )
                messages.success(request, f"Contract {contract_id_val} created successfully")
                return redirect(f"/contracts/{contract.contract_id}")
            except IntegrityError:
                form_errors["contract_id"] = ["Contract ID already exists"]
                return render(
                    request,
                    "contracts/form.html",
                    {
                        "contract": None,
                        "form_errors": form_errors,
                    },
                )
    
    return render(
        request,
        "contracts/form.html",
        {
            "contract": contract,
            "form_errors": form_errors,
        },
    )
