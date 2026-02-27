from __future__ import annotations

from django.urls import path

from apps.workflows import views

urlpatterns = [
    path("", views.index, name="workflows-index"),
    path("<str:decision_id>", views.workflow_decision_detail_page, name="workflow-decision-detail"),
]
