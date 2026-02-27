from __future__ import annotations

from django.urls import path

from apps.help_center import views

urlpatterns = [
    path("", views.index, name="help-home"),
    path("<slug:slug>", views.article_page, name="help-article-page"),
]
