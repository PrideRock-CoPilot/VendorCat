from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.contracts.models import Contract
from apps.offerings.models import Offering
from apps.vendors.models import Vendor, VendorContact, VendorIdentifier

pytestmark = pytest.mark.django_db


EDITOR_HEADERS = {
    "HTTP_X_FORWARDED_USER": "merge.editor@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_editor",
}
VIEWER_HEADERS = {
    "HTTP_X_FORWARDED_USER": "merge.viewer@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_viewer",
}


def _create_vendor(client: Client, vendor_id: str, display_name: str) -> None:
    response = client.post(
        "/api/v1/vendors",
        data=json.dumps(
            {
                "vendor_id": vendor_id,
                "legal_name": f"{display_name} Legal",
                "display_name": display_name,
                "owner_org_id": "IT-ENT",
                "risk_tier": "medium",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert response.status_code == 201


def test_merge_preview_returns_conflicts_and_impact(client: Client) -> None:
    _create_vendor(client, "v-merge-survivor", "Survivor Vendor")
    _create_vendor(client, "v-merge-donor", "Donor Vendor")

    preview = client.post(
        "/api/v1/vendors/merge/preview",
        data=json.dumps(
            {
                "survivor_vendor_id": "v-merge-survivor",
                "merged_vendor_ids": ["v-merge-donor"],
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["survivor_vendor_id"] == "v-merge-survivor"
    assert payload["merged_vendor_ids"] == ["v-merge-donor"]
    assert "impact" in payload


def test_merge_execute_reassigns_records_and_deletes_donor(client: Client) -> None:
    _create_vendor(client, "v-merge-survivor-2", "Survivor Vendor 2")
    _create_vendor(client, "v-merge-donor-2", "Donor Vendor 2")

    survivor = Vendor.objects.get(vendor_id="v-merge-survivor-2")
    donor = Vendor.objects.get(vendor_id="v-merge-donor-2")

    VendorContact.objects.create(vendor=donor, full_name="Donor Contact", contact_type="primary")
    VendorIdentifier.objects.create(vendor=donor, identifier_type="duns", identifier_value="123456789")
    Offering.objects.create(vendor=donor, offering_id="o-merge-1", offering_name="Merged Offering")
    Contract.objects.create(vendor=donor, contract_id="c-merge-1", contract_status="active")

    execute = client.post(
        "/api/v1/vendors/merge/execute",
        data=json.dumps(
            {
                "survivor_vendor_id": "v-merge-survivor-2",
                "merged_vendor_ids": ["v-merge-donor-2"],
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert execute.status_code == 200

    assert not Vendor.objects.filter(vendor_id="v-merge-donor-2").exists()
    assert VendorContact.objects.filter(vendor=survivor, full_name="Donor Contact").exists()
    assert VendorIdentifier.objects.filter(vendor=survivor, identifier_type="duns", identifier_value="123456789").exists()
    assert Offering.objects.filter(vendor=survivor, offering_id="o-merge-1").exists()
    assert Contract.objects.filter(vendor=survivor, contract_id="c-merge-1").exists()


def test_merge_endpoints_require_vendor_write_permission(client: Client) -> None:
    _create_vendor(client, "v-merge-survivor-3", "Survivor Vendor 3")
    _create_vendor(client, "v-merge-donor-3", "Donor Vendor 3")

    preview_denied = client.post(
        "/api/v1/vendors/merge/preview",
        data=json.dumps(
            {
                "survivor_vendor_id": "v-merge-survivor-3",
                "merged_vendor_ids": ["v-merge-donor-3"],
            }
        ),
        content_type="application/json",
        **VIEWER_HEADERS,
    )
    assert preview_denied.status_code == 403

    execute_denied = client.post(
        "/api/v1/vendors/merge/execute",
        data=json.dumps(
            {
                "survivor_vendor_id": "v-merge-survivor-3",
                "merged_vendor_ids": ["v-merge-donor-3"],
            }
        ),
        content_type="application/json",
        **VIEWER_HEADERS,
    )
    assert execute_denied.status_code == 403
