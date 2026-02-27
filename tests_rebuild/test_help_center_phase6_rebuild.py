from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


ADMIN_HEADERS = {
    "HTTP_X_FORWARDED_USER": "admin@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_admin",
}
USER_HEADERS = {
    "HTTP_X_FORWARDED_USER": "user@example.com",
    "HTTP_X_FORWARDED_GROUPS": "authenticated",
}
VIEWER_HEADERS = {
    "HTTP_X_FORWARDED_USER": "viewer@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_viewer",
}


def _seed_article(client: Client) -> str:
    response = client.post(
        "/api/v1/help/articles",
        data=json.dumps(
            {
                "slug": "getting-started",
                "title": "Getting Started",
                "category": "getting_started",
                "markdown_body": "# Welcome\n\nUse **VendorCatalog** safely. <script>alert(1)</script>",
                "published": True,
            }
        ),
        content_type="application/json",
        **ADMIN_HEADERS,
    )
    assert response.status_code == 201
    return response.json()["slug"]


def test_help_article_get_and_search_with_sanitization() -> None:
    client = Client()
    slug = _seed_article(client)

    get_response = client.get(f"/api/v1/help/articles/{slug}", **VIEWER_HEADERS)
    assert get_response.status_code == 200
    payload = get_response.json()
    assert payload["slug"] == slug
    assert "<script>" not in payload["rendered_html"]

    search_response = client.get("/api/v1/help/search?q=vendorcatalog", **VIEWER_HEADERS)
    assert search_response.status_code == 200
    items = search_response.json()["items"]
    assert items
    assert items[0]["slug"] == slug


def test_help_feedback_and_issue_persist_with_permissions() -> None:
    client = Client()
    slug = _seed_article(client)

    feedback_response = client.post(
        "/api/v1/help/feedback",
        data=json.dumps(
            {
                "slug": slug,
                "rating": "up",
                "comment": "Useful article",
            }
        ),
        content_type="application/json",
        **USER_HEADERS,
    )
    assert feedback_response.status_code == 201

    issue_response = client.post(
        "/api/v1/help/issues",
        data=json.dumps(
            {
                "slug": slug,
                "issue_text": "Screenshot is outdated",
                "screenshot_path": "screenshots/help-1.png",
            }
        ),
        content_type="application/json",
        **USER_HEADERS,
    )
    assert issue_response.status_code == 201

    denied = client.post(
        "/api/v1/help/issues",
        data=json.dumps(
            {
                "slug": slug,
                "issue_text": "Should fail",
            }
        ),
        content_type="application/json",
    )
    assert denied.status_code == 403


def test_help_center_pages_render_and_article_page_is_sanitized() -> None:
    client = Client()
    slug = _seed_article(client)

    list_page = client.get("/help/")
    assert list_page.status_code == 200
    assert b"Help Center" in list_page.content

    detail_page = client.get(f"/help/{slug}")
    assert detail_page.status_code == 200
    body = detail_page.content.decode("utf-8")
    assert "<script>alert(1)</script>" not in body
    assert "Getting Started" in body
