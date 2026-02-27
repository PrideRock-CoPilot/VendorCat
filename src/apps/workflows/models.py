from __future__ import annotations

from django.db import models


class WorkflowDecision(models.Model):
    """Rebuild workflow decision tracking model."""

    decision_id = models.CharField(max_length=255, unique=True, primary_key=False)
    workflow_name = models.CharField(max_length=255)
    submitted_by = models.CharField(max_length=255)
    status = models.CharField(max_length=50, default="pending")
    action = models.CharField(max_length=100)
    context_json = models.TextField(blank=True, default="{}")  # JSON object
    reviewed_by = models.CharField(max_length=255, blank=True, default="")
    review_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "workflows"

    def __str__(self) -> str:
        return f"WorkflowDecision({self.decision_id})"
