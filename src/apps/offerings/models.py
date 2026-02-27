from __future__ import annotations

from django.db import models

from apps.vendors.models import Vendor


class Offering(models.Model):
    offering_id = models.CharField(max_length=128, unique=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="offerings")
    offering_name = models.CharField(max_length=255)
    offering_type = models.CharField(max_length=128, blank=True, default="")
    lob = models.CharField(max_length=128, blank=True, default="")
    service_type = models.CharField(max_length=128, blank=True, default="")
    lifecycle_state = models.CharField(max_length=64, default="draft")
    criticality_tier = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OfferingContact(models.Model):
    offering = models.ForeignKey(Offering, on_delete=models.CASCADE, related_name="contacts")
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=128, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OfferingDataFlow(models.Model):
    DIRECTION_OPTIONS = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
        ("bidirectional", "Bidirectional"),
    ]

    offering = models.ForeignKey(Offering, on_delete=models.CASCADE, related_name="data_flows")
    flow_name = models.CharField(max_length=255)
    source_system = models.CharField(max_length=255)
    target_system = models.CharField(max_length=255)
    direction = models.CharField(max_length=32, choices=DIRECTION_OPTIONS, default="bidirectional")
    status = models.CharField(max_length=64, default="active")
    frequency = models.CharField(max_length=64, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OfferingServiceTicket(models.Model):
    STATUS_OPTIONS = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("closed", "Closed"),
    ]
    PRIORITY_OPTIONS = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    offering = models.ForeignKey(Offering, on_delete=models.CASCADE, related_name="service_tickets")
    ticket_system = models.CharField(max_length=128, blank=True, default="")
    external_ticket_id = models.CharField(max_length=128, blank=True, default="")
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=64, choices=STATUS_OPTIONS, default="open")
    priority = models.CharField(max_length=64, choices=PRIORITY_OPTIONS, default="medium")
    notes = models.TextField(blank=True, default="")
    created_by = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OfferingDocument(models.Model):
    offering = models.ForeignKey(Offering, on_delete=models.CASCADE, related_name="documents")
    doc_title = models.CharField(max_length=255)
    doc_url = models.URLField(max_length=1000)
    doc_type = models.CharField(max_length=64, blank=True, default="")
    owner_principal = models.CharField(max_length=255, blank=True, default="")
    tags = models.CharField(max_length=512, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OfferingProgramProfile(models.Model):
    offering = models.OneToOneField(Offering, on_delete=models.CASCADE, related_name="program_profile")
    internal_owner = models.CharField(max_length=255, blank=True, default="")
    vendor_success_manager = models.CharField(max_length=255, blank=True, default="")
    sla_target_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rto_hours = models.IntegerField(null=True, blank=True)
    data_residency = models.CharField(max_length=128, blank=True, default="")
    compliance_tags = models.CharField(max_length=512, blank=True, default="")
    budget_annual = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    roadmap_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OfferingEntitlement(models.Model):
    offering = models.ForeignKey(Offering, on_delete=models.CASCADE, related_name="entitlements")
    entitlement_name = models.CharField(max_length=255)
    license_type = models.CharField(max_length=128, blank=True, default="")
    purchased_units = models.IntegerField(default=0)
    assigned_units = models.IntegerField(default=0)
    renewal_date = models.DateField(null=True, blank=True)
    true_up_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
