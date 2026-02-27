from __future__ import annotations

from django.db import models


class ImportJob(models.Model):
    """Rebuild import job tracking model."""

    import_job_id = models.CharField(max_length=255, unique=True, primary_key=False)
    source_system = models.CharField(max_length=100)
    source_object = models.CharField(max_length=255, blank=True, default="")
    file_name = models.CharField(max_length=255)
    file_format = models.CharField(max_length=50, blank=True, default="")
    status = models.CharField(max_length=50, default="submitted")
    submitted_by = models.CharField(max_length=255)
    mapping_profile_id = models.CharField(max_length=255, blank=True, default="")
    row_count = models.IntegerField(default=0)
    staged_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    review_note = models.TextField(blank=True, default="")
    workflow_context_json = models.TextField(blank=True, default="{}")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "imports"

    def __str__(self) -> str:
        return f"ImportJob({self.import_job_id})"


class MappingProfile(models.Model):
    """Rebuild mapping profile for import field mapping."""

    profile_id = models.CharField(max_length=255, unique=True, primary_key=False)
    profile_name = models.CharField(max_length=255)
    layout_key = models.CharField(max_length=100, default="vendors")
    file_format = models.CharField(max_length=50)
    source_fields_json = models.TextField(blank=True, default="[]")  # JSON array
    source_target_mapping_json = models.TextField(blank=True, default="{}")  # JSON object
    created_by = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "imports"

    def __str__(self) -> str:
        return f"MappingProfile({self.profile_id})"
