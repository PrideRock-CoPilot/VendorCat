from __future__ import annotations

from decimal import Decimal

from django.db import models

from apps.vendors.models import Vendor


class Contract(models.Model):
    contract_id = models.CharField(max_length=128, unique=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="contracts")
    offering_id = models.CharField(max_length=128, blank=True, default="")
    contract_number = models.CharField(max_length=128, blank=True, default="")
    contract_status = models.CharField(max_length=64, default="draft")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    annual_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    cancelled_flag = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def annual_value_display(self) -> str:
        if self.annual_value is None:
            return ""
        return str(Decimal(self.annual_value))
