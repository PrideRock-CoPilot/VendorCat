from __future__ import annotations

from django.urls import path

from apps.reports import views

urlpatterns = [
    path("", views.index, name="reports-home"),
    path("partials/runs", views.report_runs_partial, name="reports-runs-partial"),
    path("<str:run_id>", views.report_detail_page, name="reports-detail"),
]
