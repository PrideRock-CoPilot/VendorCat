from __future__ import annotations

from django.db import models

HELP_ARTICLE_CATEGORIES = ["getting_started", "faq", "troubleshooting", "best_practices", "api_reference"]


class HelpArticle(models.Model):
    article_id = models.CharField(max_length=36, primary_key=True)
    article_title = models.CharField(max_length=255)
    category = models.CharField(max_length=32)
    content_markdown = models.TextField()
    is_published = models.BooleanField(default=False)
    view_count = models.IntegerField(default=0)
    author = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "help"
        indexes = [
            models.Index(fields=["category", "is_published"]),
            models.Index(fields=["created_at"]),
        ]
