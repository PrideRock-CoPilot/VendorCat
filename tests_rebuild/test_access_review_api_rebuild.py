from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.identity.models import AccessRequest, RoleAssignment

pytestmark = pytest.mark.django_db


def test_review_api_requires_reviewer_permission(client: Client) -> None:
    created = client.post(
        "/api/v1/access/requests",
        data=json.dumps({"requested_role": "vendor_editor", "justification": "Need edit access"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="requester@example.com",
    )
    assert created.status_code == 201
    request_id = int(created.json()["access_request_id"])

    denied = client.post(
        f"/api/v1/access/requests/{request_id}/review",
        data=json.dumps({"decision": "approved", "note": "ok"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="viewer@example.com",
    )
    assert denied.status_code == 403


def test_review_api_approves_request_and_assigns_role(client: Client) -> None:
    created = client.post(
        "/api/v1/access/requests",
        data=json.dumps({"requested_role": "vendor_editor", "justification": "Need edit access"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="requester2@example.com",
    )
    assert created.status_code == 201
    request_id = int(created.json()["access_request_id"])

    reviewed = client.post(
        f"/api/v1/access/requests/{request_id}/review",
        data=json.dumps({"decision": "approved", "note": "approved"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="reviewer@example.com",
        HTTP_X_FORWARDED_GROUPS="workflow_reviewer",
    )
    assert reviewed.status_code == 200
    payload = reviewed.json()
    assert payload["status"] == "approved"
    assert payload["assignment_id"]
    assert RoleAssignment.objects.filter(user_principal="requester2@example.com", role="vendor_editor").exists()


def test_list_api_returns_pending_items_for_reviewer(client: Client) -> None:
    AccessRequest.objects.create(
        requested_by_principal="pending.user@example.com",
        requested_role="vendor_editor",
        justification="Need edit access",
        status="pending",
    )

    response = client.get(
        "/api/v1/access/requests/list",
        HTTP_X_FORWARDED_USER="reviewer.list@example.com",
        HTTP_X_FORWARDED_GROUPS="workflow_reviewer",
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert any(item["requested_by_principal"] == "pending.user@example.com" for item in items)
