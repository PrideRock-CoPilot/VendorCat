from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.identity.models import GroupRoleAssignment, RoleAssignment, ScopeGrant

pytestmark = pytest.mark.django_db


def test_admin_can_assign_and_revoke_user_role(client: Client) -> None:
    reviewer_headers = {
        "HTTP_X_FORWARDED_USER": "rbac.admin@example.com",
        "HTTP_X_FORWARDED_GROUPS": "workflow_reviewer",
    }

    assigned = client.post(
        "/api/v1/admin/roles/assign",
        data=json.dumps({"target_user": "editor.user@example.com", "role": "vendor_editor"}),
        content_type="application/json",
        **reviewer_headers,
    )
    assert assigned.status_code == 201
    assert RoleAssignment.objects.filter(user_principal="editor.user@example.com", role="vendor_editor").exists()

    revoked = client.post(
        "/api/v1/admin/roles/revoke",
        data=json.dumps({"target_user": "editor.user@example.com", "role": "vendor_editor"}),
        content_type="application/json",
        **reviewer_headers,
    )
    assert revoked.status_code == 200
    assert not RoleAssignment.objects.filter(user_principal="editor.user@example.com", role="vendor_editor").exists()


def test_admin_can_assign_group_role_and_group_member_can_review_access(client: Client) -> None:
    reviewer_headers = {
        "HTTP_X_FORWARDED_USER": "rbac.admin@example.com",
        "HTTP_X_FORWARDED_GROUPS": "workflow_reviewer",
    }

    response = client.post(
        "/api/v1/admin/groups/assign",
        data=json.dumps({"target_group": "AD-Vendor-Reviewers", "role": "workflow_reviewer"}),
        content_type="application/json",
        **reviewer_headers,
    )
    assert response.status_code == 201
    assert GroupRoleAssignment.objects.filter(group_principal="group:ad-vendor-reviewers", role="workflow_reviewer").exists()

    as_group_member = client.get(
        "/api/v1/access/requests/list",
        HTTP_X_FORWARDED_USER="group.member@example.com",
        HTTP_X_FORWARDED_GROUPS="AD-Vendor-Reviewers",
    )
    assert as_group_member.status_code == 200


def test_admin_can_grant_and_revoke_scope(client: Client) -> None:
    reviewer_headers = {
        "HTTP_X_FORWARDED_USER": "rbac.admin@example.com",
        "HTTP_X_FORWARDED_GROUPS": "workflow_reviewer",
    }

    granted = client.post(
        "/api/v1/admin/scopes/grant",
        data=json.dumps({"target_user": "scope.user@example.com", "org_id": "FIN-OPS", "scope_level": "edit"}),
        content_type="application/json",
        **reviewer_headers,
    )
    assert granted.status_code == 201
    assert ScopeGrant.objects.filter(user_principal="scope.user@example.com", org_id="FIN-OPS", scope_level="edit").exists()

    revoked = client.post(
        "/api/v1/admin/scopes/revoke",
        data=json.dumps({"target_user": "scope.user@example.com", "org_id": "FIN-OPS", "scope_level": "edit"}),
        content_type="application/json",
        **reviewer_headers,
    )
    assert revoked.status_code == 200
    assert not ScopeGrant.objects.filter(user_principal="scope.user@example.com", org_id="FIN-OPS", scope_level="edit").exists()
