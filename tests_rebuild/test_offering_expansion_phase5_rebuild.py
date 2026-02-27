from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db

EDITOR_HEADERS = {
    "HTTP_X_FORWARDED_USER": "offering.expander@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_editor",
}


def _create_vendor_and_offering(client: Client) -> str:
    vendor = client.post(
        "/api/v1/vendors",
        data=json.dumps(
            {
                "vendor_id": "v-off-expand",
                "legal_name": "Offering Expansion Vendor",
                "display_name": "Offer Expand",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert vendor.status_code == 201

    offering = client.post(
        "/api/v1/vendors/v-off-expand/offerings",
        data=json.dumps(
            {
                "offering_id": "o-off-expand",
                "offering_name": "Expanded Offering",
                "offering_type": "SaaS",
                "lob": "IT",
                "service_type": "Platform",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert offering.status_code == 201
    return "o-off-expand"


def test_offering_nested_resources_crud_flows(client: Client) -> None:
    offering_id = _create_vendor_and_offering(client)

    contact_created = client.post(
        f"/api/v1/offerings/{offering_id}/contacts",
        data=json.dumps({"full_name": "Ops Contact", "email": "ops@example.com", "role": "operations"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert contact_created.status_code == 201
    contact_id = contact_created.json()["id"]

    contacts_list = client.get(f"/api/v1/offerings/{offering_id}/contacts")
    assert contacts_list.status_code == 200
    assert any(item["id"] == contact_id for item in contacts_list.json()["items"])

    contact_updated = client.patch(
        f"/api/v1/offerings/{offering_id}/contacts/{contact_id}",
        data=json.dumps({"phone": "+1-555-0111", "is_primary": True}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert contact_updated.status_code == 200
    assert contact_updated.json()["is_primary"] is True

    contract_created = client.post(
        f"/api/v1/offerings/{offering_id}/contracts",
        data=json.dumps(
            {
                "contract_id": "c-off-expand-1",
                "contract_number": "OFF-001",
                "contract_status": "active",
                "annual_value": "12345.67",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert contract_created.status_code == 201

    contracts_list = client.get(f"/api/v1/offerings/{offering_id}/contracts", **EDITOR_HEADERS)
    assert contracts_list.status_code == 200
    assert any(item["contract_id"] == "c-off-expand-1" for item in contracts_list.json()["items"])

    flow_created = client.post(
        f"/api/v1/offerings/{offering_id}/data-flows",
        data=json.dumps(
            {
                "flow_name": "Usage Feed",
                "source_system": "SaaS Platform",
                "target_system": "Data Lake",
                "direction": "outbound",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert flow_created.status_code == 201
    flow_id = flow_created.json()["id"]

    flow_updated = client.patch(
        f"/api/v1/offerings/{offering_id}/data-flows/{flow_id}",
        data=json.dumps({"status": "paused"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert flow_updated.status_code == 200
    assert flow_updated.json()["status"] == "paused"

    ticket_created = client.post(
        f"/api/v1/offerings/{offering_id}/service-tickets",
        data=json.dumps(
            {
                "title": "Latency Incident",
                "status": "open",
                "priority": "high",
                "ticket_system": "jira",
                "external_ticket_id": "JIRA-44",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert ticket_created.status_code == 201
    ticket_id = ticket_created.json()["id"]

    ticket_updated = client.patch(
        f"/api/v1/offerings/{offering_id}/service-tickets/{ticket_id}",
        data=json.dumps({"status": "in_progress"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert ticket_updated.status_code == 200
    assert ticket_updated.json()["status"] == "in_progress"

    document_created = client.post(
        f"/api/v1/offerings/{offering_id}/documents",
        data=json.dumps(
            {
                "doc_title": "Runbook",
                "doc_url": "https://docs.example.com/runbook",
                "doc_type": "runbook",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert document_created.status_code == 201
    document_id = document_created.json()["id"]

    docs_list = client.get(f"/api/v1/offerings/{offering_id}/documents")
    assert docs_list.status_code == 200
    assert any(item["id"] == document_id for item in docs_list.json()["items"])

    deleted_contact = client.delete(
        f"/api/v1/offerings/{offering_id}/contacts/{contact_id}",
        **EDITOR_HEADERS,
    )
    assert deleted_contact.status_code == 204


def test_offering_nested_resources_require_permissions(client: Client) -> None:
    offering_id = _create_vendor_and_offering(client)

    denied = client.post(
        f"/api/v1/offerings/{offering_id}/service-tickets",
        data=json.dumps({"title": "Denied ticket"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="viewer.only@example.com",
    )
    assert denied.status_code == 403
