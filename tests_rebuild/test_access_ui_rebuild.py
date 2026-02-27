from __future__ import annotations

import pytest
from django.test import Client

from apps.identity.models import AccessRequest, RoleAssignment, TermsAcceptance

pytestmark = pytest.mark.django_db


def test_access_pages_render(client: Client) -> None:
    for path in ["/access/", "/access/requests", "/access/requests/review", "/access/terms", "/access/bootstrap-first-admin"]:
        response = client.get(path)
        assert response.status_code == 200


def test_access_request_ui_post_creates_request(client: Client) -> None:
    response = client.post(
        "/access/requests",
        data={"requested_role": "vendor_editor", "justification": "Need editor"},
        HTTP_X_FORWARDED_USER="ui.requester@example.com",
    )
    assert response.status_code == 200
    assert AccessRequest.objects.filter(requested_by_principal="ui.requester@example.com", requested_role="vendor_editor").exists()


def test_access_review_ui_requires_reviewer(client: Client) -> None:
    pending = AccessRequest.objects.create(
        requested_by_principal="ui.pending@example.com",
        requested_role="vendor_editor",
        justification="Need editor",
        status="pending",
    )

    denied = client.post(
        "/access/requests/review",
        data={"request_id": str(pending.id), "decision": "approved", "note": "ok"},
        HTTP_X_FORWARDED_USER="ui.viewer@example.com",
    )
    assert denied.status_code == 403

    allowed = client.post(
        "/access/requests/review",
        data={"request_id": str(pending.id), "decision": "approved", "note": "ok"},
        HTTP_X_FORWARDED_USER="ui.reviewer@example.com",
        HTTP_X_FORWARDED_GROUPS="workflow_reviewer",
    )
    assert allowed.status_code == 200


def test_terms_acceptance_ui_post_creates_row(client: Client) -> None:
    response = client.post(
        "/access/terms",
        data={"terms_version": "2026-02"},
        HTTP_X_FORWARDED_USER="ui.terms@example.com",
    )
    assert response.status_code == 200
    assert TermsAcceptance.objects.filter(user_principal="ui.terms@example.com", terms_version="2026-02").exists()


def test_first_admin_bootstrap_ui_is_one_time(client: Client) -> None:
    first = client.post(
        "/access/bootstrap-first-admin",
        HTTP_X_FORWARDED_USER="ui.admin@example.com",
    )
    assert first.status_code == 200
    assert RoleAssignment.objects.filter(user_principal="ui.admin@example.com", role="vendor_admin").exists()

    second = client.post(
        "/access/bootstrap-first-admin",
        HTTP_X_FORWARDED_USER="ui.other@example.com",
    )
    assert second.status_code == 403
