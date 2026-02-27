from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


EDITOR_HEADERS = {
    "HTTP_X_FORWARDED_USER": "project.editor@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_editor",
}


def _create_project(client: Client, project_id: str = "p-sections-1") -> None:
    created = client.post(
        "/api/v1/projects",
        data=json.dumps(
            {
                "project_id": project_id,
                "project_name": "Project Sections",
                "owner_principal": "owner.sections@example.com",
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert created.status_code == 201


def test_project_sections_list_endpoint(client: Client) -> None:
    _create_project(client)

    response = client.get("/api/v1/projects/p-sections-1/sections")
    assert response.status_code == 200
    items = response.json()["items"]
    keys = {item["section_key"] for item in items}
    assert {"summary", "ownership", "offerings", "demos", "docs", "notes"}.issubset(keys)


def test_project_section_change_request_creates_workflow_decision(client: Client) -> None:
    _create_project(client)

    created = client.post(
        "/api/v1/projects/p-sections-1/sections/ownership/requests",
        data=json.dumps(
            {
                "payload": {
                    "owner_principal": "new.owner@example.com",
                    "reason": "handoff",
                }
            }
        ),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert created.status_code == 201
    assert created.json()["status"] == "pending"
    assert created.json()["workflow_name"] == "project_section_change"

    decisions = client.get("/api/v1/workflows/decisions")
    assert decisions.status_code == 200
    assert any(item["decision_id"] == created.json()["decision_id"] for item in decisions.json()["items"])


def test_project_section_change_request_validation_and_permissions(client: Client) -> None:
    _create_project(client)

    invalid_section = client.post(
        "/api/v1/projects/p-sections-1/sections/invalid/requests",
        data=json.dumps({"payload": {"x": 1}}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert invalid_section.status_code == 400

    bad_payload = client.post(
        "/api/v1/projects/p-sections-1/sections/notes/requests",
        data=json.dumps({"payload": "not-an-object"}),
        content_type="application/json",
        **EDITOR_HEADERS,
    )
    assert bad_payload.status_code == 400

    denied = client.post(
        "/api/v1/projects/p-sections-1/sections/notes/requests",
        data=json.dumps({"payload": {"note": "x"}}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="viewer.project@example.com",
    )
    assert denied.status_code == 403
