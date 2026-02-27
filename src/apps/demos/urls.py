from __future__ import annotations

from django.urls import path

from apps.demos import views

urlpatterns = [
    path("", views.index, name="demos-index"),
    path("<str:demo_id>", views.demo_detail_page, name="demo-detail"),
]
