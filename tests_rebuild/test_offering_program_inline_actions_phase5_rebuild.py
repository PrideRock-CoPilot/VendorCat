from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db

EDITOR_HEADERS = {
    "HTTP_X_FORWARDED_USER": "offering.inline@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_editor",
}


def _create_offering(client: Client) -> str:
    vendor = client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": "v-inline-1", "legal_name": "Inline Vendor"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert vendor.status_code == 201

    offering = client.post(
        "/api/v1/vendors/v-inline-1/offerings",
        data=json.dumps({"offering_id": "o-inline-1", "offering_name": "Inline Offering"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert offering.status_code == 201
    return "o-inline-1"


def test_offering_detail_inline_program_profile_and_entitlement_actions(client: Client) -> None:
    offering_id = _create_offering(client)

    profile_submit = client.post(
        f"/offerings/{offering_id}/program-profile/update",
        data={
            "internal_owner": "inline.owner@example.com",
            "vendor_success_manager": "inline.vsm@example.com",
            "sla_target_pct": "99.9",
            "rto_hours": "8",
            "data_residency": "US",
            "compliance_tags": "soc2",
            "budget_annual": "180000",
            "roadmap_notes": "inline roadmap",
        },
        **EDITOR_HEADERS,
    )
    assert profile_submit.status_code == 302

    entitlement_submit = client.post(
        f"/offerings/{offering_id}/entitlements/new",
        data={
            "entitlement_name": "Teams Enterprise",
            "license_type": "Enterprise",
            "purchased_units": "500",
            "assigned_units": "420",
            "renewal_date": "2027-06-01",
        },
        **EDITOR_HEADERS,
    )
    assert entitlement_submit.status_code == 302

    detail = client.get(f"/offerings/{offering_id}")
    assert detail.status_code == 200
    html = detail.content.decode("utf-8")
    assert "inline.owner@example.com" in html
    assert "Teams Enterprise" in html

    entitlements = client.get(f"/api/v1/offerings/{offering_id}/entitlements")
    assert entitlements.status_code == 200
    entitlement_id = entitlements.json()["items"][0]["id"]

    remove_submit = client.post(
        f"/offerings/{offering_id}/entitlements/{entitlement_id}/delete",
        **EDITOR_HEADERS,
    )
    assert remove_submit.status_code == 302

    entitlements_after = client.get(f"/api/v1/offerings/{offering_id}/entitlements")
    assert entitlements_after.status_code == 200
    assert len(entitlements_after.json()["items"]) == 0
