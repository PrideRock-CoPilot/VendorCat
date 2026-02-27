from __future__ import annotations

from django.db import models


class ReportRun(models.Model):
    report_run_id = models.CharField(max_length=36, primary_key=True)
    report_code = models.CharField(max_length=128, db_index=True, default="")
    report_type = models.CharField(max_length=32, default="")
    report_name = models.CharField(max_length=255, default="")
    report_format = models.CharField(max_length=16, default="preview")
    status = models.CharField(max_length=16, default="queued")
    triggered_by = models.CharField(max_length=255, default="")
    scheduled_time = models.DateTimeField()
    started_time = models.DateTimeField(null=True, blank=True)
    completed_time = models.DateTimeField(null=True, blank=True)
    row_count = models.IntegerField(default=0)
    file_path = models.CharField(max_length=512, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    filters_json = models.TextField(default="{}")
    warnings_json = models.TextField(default="[]")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "reports"
        indexes = [
            models.Index(fields=["report_code", "triggered_by"]),
            models.Index(fields=["status", "scheduled_time"]),
        ]


class ReportEmailRequestRecord(models.Model):
    run_id = models.CharField(max_length=36)
    email_to_csv = models.TextField()
    requested_by = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "reports"
        indexes = [
            models.Index(fields=["run_id", "created_at"]),
        ]
