from __future__ import annotations

from django.urls import path

from apps.imports import views

urlpatterns = [
    path("", views.index, name="imports-index"),
    path("<str:import_job_id>", views.import_job_detail_page, name="import-job-detail"),
]
