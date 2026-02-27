from __future__ import annotations

from django.db import models

from apps.vendors.constants import LIFECYCLE_STATES


class Demo(models.Model):
    demo_id = models.CharField(max_length=128, unique=True)
    demo_name = models.CharField(max_length=255)
    demo_type = models.CharField(max_length=64, blank=True, default="")
    demo_outcome = models.CharField(max_length=64, blank=True, default="")
    lifecycle_state = models.CharField(max_length=64, default=LIFECYCLE_STATES[0])
    project_id = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
