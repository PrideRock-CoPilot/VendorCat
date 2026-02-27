from __future__ import annotations

from django.urls import path

from apps.identity import views

urlpatterns = [
    path("queue", views.pending_approvals_queue_page, name="pending-approvals-queue-page"),
]
