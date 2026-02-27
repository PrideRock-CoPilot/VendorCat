from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.identity.models import AccessRequest, RoleAssignment, TermsAcceptance, UserDirectory

pytestmark = pytest.mark.django_db


def test_identity_endpoint_syncs_user_directory(client: Client) -> None:
    response = client.get(
        "/api/v1/identity",
        HTTP_X_FORWARDED_USER="person@example.com",
        HTTP_X_FORWARDED_NAME="Person",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["user_directory"]["user_principal"] == "person@example.com"
    assert UserDirectory.objects.filter(user_principal="person@example.com").exists()


def test_access_request_requires_authenticated_identity(client: Client) -> None:
    forbidden = client.post(
        "/api/v1/access/requests",
        data=json.dumps({"requested_role": "vendor_editor", "justification": "Need edit access"}),
        content_type="application/json",
    )
    assert forbidden.status_code == 403

    created = client.post(
        "/api/v1/access/requests",
        data=json.dumps({"requested_role": "vendor_editor", "justification": "Need edit access"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="requestor@example.com",
    )
    assert created.status_code == 201
    assert AccessRequest.objects.filter(requested_by_principal="requestor@example.com").exists()


def test_terms_acceptance_is_idempotent_per_version(client: Client) -> None:
    first = client.post(
        "/api/v1/access/terms/accept",
        data=json.dumps({"terms_version": "2026-02"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="terms.user@example.com",
    )
    assert first.status_code == 201
    assert first.json()["created"] is True

    second = client.post(
        "/api/v1/access/terms/accept",
        data=json.dumps({"terms_version": "2026-02"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="terms.user@example.com",
    )
    assert second.status_code == 201
    assert second.json()["created"] is False
    assert TermsAcceptance.objects.filter(user_principal="terms.user@example.com", terms_version="2026-02").count() == 1


def test_first_admin_bootstrap_is_one_time_operation(client: Client) -> None:
    first = client.post(
        "/api/v1/access/bootstrap-first-admin",
        HTTP_X_FORWARDED_USER="admin.seed@example.com",
    )
    assert first.status_code == 201
    assert RoleAssignment.objects.filter(user_principal="admin.seed@example.com", role="vendor_admin").exists()

    second = client.post(
        "/api/v1/access/bootstrap-first-admin",
        HTTP_X_FORWARDED_USER="other.user@example.com",
    )
    assert second.status_code == 403
