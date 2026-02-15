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


def test_dashboard_redirects_roleless_user_to_access_request(client: TestClient) -> None:
    response = client.get("/dashboard?as_user=bob.smith@example.com", follow_redirects=False)
    assert response.status_code == 200
    assert "Opening your workspace" in response.text
    assert "splash=1" in response.text
