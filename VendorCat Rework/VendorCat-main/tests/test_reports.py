from __future__ import annotations

import io
import json
import sys
import zipfile
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


def test_reports_page_loads_for_authorized_user(client: TestClient) -> None:
    response = client.get("/reports")
    assert response.status_code == 200
    assert "Reports" in response.text
    assert "Build custom extracts" in response.text


def test_reports_access_denied_for_viewer(client: TestClient) -> None:
    response = client.get("/reports?as_user=bob.smith@example.com", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/access/request"


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


def test_reports_graph_view_renders(client: TestClient) -> None:
    response = client.get(
        "/reports?run=1&report_type=vendor_inventory&view_mode=chart&chart_kind=bar&chart_x=risk_tier&chart_y=__row_count__&limit=250"
    )
    assert response.status_code == 200
    assert "Graph View" in response.text
    assert "bar-row" in response.text


def test_reports_powerbi_bundle_download_removed(client: TestClient) -> None:
    response = client.get(
        "/reports/download/powerbi?report_type=owner_coverage&owner_principal=cloud-platform@example.com&chart_x=owner_principal&chart_y=__row_count__&limit=250"
    )
    assert response.status_code == 404


def test_reports_databricks_native_links_and_embed(
    monkeypatch: pytest.MonkeyPatch,
    isolated_local_db: Path,
) -> None:
    monkeypatch.setenv(
        "TVENDOR_DATABRICKS_REPORTS_JSON",
        json.dumps(
            [
                {
                    "id": "ops-dashboard",
                    "label": "Ops Dashboard",
                    "description": "Operational KPIs in Databricks SQL.",
                    "url": "https://dbc-123.cloud.databricks.com/sql/dashboardsv3/ops-dashboard",
                    "allow_embed": True,
                }
            ]
        ),
    )
    monkeypatch.setenv("TVENDOR_DATABRICKS_REPORTS_ALLOWED_HOSTS", "dbc-123.cloud.databricks.com")
    monkeypatch.setenv("TVENDOR_DATABRICKS_REPORTS_ALLOW_EMBED", "true")

    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)

    listing = client.get("/reports")
    assert listing.status_code == 200
    assert "Databricks Native Reports" in listing.text
    assert "Ops Dashboard" in listing.text
    assert "Open in Databricks" in listing.text

    embedded = client.get("/reports?dbx_report=ops-dashboard")
    assert embedded.status_code == 200
    assert "Embedded: Ops Dashboard" in embedded.text
    assert "<iframe" in embedded.text
    assert "sql/dashboardsv3/ops-dashboard" in embedded.text


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
            "business_unit": "all",
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


