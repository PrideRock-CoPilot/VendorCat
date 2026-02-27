from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def test_vendor_api_create_list_get_patch(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.vendor@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}

    created = client.post(
        "/api/v1/vendors",
        data=json.dumps(
            {
                "vendor_id": "v-phase4",
                "legal_name": "Vendor Phase 4 LLC",
                "display_name": "Vendor P4",
                "lifecycle_state": "active",
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 201
    assert created.json()["vendor_id"] == "v-phase4"

    duplicate = client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": "v-phase4", "legal_name": "Duplicate"}),
        content_type="application/json",
        **headers,
    )
    assert duplicate.status_code == 409

    listed = client.get("/api/v1/vendors")
    assert listed.status_code == 200
    assert any(item["vendor_id"] == "v-phase4" for item in listed.json()["items"])

    detail = client.get("/api/v1/vendors/v-phase4")
    assert detail.status_code == 200
    assert detail.json()["display_name"] == "Vendor P4"

    updated = client.patch(
        "/api/v1/vendors/v-phase4",
        data=json.dumps({"risk_tier": "high"}),
        content_type="application/json",
        **headers,
    )
    assert updated.status_code == 200
    assert updated.json()["risk_tier"] == "high"


def test_vendor_rejects_invalid_lifecycle_and_risk(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.vendor2@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}

    bad_lifecycle = client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": "v-bad", "legal_name": "Bad Vendor", "lifecycle_state": "unknown"}),
        content_type="application/json",
        **headers,
    )
    assert bad_lifecycle.status_code == 400

    created = client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": "v-good", "legal_name": "Good Vendor"}),
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 201

    bad_risk = client.patch(
        "/api/v1/vendors/v-good",
        data=json.dumps({"risk_tier": "extreme"}),
        content_type="application/json",
        **headers,
    )
    assert bad_risk.status_code == 400


def test_project_api_create_list_get_patch(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.project@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}

    created = client.post(
        "/api/v1/projects",
        data=json.dumps(
            {
                "project_id": "p-phase4",
                "project_name": "Project Phase 4",
                "owner_principal": "owner@example.com",
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 201
    assert created.json()["project_id"] == "p-phase4"

    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200
    assert any(item["project_id"] == "p-phase4" for item in listed.json()["items"])

    detail = client.get("/api/v1/projects/p-phase4")
    assert detail.status_code == 200
    assert detail.json()["project_name"] == "Project Phase 4"

    updated = client.patch(
        "/api/v1/projects/p-phase4",
        data=json.dumps({"lifecycle_state": "blocked"}),
        content_type="application/json",
        **headers,
    )
    assert updated.status_code == 200
    assert updated.json()["lifecycle_state"] == "blocked"


def test_project_rejects_invalid_lifecycle(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.project2@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}
    created = client.post(
        "/api/v1/projects",
        data=json.dumps({"project_id": "p-bad", "project_name": "Bad Project", "lifecycle_state": "unknown"}),
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 400


def test_vendor_project_pages_show_records(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.page@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}
    client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": "v-ui", "legal_name": "Vendor UI"}),
        content_type="application/json",
        **headers,
    )
    client.post(
        "/api/v1/projects",
        data=json.dumps({"project_id": "p-ui", "project_name": "Project UI"}),
        content_type="application/json",
        **headers,
    )

    vendor_page = client.get("/vendor-360/", follow=True)
    assert vendor_page.status_code == 200
    assert "v-ui" in vendor_page.content.decode("utf-8")

    project_page = client.get("/projects/", follow=True)
    assert project_page.status_code == 200
    assert "p-ui" in project_page.content.decode("utf-8")


def test_vendor_and_project_detail_controls_are_permission_gated(client: Client) -> None:
    editor_headers = {"HTTP_X_FORWARDED_USER": "editor.controls@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}
    offering_editor_headers = {
        "HTTP_X_FORWARDED_USER": "offering.controls@example.com",
        "HTTP_X_FORWARDED_GROUPS": "offering_editor",
    }

    vendor_created = client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": "v-controls", "legal_name": "Vendor Controls", "owner_org_id": "IT"}),
        content_type="application/json",
        **editor_headers,
    )
    assert vendor_created.status_code == 201

    project_created = client.post(
        "/api/v1/projects",
        data=json.dumps({"project_id": "p-controls", "project_name": "Project Controls"}),
        content_type="application/json",
        **editor_headers,
    )
    assert project_created.status_code == 201

    vendor_editor_detail = client.get("/vendor-360/v-controls", **editor_headers)
    assert vendor_editor_detail.status_code == 200
    vendor_editor_html = vendor_editor_detail.content.decode("utf-8")
    assert "Edit Vendor" in vendor_editor_html
    assert "Quick Add Contract" in vendor_editor_html
    assert "Quick Add Contact" in vendor_editor_html
    assert "data-tab=\"overview\"" in vendor_editor_html
    assert "data-tab=\"contracts\"" in vendor_editor_html
    assert "data-tab=\"contacts\"" in vendor_editor_html

    offering_editor_detail = client.get("/vendor-360/v-controls", **offering_editor_headers)
    assert offering_editor_detail.status_code == 200
    offering_editor_html = offering_editor_detail.content.decode("utf-8")
    assert "Edit Vendor" not in offering_editor_html
    assert "Quick Add Contract" not in offering_editor_html
    assert "Quick Add Contact" not in offering_editor_html
    assert "Quick Add Offering" in offering_editor_html
    assert "Contracts are restricted for your current role/scope." in offering_editor_html

    project_editor_detail = client.get("/projects/p-controls", **editor_headers)
    assert project_editor_detail.status_code == 200
    project_editor_html = project_editor_detail.content.decode("utf-8")
    assert "Edit Project" in project_editor_html
    assert "data-tab=\"overview\"" in project_editor_html
    assert "data-tab=\"details\"" in project_editor_html

    project_offering_editor_detail = client.get("/projects/p-controls", **offering_editor_headers)
    assert project_offering_editor_detail.status_code == 200
    assert "Edit Project" not in project_offering_editor_detail.content.decode("utf-8")


def test_list_page_actions_are_permission_gated(client: Client) -> None:
    editor_headers = {"HTTP_X_FORWARDED_USER": "editor.list@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}
    offering_editor_headers = {
        "HTTP_X_FORWARDED_USER": "offering.list@example.com",
        "HTTP_X_FORWARDED_GROUPS": "offering_editor",
    }
    viewer_headers = {
        "HTTP_X_FORWARDED_USER": "viewer.list@example.com",
        "HTTP_X_FORWARDED_GROUPS": "vendor_viewer",
    }

    assert client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": "v-list", "legal_name": "Vendor List"}),
        content_type="application/json",
        **editor_headers,
    ).status_code == 201

    assert client.post(
        "/api/v1/projects",
        data=json.dumps({"project_id": "p-list", "project_name": "Project List"}),
        content_type="application/json",
        **editor_headers,
    ).status_code == 201

    assert client.post(
        "/api/v1/vendors/v-list/offerings",
        data=json.dumps({"offering_id": "o-list", "offering_name": "Offering List", "lob": "IT"}),
        content_type="application/json",
        **editor_headers,
    ).status_code == 201

    vendor_editor_page = client.get("/vendor-360/", **editor_headers)
    assert vendor_editor_page.status_code == 200
    vendor_editor_html = vendor_editor_page.content.decode("utf-8")
    assert "Add Vendor" in vendor_editor_html
    assert "split-detail-tab-button" in vendor_editor_html

    vendor_offering_editor_page = client.get("/vendor-360/", **offering_editor_headers)
    assert vendor_offering_editor_page.status_code == 200
    assert "Add Vendor" not in vendor_offering_editor_page.content.decode("utf-8")

    project_editor_page = client.get("/projects/", **editor_headers)
    assert project_editor_page.status_code == 200
    project_editor_html = project_editor_page.content.decode("utf-8")
    assert "Add Project" in project_editor_html
    assert "Edit" in project_editor_html

    project_offering_editor_page = client.get("/projects/", **offering_editor_headers)
    assert project_offering_editor_page.status_code == 200
    project_offering_editor_html = project_offering_editor_page.content.decode("utf-8")
    assert "Add Project" not in project_offering_editor_html
    assert "/projects/p-list/edit" not in project_offering_editor_html

    offering_offering_editor_page = client.get("/offerings/", follow=True, **offering_editor_headers)
    assert offering_offering_editor_page.status_code == 200
    offering_offering_editor_html = offering_offering_editor_page.content.decode("utf-8")
    assert "New Offering" in offering_offering_editor_html
    assert "/offerings/o-list/edit" in offering_offering_editor_html

    offering_viewer_page = client.get("/offerings/", follow=True, **viewer_headers)
    assert offering_viewer_page.status_code == 200
    offering_viewer_html = offering_viewer_page.content.decode("utf-8")
    assert "New Offering" not in offering_viewer_html
    assert "/offerings/o-list/edit" not in offering_viewer_html
