from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.app import create_app  # noqa: E402
from vendor_catalog_app.web.core.runtime import get_config, get_repo  # noqa: E402
from vendor_catalog_app.web.routers.reports.common import REPORT_TYPES  # noqa: E402


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
    assert "Host and run report views directly in this app" in response.text
    assert "Ready-to-Run Hosted Reports" in response.text
    assert "Open Workspace Designer" in response.text
    assert "Download Power BI Bundle" not in response.text


def test_reports_page_lists_all_ready_to_run_cards(client: TestClient) -> None:
    response = client.get("/reports")
    assert response.status_code == 200
    card_keys = set(re.findall(r'data-ready-report="([^"]+)"', response.text))
    assert len(card_keys) >= 12
    assert card_keys == set(REPORT_TYPES.keys())


def test_reports_page_ready_nav_shows_icons_and_selected_report(client: TestClient) -> None:
    response = client.get("/reports?report_type=contract_renewals")
    assert response.status_code == 200
    assert "reports-ready-shell" in response.text
    assert "reports-ready-nav" in response.text
    assert "reports-ready-main" in response.text
    assert "Apply Slicers" in response.text
    assert "Open Hosted Report" not in response.text
    assert (
        re.search(
            r'class="reports-ready-nav-item selected"[^>]*data-ready-report="contract_renewals"',
            response.text,
        )
        is not None
    )
    nav_item_blocks = re.findall(
        r'<a\s+class="reports-ready-nav-item[^>]*data-ready-report="[^"]+"[^>]*>.*?</a>',
        response.text,
        flags=re.S,
    )
    assert len(nav_item_blocks) == len(REPORT_TYPES)
    assert all("reports-ready-icon tone-" in block for block in nav_item_blocks)


def test_reports_catalog_has_minimum_ready_to_go_reports() -> None:
    assert len(REPORT_TYPES) >= 12
    assert "high_risk_vendor_inventory" in REPORT_TYPES
    assert "active_project_portfolio" in REPORT_TYPES
    assert "renewal_pipeline_90d" in REPORT_TYPES
    assert "demo_selected_only" in REPORT_TYPES
    assert "budget_overruns" in REPORT_TYPES
    assert "open_vendor_warnings" in REPORT_TYPES


def test_reports_workspace_page_loads_for_authorized_user(client: TestClient) -> None:
    response = client.get("/reports/workspace")
    assert response.status_code == 200
    assert "Reports Workspace" in response.text
    assert "Unified Report Catalog" in response.text
    assert "Report Board Designer" in response.text


def test_reports_workspace_board_save_load_delete(client: TestClient) -> None:
    save = client.post(
        "/reports/workspace/boards/save",
        data={
            "board_name": "Ops Weekly",
            "board_id": "",
            "board_json": (
                '{"version":1,"widgets":[{"widget_type":"chart","title":"Ops KPIs","report_type":"vendor_inventory",'
                '"view_mode":"chart","chart_kind":"bar","chart_x":"display_name","chart_y":"total_contract_value",'
                '"search":"","vendor":"all","limit":500}]}'
            ),
        },
        follow_redirects=False,
    )
    assert save.status_code == 303
    assert save.headers["location"].startswith("/reports/workspace?board=ops-weekly")

    loaded = client.get(save.headers["location"])
    assert loaded.status_code == 200
    assert "Saved report board &#39;Ops Weekly&#39;." in loaded.text
    assert "Ops Weekly" in loaded.text
    assert "Ops KPIs" in loaded.text

    delete = client.post(
        "/reports/workspace/boards/delete",
        data={"board_id": "ops-weekly"},
        follow_redirects=True,
    )
    assert delete.status_code == 200
    assert "Report board removed." in delete.text


def test_reports_workspace_board_presentation_and_export_bundle(client: TestClient) -> None:
    save = client.post(
        "/reports/workspace/boards/save",
        data={
            "board_name": "Leadership Packet",
            "board_id": "",
            "board_json": (
                '{"version":1,"widgets":[{"widget_type":"chart","title":"Renewal Snapshot",'
                '"report_type":"contract_renewals","view_mode":"both","chart_kind":"line","chart_x":"renewal_date",'
                '"chart_y":"annual_value","search":"","vendor":"all","limit":500},'
                '{"widget_type":"table","title":"Owner Coverage","report_type":"owner_coverage","view_mode":"table",'
                '"chart_kind":"bar","chart_x":"owner_principal","chart_y":"__row_count__",'
                '"search":"","vendor":"all","limit":250}]}'
            ),
        },
        follow_redirects=False,
    )
    assert save.status_code == 303
    assert save.headers["location"].startswith("/reports/workspace?board=leadership-packet")

    present = client.get("/reports/workspace/present?board=leadership-packet")
    assert present.status_code == 200
    assert "Presentation Mode" in present.text
    assert "Leadership Packet" in present.text
    assert "Renewal Snapshot" in present.text
    assert "Owner Coverage" in present.text
    assert "Open Runner" in present.text

    export = client.get("/reports/workspace/boards/export?board=leadership-packet")
    assert export.status_code == 200
    assert export.headers.get("content-type", "").startswith("application/zip")
    with zipfile.ZipFile(io.BytesIO(export.content), "r") as archive:
        names = set(archive.namelist())
        assert "board_manifest.json" in names
        assert any(name.endswith(".csv") for name in names if name != "board_manifest.json")
        manifest = json.loads(archive.read("board_manifest.json").decode("utf-8"))
    assert manifest["board_id"] == "leadership-packet"
    assert int(manifest["widget_count"]) == 2


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


def test_reports_powerbi_bundle_download_route_removed(client: TestClient) -> None:
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
            "lob": "all",
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


