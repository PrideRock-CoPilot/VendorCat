from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.services import get_config, get_repo


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("TVENDOR_USE_MOCK", "1")
    monkeypatch.setenv("TVENDOR_TEST_USER", "admin@example.com")
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    return TestClient(app)


def test_vendors_page_renders(client: TestClient) -> None:
    response = client.get("/vendors")
    assert response.status_code == 200
    assert "Vendor 360" in response.text


def test_vendor_new_requires_edit_permissions(client: TestClient) -> None:
    response = client.get("/vendors/new?as_user=viewer.only@example.com", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/vendors")


def test_create_vendor_and_find_in_list(client: TestClient) -> None:
    response = client.post(
        "/vendors/new",
        data={
            "return_to": "/vendors",
            "legal_name": "Acme Vendor LLC",
            "display_name": "Acme",
            "lifecycle_state": "draft",
            "owner_org_id": "IT-ENT",
            "risk_tier": "low",
            "source_system": "manual",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    match = re.search(r"/vendors/(vnd-[^/]+)/summary", location)
    assert match is not None
    vendor_id = match.group(1)

    list_response = client.get(f"/vendors?search={vendor_id}")
    assert list_response.status_code == 200
    assert vendor_id in list_response.text
    assert "Acme" in list_response.text


def test_create_vendor_validation_keeps_values_and_marks_owner_org(client: TestClient) -> None:
    response = client.post(
        "/vendors/new",
        data={
            "return_to": "/vendors",
            "legal_name": "Validation Vendor LLC",
            "display_name": "Validation Vendor",
            "lifecycle_state": "draft",
            "owner_org_choice": "__new__",
            "new_owner_org_id": "",
            "risk_tier": "low",
            "source_system": "manual",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Enter a new Owner Org ID." in response.text
    assert "Validation Vendor LLC" in response.text
    assert 'class="input-error"' in response.text


def test_create_offering_and_map_unassigned_records(client: TestClient) -> None:
    new_offering_response = client.post(
        "/vendors/vnd-003/offerings/new",
        data={
            "return_to": "/vendors",
            "offering_name": "Legacy Bridge",
            "offering_type": "SaaS",
            "lifecycle_state": "draft",
            "criticality_tier": "tier_2",
        },
        follow_redirects=False,
    )
    assert new_offering_response.status_code == 303
    match = re.search(r"/vendors/vnd-003/offerings/(off-[^?]+)", new_offering_response.headers["location"])
    assert match is not None
    offering_id = match.group(1)

    map_contract_response = client.post(
        "/vendors/vnd-003/map-contract",
        data={
            "return_to": "/vendors/vnd-003/offerings",
            "contract_id": "ctr-001",
            "offering_id": offering_id,
            "reason": "Map legacy contract",
        },
        follow_redirects=False,
    )
    assert map_contract_response.status_code == 303

    map_demo_response = client.post(
        "/vendors/vnd-003/map-demo",
        data={
            "return_to": "/vendors/vnd-003/offerings",
            "demo_id": "demo-002",
            "offering_id": offering_id,
            "reason": "Map legacy demo",
        },
        follow_redirects=False,
    )
    assert map_demo_response.status_code == 303

    offerings_page = client.get("/vendors/vnd-003/offerings?return_to=%2Fvendors")
    assert offerings_page.status_code == 200
    assert "Legacy Bridge" in offerings_page.text
    assert "No unassigned contracts." in offerings_page.text
    assert "No unassigned demos." in offerings_page.text

    offering_detail_page = client.get(f"/vendors/vnd-003/offerings/{offering_id}?return_to=%2Fvendors")
    assert offering_detail_page.status_code == 200
    assert "ctr-001" in offering_detail_page.text
    assert "demo-002" in offering_detail_page.text


def test_search_matches_related_contract_and_owner_data(client: TestClient) -> None:
    by_contract = client.get("/vendors?search=ctr-101")
    assert by_contract.status_code == 200
    assert "Microsoft" in by_contract.text

    by_owner = client.get("/vendors?search=cloud-platform@example.com")
    assert by_owner.status_code == 200
    assert "Microsoft" in by_owner.text
