from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def _create_vendor(client: Client, vendor_id: str) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.offering@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}
    response = client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": vendor_id, "legal_name": "Offering Vendor"}),
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 201


def test_offering_create_list_get_patch(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.offering@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}
    vendor_id = "v-offer"
    _create_vendor(client, vendor_id)

    created = client.post(
        f"/api/v1/vendors/{vendor_id}/offerings",
        data=json.dumps(
            {
                "offering_id": "o-1",
                "offering_name": "Core Platform",
                "offering_type": "SaaS",
                "lob": "IT",
                "service_type": "Platform",
                "lifecycle_state": "active",
                "criticality_tier": "tier_2",
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 201
    assert created.json()["offering_id"] == "o-1"

    listed = client.get(f"/api/v1/vendors/{vendor_id}/offerings")
    assert listed.status_code == 200
    assert any(item["offering_id"] == "o-1" for item in listed.json()["items"])

    detail = client.get("/api/v1/offerings/o-1")
    assert detail.status_code == 200
    assert detail.json()["offering_name"] == "Core Platform"

    updated = client.patch(
        "/api/v1/offerings/o-1",
        data=json.dumps({"lifecycle_state": "suspended"}),
        content_type="application/json",
        **headers,
    )
    assert updated.status_code == 200
    assert updated.json()["lifecycle_state"] == "suspended"


def test_offering_validation_rejects_invalid_values(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.offering2@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}
    vendor_id = "v-offer-2"
    _create_vendor(client, vendor_id)

    bad_lifecycle = client.post(
        f"/api/v1/vendors/{vendor_id}/offerings",
        data=json.dumps({"offering_id": "o-bad", "offering_name": "Bad", "lifecycle_state": "unknown"}),
        content_type="application/json",
        **headers,
    )
    assert bad_lifecycle.status_code == 400

    bad_type = client.post(
        f"/api/v1/vendors/{vendor_id}/offerings",
        data=json.dumps({"offering_id": "o-bad2", "offering_name": "Bad2", "offering_type": "Weird"}),
        content_type="application/json",
        **headers,
    )
    assert bad_type.status_code == 400


def test_offering_requires_permission(client: Client) -> None:
    vendor_id = "v-offer-3"
    _create_vendor(client, vendor_id)

    denied = client.post(
        f"/api/v1/vendors/{vendor_id}/offerings",
        data=json.dumps({"offering_id": "o-denied", "offering_name": "Denied"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="viewer@example.com",
    )
    assert denied.status_code == 403


def test_offering_list_and_detail_pages_render(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.offerui@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}
    vendor_id = "v-offer-ui"
    offering_id = "o-ui"

    vendor_response = client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": vendor_id, "legal_name": "Offering UI Vendor"}),
        content_type="application/json",
        **headers,
    )
    assert vendor_response.status_code == 201

    offering_response = client.post(
        f"/api/v1/vendors/{vendor_id}/offerings",
        data=json.dumps({"offering_id": offering_id, "offering_name": "UI Offering"}),
        content_type="application/json",
        **headers,
    )
    assert offering_response.status_code == 201

    list_page = client.get("/offerings/")
    assert list_page.status_code == 200
    assert offering_id in list_page.content.decode("utf-8")

    detail_page = client.get(f"/offerings/{offering_id}")
    assert detail_page.status_code == 200
    detail_html = detail_page.content.decode("utf-8")
    assert "UI Offering" in detail_html
    assert "data-tab=\"overview\"" in detail_html
    assert "data-tab=\"program\"" in detail_html
    assert "data-tab=\"entitlements\"" in detail_html
    assert "data-tab=\"contacts\"" in detail_html
    assert "data-tab=\"contracts\"" in detail_html


def test_offering_list_filters_and_attention_signals(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.offerfilter@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}
    vendor_id = "v-offer-filter"

    vendor_response = client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": vendor_id, "legal_name": "Offering Filter Vendor"}),
        content_type="application/json",
        **headers,
    )
    assert vendor_response.status_code == 201

    client.post(
        f"/api/v1/vendors/{vendor_id}/offerings",
        data=json.dumps(
            {
                "offering_id": "tmp-off-1",
                "offering_name": "Temporary Offering",
                "lifecycle_state": "active",
                "criticality_tier": "tier_1",
            }
        ),
        content_type="application/json",
        **headers,
    )

    client.post(
        f"/api/v1/vendors/{vendor_id}/offerings",
        data=json.dumps(
            {
                "offering_id": "off-stable-1",
                "offering_name": "Stable Offering",
                "lifecycle_state": "active",
            }
        ),
        content_type="application/json",
        **headers,
    )

    client.post(
        "/api/v1/offerings/off-stable-1/service-tickets",
        data=json.dumps({"title": "Latency issue", "status": "open", "priority": "high"}),
        content_type="application/json",
        **headers,
    )

    attention_page = client.get("/offerings/?health=needs_attention")
    assert attention_page.status_code == 200
    html = attention_page.content.decode("utf-8")
    assert "tmp-off-1" in html
    assert "off-stable-1" in html
    assert "Needs attention" in html

    criticality_page = client.get("/offerings/?criticality=tier_1")
    assert criticality_page.status_code == 200
    filtered_html = criticality_page.content.decode("utf-8")
    assert "tmp-off-1" in filtered_html
