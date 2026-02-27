from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def test_demo_create_list_get_patch(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.demo@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}

    created = client.post(
        "/api/v1/demos",
        data=json.dumps(
            {
                "demo_id": "demo-1",
                "demo_name": "Demo One",
                "demo_type": "live",
                "demo_outcome": "unknown",
                "lifecycle_state": "active",
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 201
    assert created.json()["demo_id"] == "demo-1"

    listed = client.get("/api/v1/demos")
    assert listed.status_code == 200
    assert any(item["demo_id"] == "demo-1" for item in listed.json()["items"])

    detail = client.get("/api/v1/demos/demo-1")
    assert detail.status_code == 200
    assert detail.json()["demo_name"] == "Demo One"

    updated = client.patch(
        "/api/v1/demos/demo-1",
        data=json.dumps({"demo_outcome": "selected"}),
        content_type="application/json",
        **headers,
    )
    assert updated.status_code == 200
    assert updated.json()["demo_outcome"] == "selected"


def test_demo_validation_rejects_invalid_values(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.demo2@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}

    bad_type = client.post(
        "/api/v1/demos",
        data=json.dumps({"demo_id": "demo-bad", "demo_name": "Bad", "demo_type": "weird"}),
        content_type="application/json",
        **headers,
    )
    assert bad_type.status_code == 400

    bad_lifecycle = client.post(
        "/api/v1/demos",
        data=json.dumps({"demo_id": "demo-bad2", "demo_name": "Bad2", "lifecycle_state": "unknown"}),
        content_type="application/json",
        **headers,
    )
    assert bad_lifecycle.status_code == 400


def test_demo_requires_permission(client: Client) -> None:
    denied = client.post(
        "/api/v1/demos",
        data=json.dumps({"demo_id": "demo-denied", "demo_name": "Denied"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="viewer@example.com",
    )
    assert denied.status_code == 403


def test_demo_list_and_detail_pages_render(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.demo@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}

    client.post(
        "/api/v1/demos",
        data=json.dumps(
            {
                "demo_id": "demo-page-1",
                "demo_name": "Demo Page Test",
                "demo_type": "recorded",
                "demo_outcome": "selected",
                "lifecycle_state": "active",
            }
        ),
        content_type="application/json",
        **headers,
    )

    list_page = client.get("/demos/")
    assert list_page.status_code == 200
    assert "Demo Page Test" in list_page.content.decode("utf-8")

    detail_page = client.get("/demos/demo-page-1")
    assert detail_page.status_code == 200
    assert "demo-page-1" in detail_page.content.decode("utf-8")

