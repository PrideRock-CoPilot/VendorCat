from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def _create_vendor(client: Client, vendor_id: str) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.contract@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}
    response = client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": vendor_id, "legal_name": "Contract Vendor"}),
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 201


def test_contract_create_list_get_patch(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.contract@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}
    vendor_id = "v-contract"
    _create_vendor(client, vendor_id)

    created = client.post(
        f"/api/v1/vendors/{vendor_id}/contracts",
        data=json.dumps(
            {
                "contract_id": "ctr-1",
                "contract_number": "CN-001",
                "contract_status": "active",
                "annual_value": "125000.50",
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 201
    assert created.json()["contract_id"] == "ctr-1"

    listed = client.get(f"/api/v1/vendors/{vendor_id}/contracts")
    assert listed.status_code == 200
    assert any(item["contract_id"] == "ctr-1" for item in listed.json()["items"])

    detail = client.get("/api/v1/contracts/ctr-1")
    assert detail.status_code == 200
    assert detail.json()["contract_number"] == "CN-001"

    updated = client.patch(
        "/api/v1/contracts/ctr-1",
        data=json.dumps({"contract_status": "retired"}),
        content_type="application/json",
        **headers,
    )
    assert updated.status_code == 200
    assert updated.json()["contract_status"] == "retired"


def test_contract_validation_rejects_invalid_status(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.contract2@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}
    vendor_id = "v-contract-2"
    _create_vendor(client, vendor_id)

    bad_status = client.post(
        f"/api/v1/vendors/{vendor_id}/contracts",
        data=json.dumps({"contract_id": "ctr-bad", "contract_status": "unknown"}),
        content_type="application/json",
        **headers,
    )
    assert bad_status.status_code == 400


def test_contract_requires_permission(client: Client) -> None:
    vendor_id = "v-contract-3"
    _create_vendor(client, vendor_id)

    denied = client.post(
        f"/api/v1/vendors/{vendor_id}/contracts",
        data=json.dumps({"contract_id": "ctr-denied"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="viewer@example.com",
    )
    assert denied.status_code == 403


def test_contract_list_and_detail_pages_render(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.contractui@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}
    vendor_id = "v-contract-ui"

    vendor_response = client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": vendor_id, "legal_name": "Contract UI Vendor"}),
        content_type="application/json",
        **headers,
    )
    assert vendor_response.status_code == 201

    contract_response = client.post(
        f"/api/v1/vendors/{vendor_id}/contracts",
        data=json.dumps({"contract_id": "ctr-ui", "contract_status": "active"}),
        content_type="application/json",
        **headers,
    )
    assert contract_response.status_code == 201

    list_page = client.get("/contracts/")
    assert list_page.status_code == 200
    assert "ctr-ui" in list_page.content.decode("utf-8")

    detail_page = client.get("/contracts/ctr-ui")
    assert detail_page.status_code == 200
    assert "ctr-ui" in detail_page.content.decode("utf-8")
