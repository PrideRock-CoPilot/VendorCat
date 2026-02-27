from __future__ import annotations

from django.urls import path

from apps.identity import views

urlpatterns = [
    path("", views.home, name="identity-context"),
]
