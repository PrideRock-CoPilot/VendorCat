from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db

EDITOR_HEADERS = {
    "HTTP_X_FORWARDED_USER": "offering.sections@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_editor",
}


def _setup_offering_with_nested_data(client: Client) -> str:
    vendor = client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": "v-off-ui", "legal_name": "Offering UI Vendor"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert vendor.status_code == 201

    offering = client.post(
        "/api/v1/vendors/v-off-ui/offerings",
        data=json.dumps(
            {
                "offering_id": "o-off-ui",
                "offering_name": "Offering UI",
                "offering_type": "SaaS",
                "lob": "IT",
                "service_type": "Platform",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert offering.status_code == 201

    client.post(
        "/api/v1/offerings/o-off-ui/contacts",
        data=json.dumps({"full_name": "UI Contact", "role": "owner"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    client.post(
        "/api/v1/offerings/o-off-ui/contracts",
        data=json.dumps({"contract_id": "c-off-ui-1", "contract_status": "active"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    client.post(
        "/api/v1/offerings/o-off-ui/data-flows",
        data=json.dumps(
            {
                "flow_name": "UI Flow",
                "source_system": "App",
                "target_system": "Warehouse",
                "direction": "outbound",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    client.post(
        "/api/v1/offerings/o-off-ui/service-tickets",
        data=json.dumps({"title": "UI Incident", "status": "open", "priority": "high"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    client.post(
        "/api/v1/offerings/o-off-ui/documents",
        data=json.dumps({"doc_title": "UI Runbook", "doc_url": "https://docs.example.com/ui-runbook"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )

    return "o-off-ui"


def test_offering_detail_page_renders_nested_sections(client: Client) -> None:
    offering_id = _setup_offering_with_nested_data(client)

    page = client.get(f"/offerings/{offering_id}", **EDITOR_HEADERS)
    assert page.status_code == 200
    html = page.content.decode("utf-8")

    assert "Contacts" in html
    assert "Contracts" in html
    assert "Data Flows" in html
    assert "Service Tickets" in html
    assert "Documents" in html

    assert "UI Contact" in html
    assert "c-off-ui-1" in html
    assert "UI Flow" in html
    assert "UI Incident" in html
    assert "UI Runbook" in html
