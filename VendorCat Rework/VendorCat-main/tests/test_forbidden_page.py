from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.core.runtime import get_config, get_repo


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, isolated_local_db: Path) -> TestClient:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    return TestClient(app)


def test_non_api_forbidden_renders_html_page(client: TestClient) -> None:
    response = client.post(
        "/help/report?as_user=bob.smith@example.com",
        data={
            "issue_title": "test",
            "issue_description": "test",
            "return_to": "/help",
        },
    )
    assert response.status_code == 403
    assert "Access Denied" in response.text
    assert "Ah ah ah, access denied." in response.text
    assert "magic word" in response.text
    assert "/help/report" in response.text
