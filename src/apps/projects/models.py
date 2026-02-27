from __future__ import annotations

from django.db import models


class Project(models.Model):
    project_id = models.CharField(max_length=128, unique=True)
    project_name = models.CharField(max_length=255)
    owner_principal = models.CharField(max_length=255)
    lifecycle_state = models.CharField(max_length=64, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
