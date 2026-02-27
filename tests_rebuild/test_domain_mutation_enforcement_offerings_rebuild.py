from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def test_offering_mutation_requires_editor_permissions(client: Client) -> None:
    editor_headers = {"HTTP_X_FORWARDED_USER": "editor.offering@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}
    client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": "v-offer-guard", "legal_name": "Guard Vendor"}),
        content_type="application/json",
        **editor_headers,
    )

    denied = client.post(
        "/api/v1/vendors/v-offer-guard/offerings",
        data=json.dumps({"offering_id": "o-guard", "offering_name": "Guard"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="viewer.guard@example.com",
    )
    assert denied.status_code == 403

    allowed = client.post(
        "/api/v1/vendors/v-offer-guard/offerings",
        data=json.dumps({"offering_id": "o-guard", "offering_name": "Guard"}),
        content_type="application/json",
        **editor_headers,
    )
    assert allowed.status_code == 201
