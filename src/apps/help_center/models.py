from __future__ import annotations

from django.db import models


class HelpArticle(models.Model):
    article_id = models.CharField(max_length=36, primary_key=True)
    slug = models.SlugField(max_length=128, unique=True, default="")
    title = models.CharField(max_length=255, default="")
    markdown_body = models.TextField(default="")
    rendered_html = models.TextField(default="")
    published = models.BooleanField(default=False)

    # Backward-compatible fields retained while rebuilding contracts.
    article_title = models.CharField(max_length=255, default="")
    category = models.CharField(max_length=32)
    content_markdown = models.TextField(default="")
    is_published = models.BooleanField(default=False)
    view_count = models.IntegerField(default=0)
    author = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "help_center"
        indexes = [
            models.Index(fields=["slug", "published"]),
            models.Index(fields=["category", "is_published"]),
            models.Index(fields=["created_at"]),
        ]


class HelpFeedback(models.Model):
    slug = models.SlugField(max_length=128)
    rating = models.CharField(max_length=8)
    comment = models.TextField(blank=True, default="")
    submitted_by = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "help_center"
        indexes = [
            models.Index(fields=["slug", "created_at"]),
        ]


class HelpIssue(models.Model):
    slug = models.SlugField(max_length=128)
    issue_text = models.TextField()
    screenshot_path = models.CharField(max_length=512, blank=True, default="")
    submitted_by = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "help_center"
        indexes = [
            models.Index(fields=["slug", "created_at"]),
        ]
