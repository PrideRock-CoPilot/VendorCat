from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.identity.models import UserDirectory

pytestmark = pytest.mark.django_db


EDITOR_HEADERS = {
    "HTTP_X_FORWARDED_USER": "search.editor@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_editor",
}


def test_search_vendors_offerings_projects_contracts(client: Client) -> None:
    vendor_created = client.post(
        "/api/v1/vendors",
        data=json.dumps(
            {
                "vendor_id": "v-search-1",
                "legal_name": "Searchable Vendor LLC",
                "display_name": "Search Vendor",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert vendor_created.status_code == 201

    offering_created = client.post(
        "/api/v1/vendors/v-search-1/offerings",
        data=json.dumps(
            {
                "offering_id": "o-search-1",
                "offering_name": "Search Platform",
                "offering_type": "SaaS",
                "lob": "IT",
                "service_type": "Platform",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert offering_created.status_code == 201

    project_created = client.post(
        "/api/v1/projects",
        data=json.dumps(
            {
                "project_id": "p-search-1",
                "project_name": "Search Migration",
                "owner_principal": "owner.search@example.com",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert project_created.status_code == 201

    contract_created = client.post(
        "/api/v1/vendors/v-search-1/contracts",
        data=json.dumps(
            {
                "contract_id": "c-search-1",
                "contract_number": "SRCH-001",
                "contract_status": "active",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert contract_created.status_code == 201

    vendors = client.get("/api/v1/search/vendors?q=search")
    assert vendors.status_code == 200
    assert any(item["id"] == "v-search-1" for item in vendors.json()["items"])

    offerings = client.get("/api/v1/search/offerings?q=platform")
    assert offerings.status_code == 200
    assert any(item["id"] == "o-search-1" for item in offerings.json()["items"])

    projects = client.get("/api/v1/search/projects?q=migration")
    assert projects.status_code == 200
    assert any(item["id"] == "p-search-1" for item in projects.json()["items"])

    contracts = client.get("/api/v1/search/contracts?q=srch")
    assert contracts.status_code == 200
    assert any(item["id"] == "c-search-1" for item in contracts.json()["items"])


def test_search_users_and_contacts(client: Client) -> None:
    UserDirectory.objects.create(
        user_principal="search.user@example.com",
        display_name="Search User",
        email="search.user@example.com",
    )
    UserDirectory.objects.create(
        user_principal="inactive.search.user@example.com",
        display_name="Inactive Search User",
        email="inactive.search.user@example.com",
        active_flag=False,
    )

    vendor_created = client.post(
        "/api/v1/vendors",
        data=json.dumps(
            {
                "vendor_id": "v-contact-search",
                "legal_name": "Contact Search Vendor",
                "display_name": "Contact Search",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert vendor_created.status_code == 201

    contact_created = client.post(
        "/vendor-360/api/v-contact-search/contacts",
        data=json.dumps(
            {
                "full_name": "Search Contact",
                "contact_type": "primary",
                "email": "contact.search@example.com",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert contact_created.status_code == 201

    users = client.get("/api/v1/search/users?q=search user")
    assert users.status_code == 200
    users_payload = users.json()["items"]
    assert any(item["id"] == "search.user@example.com" for item in users_payload)
    assert all(item["id"] != "inactive.search.user@example.com" for item in users_payload)

    users_with_inactive = client.get("/api/v1/search/users?q=search user&include_inactive=true")
    assert users_with_inactive.status_code == 200
    assert any(item["id"] == "inactive.search.user@example.com" for item in users_with_inactive.json()["items"])

    contacts = client.get("/api/v1/search/contacts?q=search contact")
    assert contacts.status_code == 200
    contact_items = contacts.json()["items"]
    matched = next(item for item in contact_items if item["label"] == "Search Contact")
    assert matched["email"] == "contact.search@example.com"
