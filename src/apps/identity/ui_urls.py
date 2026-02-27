from __future__ import annotations

from django.urls import path

from apps.identity import views

urlpatterns = [
    path("", views.access_home_page, name="access-home"),
    path("requests", views.access_request_page, name="access-request-page"),
    path("requests/review", views.access_review_page, name="access-review-page"),
    path("terms", views.terms_acceptance_page, name="access-terms"),
    path("bootstrap-first-admin", views.bootstrap_first_admin_page, name="access-bootstrap-first-admin"),
]
