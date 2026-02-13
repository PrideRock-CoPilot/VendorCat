from __future__ import annotations

import re
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


def test_imports_bulk_insert_vendors_creates_multiple_records(client: TestClient) -> None:
    csv_payload = (
        "vendor_id,legal_name,display_name,owner_org_id,lifecycle_state,risk_tier,support_contact_name,"
        "support_contact_type,support_email,support_phone\n"
        ",Bulk Import Vendor One LLC,Bulk Import Vendor One,IT-ENT,draft,low,Owner One,business,"
        "owner.one@example.com,555-0101\n"
        ",Bulk Import Vendor Two LLC,Bulk Import Vendor Two,FIN-OPS,draft,medium,Owner Two,support,"
        "owner.two@example.com,555-0102\n"
    )

    preview_response = client.post(
        "/imports/preview",
        data={"layout": "vendors"},
        files={"file": ("vendors.csv", csv_payload, "text/csv")},
        follow_redirects=True,
    )
    assert preview_response.status_code == 200
    assert "Bulk Import Vendor One" in preview_response.text
    assert "Bulk Import Vendor Two" in preview_response.text

    token_match = re.search(r'name="preview_token" value="([^"]+)"', preview_response.text)
    assert token_match is not None
    preview_token = token_match.group(1)

    apply_response = client.post(
        "/imports/apply",
        data={
            "preview_token": preview_token,
            "reason": "bulk insert test",
            "bulk_default_action": "new",
        },
        follow_redirects=True,
    )
    assert apply_response.status_code == 200
    assert "Import complete." in apply_response.text
    assert "created=2" in apply_response.text
    assert "failed=0" in apply_response.text

    vendors_page = client.get("/vendors?search=Bulk+Import+Vendor")
    assert vendors_page.status_code == 200
    assert "Bulk Import Vendor One" in vendors_page.text
    assert "Bulk Import Vendor Two" in vendors_page.text
