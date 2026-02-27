from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db

EDITOR_HEADERS = {
    "HTTP_X_FORWARDED_USER": "offering.ops.inline@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_editor",
}


def _create_offering(client: Client) -> str:
    vendor = client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": "v-ops-inline-1", "legal_name": "Ops Inline Vendor"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert vendor.status_code == 201

    offering = client.post(
        "/api/v1/vendors/v-ops-inline-1/offerings",
        data=json.dumps({"offering_id": "o-ops-inline-1", "offering_name": "Ops Inline Offering"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert offering.status_code == 201
    return "o-ops-inline-1"


def test_offering_detail_operational_inline_actions(client: Client) -> None:
    offering_id = _create_offering(client)

    contact_add = client.post(
        f"/offerings/{offering_id}/contacts/new",
        data={"full_name": "Inline Contact", "role": "TAM", "email": "tam@example.com"},
        **EDITOR_HEADERS,
    )
    assert contact_add.status_code == 302

    contract_add = client.post(
        f"/offerings/{offering_id}/contracts/new",
        data={"contract_id": "c-ops-inline-1", "contract_status": "active", "annual_value": "75000"},
        **EDITOR_HEADERS,
    )
    assert contract_add.status_code == 302

    flow_add = client.post(
        f"/offerings/{offering_id}/data-flows/new",
        data={"flow_name": "Ops Feed", "source_system": "SaaS", "target_system": "Warehouse", "direction": "outbound"},
        **EDITOR_HEADERS,
    )
    assert flow_add.status_code == 302

    ticket_add = client.post(
        f"/offerings/{offering_id}/service-tickets/new",
        data={"title": "Inline Incident", "status": "open", "priority": "high"},
        **EDITOR_HEADERS,
    )
    assert ticket_add.status_code == 302

    doc_add = client.post(
        f"/offerings/{offering_id}/documents/new",
        data={"doc_title": "Inline Runbook", "doc_url": "https://docs.example.com/inline"},
        **EDITOR_HEADERS,
    )
    assert doc_add.status_code == 302

    detail = client.get(f"/offerings/{offering_id}", **EDITOR_HEADERS)
    assert detail.status_code == 200
    html = detail.content.decode("utf-8")
    assert "Inline Contact" in html
    assert "c-ops-inline-1" in html
    assert "Ops Feed" in html
    assert "Inline Incident" in html
    assert "Inline Runbook" in html

    contacts = client.get(f"/api/v1/offerings/{offering_id}/contacts")
    assert contacts.status_code == 200
    contact_id = contacts.json()["items"][0]["id"]

    flows = client.get(f"/api/v1/offerings/{offering_id}/data-flows")
    assert flows.status_code == 200
    flow_id = flows.json()["items"][0]["id"]

    tickets = client.get(f"/api/v1/offerings/{offering_id}/service-tickets")
    assert tickets.status_code == 200
    ticket_id = tickets.json()["items"][0]["id"]

    docs = client.get(f"/api/v1/offerings/{offering_id}/documents")
    assert docs.status_code == 200
    doc_id = docs.json()["items"][0]["id"]

    contact_edit = client.post(
        f"/offerings/{offering_id}/contacts/{contact_id}/edit",
        data={
            "full_name": "Inline Contact Updated",
            "role": "Service Owner",
            "email": "owner@example.com",
            "phone": "555-2222",
            "is_primary": "1",
            "is_active": "1",
        },
        **EDITOR_HEADERS,
    )
    assert contact_edit.status_code == 302

    flow_edit = client.post(
        f"/offerings/{offering_id}/data-flows/{flow_id}/edit",
        data={
            "flow_name": "Ops Feed Updated",
            "source_system": "SaaS-Updated",
            "target_system": "Warehouse-Updated",
            "direction": "inbound",
            "status": "paused",
        },
        **EDITOR_HEADERS,
    )
    assert flow_edit.status_code == 302

    ticket_edit = client.post(
        f"/offerings/{offering_id}/service-tickets/{ticket_id}/edit",
        data={
            "title": "Inline Incident Updated",
            "status": "in_progress",
            "priority": "critical",
            "ticket_system": "ServiceNow",
            "external_ticket_id": "INC-42",
        },
        **EDITOR_HEADERS,
    )
    assert ticket_edit.status_code == 302

    doc_edit = client.post(
        f"/offerings/{offering_id}/documents/{doc_id}/edit",
        data={
            "doc_title": "Inline Runbook Updated",
            "doc_url": "https://docs.example.com/inline-updated",
            "doc_type": "runbook",
            "owner_principal": "ops.owner@example.com",
            "is_active": "1",
        },
        **EDITOR_HEADERS,
    )
    assert doc_edit.status_code == 302

    contacts_after_edit = client.get(f"/api/v1/offerings/{offering_id}/contacts")
    flows_after_edit = client.get(f"/api/v1/offerings/{offering_id}/data-flows")
    tickets_after_edit = client.get(f"/api/v1/offerings/{offering_id}/service-tickets")
    docs_after_edit = client.get(f"/api/v1/offerings/{offering_id}/documents")

    assert contacts_after_edit.status_code == 200
    assert flows_after_edit.status_code == 200
    assert tickets_after_edit.status_code == 200
    assert docs_after_edit.status_code == 200

    assert contacts_after_edit.json()["items"][0]["full_name"] == "Inline Contact Updated"
    assert contacts_after_edit.json()["items"][0]["is_primary"] is True
    assert flows_after_edit.json()["items"][0]["flow_name"] == "Ops Feed Updated"
    assert flows_after_edit.json()["items"][0]["direction"] == "inbound"
    assert tickets_after_edit.json()["items"][0]["title"] == "Inline Incident Updated"
    assert tickets_after_edit.json()["items"][0]["priority"] == "critical"
    assert docs_after_edit.json()["items"][0]["doc_title"] == "Inline Runbook Updated"
    assert docs_after_edit.json()["items"][0]["doc_url"] == "https://docs.example.com/inline-updated"

    contact_remove = client.post(f"/offerings/{offering_id}/contacts/{contact_id}/delete", **EDITOR_HEADERS)
    assert contact_remove.status_code == 302

    flow_remove = client.post(f"/offerings/{offering_id}/data-flows/{flow_id}/delete", **EDITOR_HEADERS)
    assert flow_remove.status_code == 302

    ticket_remove = client.post(f"/offerings/{offering_id}/service-tickets/{ticket_id}/delete", **EDITOR_HEADERS)
    assert ticket_remove.status_code == 302

    doc_remove = client.post(f"/offerings/{offering_id}/documents/{doc_id}/delete", **EDITOR_HEADERS)
    assert doc_remove.status_code == 302

    contacts_after = client.get(f"/api/v1/offerings/{offering_id}/contacts")
    flows_after = client.get(f"/api/v1/offerings/{offering_id}/data-flows")
    tickets_after = client.get(f"/api/v1/offerings/{offering_id}/service-tickets")
    docs_after = client.get(f"/api/v1/offerings/{offering_id}/documents")

    assert contacts_after.status_code == 200 and len(contacts_after.json()["items"]) == 0
    assert flows_after.status_code == 200 and len(flows_after.json()["items"]) == 0
    assert tickets_after.status_code == 200 and len(tickets_after.json()["items"]) == 0
    assert docs_after.status_code == 200 and len(docs_after.json()["items"]) == 0
