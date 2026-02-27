from __future__ import annotations

from django.urls import path

from apps.identity import views

urlpatterns = [
    path("queue", views.pending_approvals_queue_endpoint, name="pending-approvals-queue"),
    path("queue/open-next", views.pending_approvals_open_next_endpoint, name="pending-approvals-open-next"),
    path("queue/<int:request_id>/decision", views.pending_approval_decision_endpoint, name="pending-approvals-decision"),
]
