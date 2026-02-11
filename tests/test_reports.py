from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.services import get_config, get_repo


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, isolated_local_db: Path) -> TestClient:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    return TestClient(app)


def test_reports_page_loads_for_authorized_user(client: TestClient) -> None:
    response = client.get("/reports")
    assert response.status_code == 200
    assert "Reports" in response.text
    assert "Build custom extracts" in response.text


def test_reports_access_denied_for_viewer(client: TestClient) -> None:
    response = client.get("/reports?as_user=viewer@example.com", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_reports_run_owner_coverage_and_download_csv(client: TestClient) -> None:
    response = client.get(
        "/reports?run=1&report_type=owner_coverage&owner_principal=cloud-platform@example.com&limit=250"
    )
    assert response.status_code == 200
    assert "owner_principal" in response.text
    assert "cloud-platform@example.com" in response.text

    download = client.get(
        "/reports/download?report_type=owner_coverage&owner_principal=cloud-platform@example.com&limit=250"
    )
    assert download.status_code == 200
    assert download.headers.get("content-type", "").startswith("text/csv")
    assert "owner_principal" in download.text
    assert "cloud-platform@example.com" in download.text


def test_reports_email_request(client: TestClient) -> None:
    response = client.post(
        "/reports/email",
        data={
            "report_type": "project_portfolio",
            "search": "Defender",
            "vendor": "all",
            "lifecycle_state": "all",
            "project_status": "all",
            "outcome": "all",
            "owner_principal": "",
            "org": "all",
            "horizon_days": "180",
            "limit": "500",
            "cols": "",
            "email_to": "leadership@example.com",
            "email_subject": "Weekly Project Snapshot",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Email extract request queued." in response.text

