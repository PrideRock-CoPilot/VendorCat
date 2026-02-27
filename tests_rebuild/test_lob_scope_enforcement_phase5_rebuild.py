from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.identity.models import ScopeGrant

pytestmark = pytest.mark.django_db

ADMIN_HEADERS = {
    "HTTP_X_FORWARDED_USER": "lob.admin@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_admin",
}
EDITOR_HEADERS = {
    "HTTP_X_FORWARDED_USER": "lob.editor@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_editor",
}
VIEWER_HEADERS = {
    "HTTP_X_FORWARDED_USER": "lob.viewer@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_viewer",
}
OFFERING_EDITOR_HEADERS = {
    "HTTP_X_FORWARDED_USER": "lob.offering.editor@example.com",
    "HTTP_X_FORWARDED_GROUPS": "offering_editor",
}


def _create_vendor_and_offering(client: Client, *, vendor_id: str, offering_id: str, lob: str) -> None:
    created_vendor = client.post(
        "/api/v1/vendors",
        data=json.dumps(
            {
                "vendor_id": vendor_id,
                "legal_name": f"{vendor_id} Legal",
                "display_name": vendor_id,
                "owner_org_id": lob,
            }
        ),
        content_type="application/json",
        **ADMIN_HEADERS,
    )
    assert created_vendor.status_code == 201

    created_offering = client.post(
        f"/api/v1/vendors/{vendor_id}/offerings",
        data=json.dumps(
            {
                "offering_id": offering_id,
                "offering_name": offering_id,
                "lob": lob,
            }
        ),
        content_type="application/json",
        **ADMIN_HEADERS,
    )
    assert created_offering.status_code == 201


def test_scoped_user_can_only_mutate_offerings_with_matching_lob_scope(client: Client) -> None:
    _create_vendor_and_offering(client, vendor_id="v-lob-1", offering_id="o-lob-it", lob="IT")

    ScopeGrant.objects.create(
        user_principal="lob.editor@example.com",
        org_id="Finance",
        scope_level="edit",
    )

    denied = client.post(
        "/api/v1/offerings/o-lob-it/contacts",
        data=json.dumps({"full_name": "Denied Contact"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert denied.status_code == 403

    ScopeGrant.objects.create(
        user_principal="lob.editor@example.com",
        org_id="IT",
        scope_level="edit",
    )

    allowed = client.post(
        "/api/v1/offerings/o-lob-it/contacts",
        data=json.dumps({"full_name": "Allowed Contact"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert allowed.status_code == 201


def test_scoped_vendor_level_change_requires_all_vendor_lobs(client: Client) -> None:
    _create_vendor_and_offering(client, vendor_id="v-lob-2", offering_id="o-lob-2-it", lob="IT")
    created_second = client.post(
        "/api/v1/vendors/v-lob-2/offerings",
        data=json.dumps(
            {
                "offering_id": "o-lob-2-fin",
                "offering_name": "o-lob-2-fin",
                "lob": "Finance",
            }
        ),
        content_type="application/json",
        **ADMIN_HEADERS,
    )
    assert created_second.status_code == 201

    ScopeGrant.objects.create(
        user_principal="lob.editor@example.com",
        org_id="IT",
        scope_level="edit",
    )

    denied = client.patch(
        "/api/v1/vendors/v-lob-2",
        data=json.dumps({"display_name": "Scoped Change"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert denied.status_code == 403

    ScopeGrant.objects.create(
        user_principal="lob.editor@example.com",
        org_id="Finance",
        scope_level="edit",
    )

    allowed = client.patch(
        "/api/v1/vendors/v-lob-2",
        data=json.dumps({"display_name": "Scoped Change Allowed"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert allowed.status_code == 200


def test_contracts_are_hidden_on_offering_detail_for_users_without_contract_read(client: Client) -> None:
    _create_vendor_and_offering(client, vendor_id="v-lob-3", offering_id="o-lob-3", lob="IT")

    created_contract = client.post(
        "/api/v1/offerings/o-lob-3/contracts",
        data=json.dumps({"contract_id": "c-lob-3", "contract_status": "active"}),
        content_type="application/json",
        **ADMIN_HEADERS,
    )
    assert created_contract.status_code == 201

    page = client.get("/offerings/o-lob-3", **VIEWER_HEADERS)
    assert page.status_code == 200
    html = page.content.decode("utf-8")
    assert "Contracts are restricted for your current role/scope." in html
    assert "c-lob-3" not in html

    contracts_api = client.get("/api/v1/offerings/o-lob-3/contracts", **VIEWER_HEADERS)
    assert contracts_api.status_code == 403


def test_offering_editor_can_manage_tickets_but_not_contracts(client: Client) -> None:
    _create_vendor_and_offering(client, vendor_id="v-lob-4", offering_id="o-lob-4", lob="IT")

    detail = client.get("/offerings/o-lob-4", **OFFERING_EDITOR_HEADERS)
    assert detail.status_code == 200
    html = detail.content.decode("utf-8")
    assert "openOfferingDrawer('drawerServiceTickets')" in html
    assert "openOfferingDrawer('drawerContracts')" not in html
    assert "Contracts are restricted for your current role/scope." in html

    create_ticket = client.post(
        "/api/v1/offerings/o-lob-4/service-tickets",
        data=json.dumps({"title": "Scoped Ticket", "status": "open", "priority": "high"}),
        content_type="application/json",
        **OFFERING_EDITOR_HEADERS,
    )
    assert create_ticket.status_code == 201

    create_contract = client.post(
        "/api/v1/offerings/o-lob-4/contracts",
        data=json.dumps({"contract_id": "c-lob-4", "contract_status": "active"}),
        content_type="application/json",
        **OFFERING_EDITOR_HEADERS,
    )
    assert create_contract.status_code == 403


def test_scoped_offering_editor_cannot_see_edit_action_for_unscoped_lob(client: Client) -> None:
    _create_vendor_and_offering(client, vendor_id="v-lob-5", offering_id="o-lob-5", lob="IT")

    ScopeGrant.objects.create(
        user_principal="lob.offering.editor@example.com",
        org_id="Finance",
        scope_level="edit",
    )

    page = client.get("/offerings/", follow=True, **OFFERING_EDITOR_HEADERS)
    assert page.status_code == 200
    html = page.content.decode("utf-8")
    assert "o-lob-5" in html
    assert "/offerings/o-lob-5/edit" not in html
