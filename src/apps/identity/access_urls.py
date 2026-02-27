from __future__ import annotations

from django.urls import path

from apps.identity import views

urlpatterns = [
    path("requests", views.create_access_request_endpoint, name="access-request-create"),
    path("requests/list", views.list_access_requests_endpoint, name="access-request-list"),
    path("requests/<int:request_id>/review", views.review_access_request_endpoint, name="access-request-review"),
    path("terms/accept", views.accept_terms_endpoint, name="terms-accept"),
    path("bootstrap-first-admin", views.bootstrap_first_admin_endpoint, name="bootstrap-first-admin"),
]
