from __future__ import annotations

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncMonth
from datetime import datetime, timedelta
from decimal import Decimal
import json

from apps.vendors.models import Vendor
from apps.projects.models import Project
from apps.contracts.models import Contract
from apps.demos.models import Demo


def home_redirect(request: HttpRequest) -> HttpResponseRedirect:
    return HttpResponseRedirect("/dashboard")


def dashboard(request: HttpRequest) -> HttpResponse:
    # Get filter parameters
    lob_filter = request.GET.get("lob", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    
    # Build base querysets with filters
    vendor_qs = Vendor.objects.all()
    project_qs = Project.objects.all()
    contract_qs = Contract.objects.all()
    demo_qs = Demo.objects.all()
    
    # Apply LOB filter
    if lob_filter:
        vendor_qs = vendor_qs.filter(owner_org_id=lob_filter)
        # Assuming contracts are linked to vendors for LOB filtering
        contract_qs = contract_qs.filter(vendor__owner_org_id=lob_filter)
    
    # Apply date filters
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
            vendor_qs = vendor_qs.filter(created_at__gte=date_from_obj)
            project_qs = project_qs.filter(created_at__gte=date_from_obj)
            contract_qs = contract_qs.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
            vendor_qs = vendor_qs.filter(created_at__lte=date_to_obj)
            project_qs = project_qs.filter(created_at__lte=date_to_obj)
            contract_qs = contract_qs.filter(created_at__lte=date_to_obj)
        except ValueError:
            pass
    
    # Get overall counts
    vendor_count = vendor_qs.count()
    project_count = project_qs.count()
    contract_count = contract_qs.count()
    demo_count = demo_qs.count()
    
    # Vendor distribution by status
    vendor_by_status = list(
        vendor_qs.values("lifecycle_state")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    
    # Vendor distribution by risk tier
    vendor_by_risk = list(
        vendor_qs.values("risk_tier")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    
    # Contract distribution by status
    contract_by_status = list(
        contract_qs.values("contract_status")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    
    # Total contract value and active contracts
    contract_stats = contract_qs.aggregate(
        total_value=Sum("annual_value"),
        active_count=Count("id", filter=Q(contract_status="active"))
    )
    total_contract_value = contract_stats["total_value"] or Decimal("0")
    active_contract_count = contract_stats["active_count"] or 0
    
    # Trend data - vendors created per month (last 6 months)
    six_months_ago = datetime.now() - timedelta(days=180)
    vendor_trend = list(
        Vendor.objects.filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    
    # Project trend - projects created per month (last 6 months)
    project_trend = list(
        Project.objects.filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    
    # Contract value trend per month (last 6 months)
    contract_trend = list(
        Contract.objects.filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(total_value=Sum("annual_value"))
        .order_by("month")
    )
    
    # Get available LOBs for filter dropdown
    available_lobs = list(
        Vendor.objects.values_list("owner_org_id", flat=True)
        .distinct()
        .order_by("owner_org_id")
    )
    
    # Recent activity
    recent_vendors = vendor_qs.order_by("-updated_at")[:5]
    
    # Format data for JavaScript charts
    chart_data = {
        "vendor_by_status": {
            "labels": [item["lifecycle_state"] for item in vendor_by_status],
            "data": [item["count"] for item in vendor_by_status]
        },
        "vendor_by_risk": {
            "labels": [item["risk_tier"] for item in vendor_by_risk],
            "data": [item["count"] for item in vendor_by_risk]
        },
        "contract_by_status": {
            "labels": [item["contract_status"] for item in contract_by_status],
            "data": [item["count"] for item in contract_by_status]
        },
        "vendor_trend": {
            "labels": [item["month"].strftime("%b %Y") for item in vendor_trend],
            "data": [item["count"] for item in vendor_trend]
        },
        "project_trend": {
            "labels": [item["month"].strftime("%b %Y") for item in project_trend],
            "data": [item["count"] for item in project_trend]
        },
        "contract_trend": {
            "labels": [item["month"].strftime("%b %Y") for item in contract_trend],
            "data": [float(item["total_value"] or 0) for item in contract_trend]
        }
    }
    
    return render(
        request,
        "core/dashboard.html",
        {
            "page_title": "Dashboard",
            "vendor_count": vendor_count,
            "project_count": project_count,
            "contract_count": contract_count,
            "demo_count": demo_count,
            "active_contract_count": active_contract_count,
            "total_contract_value": total_contract_value,
            "recent_vendors": recent_vendors,
            "chart_data": json.dumps(chart_data),
            "available_lobs": available_lobs,
            "selected_lob": lob_filter,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


def section_placeholder(request: HttpRequest, section_name: str) -> HttpResponse:
    return render(
        request,
        "shared/section_placeholder.html",
        {
            "page_title": section_name,
            "section_name": section_name,
            "section_message": "This module is scaffolded for parity implementation.",
        },
    )
