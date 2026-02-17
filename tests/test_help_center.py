from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.core.help_validator import validate_help_articles
from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.core.runtime import get_config, get_repo


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, isolated_local_db: Path) -> TestClient:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    return TestClient(app)


def test_help_slug_routing(client: TestClient) -> None:
    response = client.get("/help/add-vendor?as_user=admin@example.com")
    assert response.status_code == 200
    assert "Add a new vendor" in response.text


def test_help_search_ranking(client: TestClient) -> None:
    response = client.get("/help?q=add vendor")
    assert response.status_code == 200
    match = re.search(r'data-help-result-slug="([^"]+)"', response.text)
    assert match is not None
    assert match.group(1) == "add-vendor"


def test_help_markdown_sanitized(client: TestClient) -> None:
    repo = get_repo()
    article_id = repo.create_help_article(
        slug="unsafe-test-article",
        title="Unsafe test article",
        section="Test",
        article_type="guide",
        role_visibility="viewer,editor,admin",
        content_md="Hello <script>alert(1)</script>",
        owned_by="Test",
        actor_user_principal="seed:system",
    )
    assert article_id
    response = client.get("/help/unsafe-test-article")
    assert response.status_code == 200
    assert "<script>" not in response.text


def test_help_feedback_persists(client: TestClient) -> None:
    response = client.post(
        "/help/feedback?as_user=admin@example.com",
        data={
            "article_id": "help-003",
            "article_slug": "add-vendor",
            "was_helpful": "1",
            "comment": "Clear and short",
            "page_path": "/help/add-vendor",
            "return_to": "/help/add-vendor",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    repo = get_repo()
    rows = repo.client.query(
        "SELECT article_slug, was_helpful, comment FROM vendor_help_feedback WHERE article_slug = ?",
        ("add-vendor",),
    )
    assert not rows.empty
    assert str(rows.iloc[0]["article_slug"]) == "add-vendor"


def test_help_content_validator(client: TestClient) -> None:
    repo = get_repo()
    articles = repo.list_help_articles_full()
    errors = validate_help_articles(articles)
    assert not errors
