from __future__ import annotations

from django.urls import path

from apps.contracts import views

urlpatterns = [
    # HTML Pages
    path("", views.contract_list_page, name="contracts-list"),
    path("new", views.contract_form_page, name="contracts-create"),
    path("<str:contract_id>", views.contract_detail_page, name="contracts-detail"),
    path("<str:contract_id>/edit", views.contract_form_page, name="contracts-edit"),
]
