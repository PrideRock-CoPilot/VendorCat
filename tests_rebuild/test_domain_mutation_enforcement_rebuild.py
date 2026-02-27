from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def test_vendor_project_import_report_mutations_require_editor_permissions(client: Client) -> None:
    editor_headers = {"HTTP_X_FORWARDED_USER": "editor.user@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}

    vendor_create = client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": "v-1"}),
        content_type="application/json",
        **editor_headers,
    )
    assert vendor_create.status_code == 201

    vendor_patch = client.patch(
        "/api/v1/vendors/v-1",
        data=json.dumps({"display_name": "New"}),
        content_type="application/json",
        **editor_headers,
    )
    assert vendor_patch.status_code == 200

    project_create = client.post(
        "/api/v1/projects",
        data=json.dumps({"project_id": "p-1"}),
        content_type="application/json",
        **editor_headers,
    )
    assert project_create.status_code == 201

    project_patch = client.patch(
        "/api/v1/projects/p-1",
        data=json.dumps({"project_name": "Updated"}),
        content_type="application/json",
        **editor_headers,
    )
    assert project_patch.status_code == 200

    import_create = client.post(
        "/api/v1/imports/jobs",
        data=json.dumps({"source_system": "erp", "source_object": "vendor", "file_name": "vendors.csv"}),
        content_type="application/json",
        **editor_headers,
    )
    assert import_create.status_code == 201

    report_run = client.post(
        "/api/v1/reports/runs",
        data=json.dumps({"report_code": "vendor_audit"}),
        content_type="application/json",
        **editor_headers,
    )
    assert report_run.status_code == 201


def test_vendor_mutation_denied_for_anonymous_identity(client: Client) -> None:
    response = client.post(
        "/api/v1/vendors",
        data=json.dumps({"vendor_id": "v-denied"}),
        content_type="application/json",
    )
    assert response.status_code == 403


def test_workflow_decision_requires_workflow_reviewer(client: Client) -> None:
    denied = client.post(
        "/api/v1/workflows/decisions",
        data=json.dumps({"decision": "approved"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="editor.only@example.com",
        HTTP_X_FORWARDED_GROUPS="vendor_editor",
    )
    assert denied.status_code == 403

    allowed = client.post(
        "/api/v1/workflows/decisions",
        data=json.dumps({"decision": "approved"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="reviewer.user@example.com",
        HTTP_X_FORWARDED_GROUPS="workflow_reviewer",
    )
    assert allowed.status_code == 201


def test_import_requires_source_system(client: Client) -> None:
    response = client.post(
        "/api/v1/imports/jobs",
        data=json.dumps({"source_system": "", "file_name": "vendors.csv"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="editor.user2@example.com",
        HTTP_X_FORWARDED_GROUPS="vendor_editor",
    )
    assert response.status_code == 400
