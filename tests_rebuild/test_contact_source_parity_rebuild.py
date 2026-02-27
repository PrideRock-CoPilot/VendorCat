from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.identity.models import UserDirectory
from apps.offerings.models import Offering
from apps.vendors.models import Vendor, VendorContact

pytestmark = pytest.mark.django_db

EDITOR_HEADERS = {
    "HTTP_X_FORWARDED_USER": "contact.parity.editor@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_editor",
}


def _create_vendor_and_offering(client: Client) -> tuple[Vendor, Offering]:
    vendor_response = client.post(
        "/api/v1/vendors",
        data=json.dumps(
            {
                "vendor_id": "v-contact-parity",
                "legal_name": "Contact Parity Vendor LLC",
                "display_name": "Contact Parity Vendor",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert vendor_response.status_code == 201

    offering_response = client.post(
        "/api/v1/vendors/v-contact-parity/offerings",
        data=json.dumps(
            {
                "offering_id": "o-contact-parity",
                "offering_name": "Parity Offering",
                "offering_type": "SaaS",
                "lob": "IT",
                "service_type": "Platform",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert offering_response.status_code == 201

    vendor = Vendor.objects.get(vendor_id="v-contact-parity")
    offering = Offering.objects.get(offering_id="o-contact-parity")
    return vendor, offering


def test_vendor_internal_contact_requires_active_user(client: Client) -> None:
    vendor, _ = _create_vendor_and_offering(client)

    UserDirectory.objects.create(
        user_principal="active.user@example.com",
        display_name="Active User",
        email="active.user@example.com",
        active_flag=True,
    )
    UserDirectory.objects.create(
        user_principal="inactive.user@example.com",
        display_name="Inactive User",
        email="inactive.user@example.com",
        active_flag=False,
    )

    inactive_response = client.post(
        f"/vendor-360/api/{vendor.vendor_id}/contacts",
        data=json.dumps(
            {
                "contact_source": "internal",
                "internal_user_principal": "inactive.user@example.com",
                "contact_role": "SME",
                "contact_type": "technical",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert inactive_response.status_code == 400

    active_response = client.post(
        f"/vendor-360/api/{vendor.vendor_id}/contacts",
        data=json.dumps(
            {
                "contact_source": "internal",
                "internal_user_principal": "active.user@example.com",
                "contact_role": "SME",
                "contact_type": "technical",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert active_response.status_code == 201
    payload = active_response.json()
    assert payload["full_name"] == "Active User"
    assert payload["email"] == "active.user@example.com"
    assert payload["title"] == "SME"


def test_offering_external_contact_can_reuse_existing_contact(client: Client) -> None:
    vendor, offering = _create_vendor_and_offering(client)

    source_contact = VendorContact.objects.create(
        vendor=vendor,
        full_name="Existing External Contact",
        contact_type="support",
        email="external.contact@example.com",
        phone="555-3322",
        title="Account Manager",
        is_active=True,
    )

    response = client.post(
        f"/api/v1/offerings/{offering.offering_id}/contacts",
        data=json.dumps(
            {
                "contact_source": "external",
                "external_contact_id": str(source_contact.id),
                "full_name": "",
                "email": "",
                "phone": "",
                "role": "",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["full_name"] == "Existing External Contact"
    assert payload["email"] == "external.contact@example.com"
    assert payload["phone"] == "555-3322"
    assert payload["role"] == "Account Manager"
