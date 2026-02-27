from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.identity.models import AccessRequest

pytestmark = pytest.mark.django_db


def test_pending_approvals_queue_and_open_next(client: Client) -> None:
    AccessRequest.objects.create(
        requested_by_principal="pending.queue@example.com",
        requested_role="vendor_editor",
        justification="Need queue approval",
        status="pending",
    )

    queue = client.get(
        "/api/v1/pending-approvals/queue",
        HTTP_X_FORWARDED_USER="reviewer.queue@example.com",
        HTTP_X_FORWARDED_GROUPS="workflow_reviewer",
    )
    assert queue.status_code == 200
    assert queue.json()["count"] >= 1

    next_item = client.post(
        "/api/v1/pending-approvals/queue/open-next",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="reviewer.queue@example.com",
        HTTP_X_FORWARDED_GROUPS="workflow_reviewer",
    )
    assert next_item.status_code == 200
    assert next_item.json()["item"]["requested_by_principal"] == "pending.queue@example.com"


def test_pending_approvals_decision_updates_request(client: Client) -> None:
    request_row = AccessRequest.objects.create(
        requested_by_principal="pending.decision@example.com",
        requested_role="vendor_editor",
        justification="Need decision",
        status="pending",
    )

    decision = client.post(
        f"/api/v1/pending-approvals/queue/{request_row.id}/decision",
        data=json.dumps({"decision": "approved", "note": "approved by queue"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="reviewer.decision@example.com",
        HTTP_X_FORWARDED_GROUPS="workflow_reviewer",
    )
    assert decision.status_code == 200

    request_row.refresh_from_db()
    assert request_row.status == "approved"


def test_pending_approvals_queue_page_renders(client: Client) -> None:
    response = client.get(
        "/pending-approvals/queue",
        HTTP_X_FORWARDED_USER="reviewer.ui@example.com",
        HTTP_X_FORWARDED_GROUPS="workflow_reviewer",
    )
    assert response.status_code == 200
    assert "Pending Approvals Queue" in response.content.decode("utf-8")
