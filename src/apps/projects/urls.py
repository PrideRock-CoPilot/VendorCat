from __future__ import annotations

from django.urls import path

from apps.projects import views

urlpatterns = [
    # HTML Pages
    path("", views.project_list_page, name="projects-list"),
    path("new", views.project_form_page, name="projects-create"),
    path("<str:project_id>", views.project_detail_page, name="projects-detail"),
    path("<str:project_id>/edit", views.project_form_page, name="projects-edit"),
]
