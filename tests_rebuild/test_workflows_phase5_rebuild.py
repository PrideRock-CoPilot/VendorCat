from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def test_workflow_decision_create_list_get_patch(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "reviewer@example.com", "HTTP_X_FORWARDED_GROUPS": "workflow_reviewer"}

    created = client.post(
        "/api/v1/workflows/decisions",
        data=json.dumps(
            {
                "decision_id": "dec-1",
                "workflow_name": "vendor_approval",
                "action": "approve",
                "context": {"vendor_id": "v-1"},
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 201
    assert created.json()["decision_id"] == "dec-1"

    listed = client.get("/api/v1/workflows/decisions")
    assert listed.status_code == 200
    assert any(item["decision_id"] == "dec-1" for item in listed.json()["items"])

    detail = client.get("/api/v1/workflows/decisions/dec-1")
    assert detail.status_code == 200
    assert detail.json()["workflow_name"] == "vendor_approval"

    updated = client.patch(
        "/api/v1/workflows/decisions/dec-1",
        data=json.dumps({"status": "approved", "reviewed_by": "reviewer@example.com"}),
        content_type="application/json",
        **headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "approved"


def test_workflow_decision_validation_rejects_invalid_status(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "reviewer@example.com", "HTTP_X_FORWARDED_GROUPS": "workflow_reviewer"}

    client.post(
        "/api/v1/workflows/decisions",
        data=json.dumps(
            {
                "decision_id": "dec-validate",
                "workflow_name": "test",
                "action": "test_action",
            }
        ),
        content_type="application/json",
        **headers,
    )

    bad_status = client.patch(
        "/api/v1/workflows/decisions/dec-validate",
        data=json.dumps({"status": "invalid_status"}),
        content_type="application/json",
        **headers,
    )
    assert bad_status.status_code == 400


def test_workflow_decision_requires_permission(client: Client) -> None:
    denied = client.post(
        "/api/v1/workflows/decisions",
        data=json.dumps({"decision_id": "dec-denied", "workflow_name": "test", "action": "test"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="viewer@example.com",
    )
    assert denied.status_code == 403


def test_workflow_decision_list_and_detail_pages_render(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "reviewer@example.com", "HTTP_X_FORWARDED_GROUPS": "workflow_reviewer"}
    viewer_headers = {"HTTP_X_FORWARDED_USER": "viewer@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_viewer"}

    client.post(
        "/api/v1/workflows/decisions",
        data=json.dumps(
            {
                "decision_id": "dec-page-1",
                "workflow_name": "compliance_review",
                "action": "review_compliance",
                "context": {"entity_type": "vendor"},
            }
        ),
        content_type="application/json",
        **headers,
    )

    list_page = client.get("/workflows/", **headers)
    assert list_page.status_code == 200
    list_html = list_page.content.decode("utf-8")
    assert "compliance_review" in list_html
    assert "New Workflow" in list_html

    viewer_page = client.get("/workflows/", **viewer_headers)
    assert viewer_page.status_code == 200
    assert "New Workflow" not in viewer_page.content.decode("utf-8")

    detail_page = client.get("/workflows/dec-page-1")
    assert detail_page.status_code == 200
    assert "dec-page-1" in detail_page.content.decode("utf-8")


def test_workflow_open_next_and_transition_flow(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "reviewer2@example.com", "HTTP_X_FORWARDED_GROUPS": "workflow_reviewer"}

    client.post(
        "/api/v1/workflows/decisions",
        data=json.dumps(
            {
                "decision_id": "dec-next-1",
                "workflow_name": "vendor_changes",
                "action": "review_change",
            }
        ),
        content_type="application/json",
        **headers,
    )

    open_next = client.get("/api/v1/workflows/decisions/open-next?workflow_name=vendor_changes")
    assert open_next.status_code == 200
    assert open_next.json()["decision_id"] == "dec-next-1"
    assert open_next.json()["status"] == "pending"

    transitioned = client.post(
        "/api/v1/workflows/decisions/dec-next-1/transition",
        data=json.dumps({"action": "approve", "review_note": "approved for rollout"}),
        content_type="application/json",
        **headers,
    )
    assert transitioned.status_code == 200
    assert transitioned.json()["status"] == "approved"
    assert transitioned.json()["review_note"] == "approved for rollout"


def test_workflow_transition_validation_and_permission(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "reviewer3@example.com", "HTTP_X_FORWARDED_GROUPS": "workflow_reviewer"}

    client.post(
        "/api/v1/workflows/decisions",
        data=json.dumps(
            {
                "decision_id": "dec-transition-invalid",
                "workflow_name": "vendor_changes",
                "action": "review_change",
            }
        ),
        content_type="application/json",
        **headers,
    )

    invalid = client.post(
        "/api/v1/workflows/decisions/dec-transition-invalid/transition",
        data=json.dumps({"action": "reopen"}),
        content_type="application/json",
        **headers,
    )
    assert invalid.status_code == 400

    denied = client.post(
        "/api/v1/workflows/decisions/dec-transition-invalid/transition",
        data=json.dumps({"action": "approve"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="viewer@example.com",
    )
    assert denied.status_code == 403
