from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db

EDITOR_HEADERS = {
    "HTTP_X_FORWARDED_USER": "offering.program@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_editor",
}


def _create_offering(client: Client, offering_id: str = "o-program-1") -> str:
    vendor = client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": "v-program-1", "legal_name": "Program Vendor"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert vendor.status_code == 201

    offering = client.post(
        "/api/v1/vendors/v-program-1/offerings",
        data=json.dumps({"offering_id": offering_id, "offering_name": "Program Offering"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert offering.status_code == 201
    return offering_id


def test_offering_program_profile_and_entitlements_apis(client: Client) -> None:
    offering_id = _create_offering(client)

    profile_get = client.get(f"/api/v1/offerings/{offering_id}/program-profile")
    assert profile_get.status_code == 200

    profile_patch = client.patch(
        f"/api/v1/offerings/{offering_id}/program-profile",
        data=json.dumps(
            {
                "internal_owner": "owner@example.com",
                "vendor_success_manager": "vsm@example.com",
                "sla_target_pct": "99.90",
                "rto_hours": 4,
                "data_residency": "US-East",
                "compliance_tags": "soc2,hipaa",
                "budget_annual": "250000.00",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert profile_patch.status_code == 200
    assert profile_patch.json()["internal_owner"] == "owner@example.com"

    entitlement_created = client.post(
        f"/api/v1/offerings/{offering_id}/entitlements",
        data=json.dumps(
            {
                "entitlement_name": "Microsoft 365 E5",
                "license_type": "E5",
                "purchased_units": 1200,
                "assigned_units": 1100,
                "renewal_date": "2027-01-01",
                "true_up_date": "2026-11-01",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert entitlement_created.status_code == 201
    entitlement_id = entitlement_created.json()["id"]

    entitlement_patch = client.patch(
        f"/api/v1/offerings/{offering_id}/entitlements/{entitlement_id}",
        data=json.dumps({"assigned_units": 1150}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert entitlement_patch.status_code == 200
    assert entitlement_patch.json()["assigned_units"] == 1150

    entitlement_list = client.get(f"/api/v1/offerings/{offering_id}/entitlements")
    assert entitlement_list.status_code == 200
    assert any(item["id"] == entitlement_id for item in entitlement_list.json()["items"])


def test_offering_program_modules_render_on_detail_page(client: Client) -> None:
    offering_id = _create_offering(client, offering_id="o-program-2")

    client.patch(
        f"/api/v1/offerings/{offering_id}/program-profile",
        data=json.dumps(
            {
                "internal_owner": "program.owner@example.com",
                "vendor_success_manager": "program.vsm@example.com",
                "sla_target_pct": "99.95",
                "data_residency": "EU",
                "compliance_tags": "gdpr,soc2",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )

    client.post(
        f"/api/v1/offerings/{offering_id}/entitlements",
        data=json.dumps(
            {
                "entitlement_name": "Power BI Pro",
                "license_type": "Per-user",
                "purchased_units": 300,
                "assigned_units": 220,
                "renewal_date": "2027-03-01",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )

    client.post(
        f"/api/v1/offerings/{offering_id}/contracts",
        data=json.dumps(
            {
                "contract_id": "c-program-2",
                "contract_status": "active",
                "annual_value": "120000",
                "end_date": "2027-03-01",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )

    detail = client.get(f"/offerings/{offering_id}", **EDITOR_HEADERS)
    assert detail.status_code == 200
    html = detail.content.decode("utf-8")
    assert "Program Health" in html
    assert "Governance & Compliance" in html
    assert "Licenses & Entitlements" in html
    assert "Edit in Drawer" in html
    assert "Add in Drawer" in html
    assert "openOfferingDrawer('drawerProgramProfile')" in html
    assert "openOfferingDrawer('drawerEntitlements')" in html
    assert "program.owner@example.com" in html
    assert "Power BI Pro" in html
    assert ">Update Program Profile<" in html


def test_offering_program_endpoints_require_permission(client: Client) -> None:
    offering_id = _create_offering(client, offering_id="o-program-3")

    denied_profile = client.patch(
        f"/api/v1/offerings/{offering_id}/program-profile",
        data=json.dumps({"internal_owner": "nope@example.com"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="viewer.program@example.com",
    )
    assert denied_profile.status_code == 403

    denied_entitlement = client.post(
        f"/api/v1/offerings/{offering_id}/entitlements",
        data=json.dumps({"entitlement_name": "Denied"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="viewer.program@example.com",
    )
    assert denied_entitlement.status_code == 403
