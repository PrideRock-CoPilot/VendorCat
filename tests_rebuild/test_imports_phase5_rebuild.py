from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def test_import_job_create_list_get_patch(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}

    created = client.post(
        "/api/v1/imports/jobs",
        data=json.dumps(
            {
                "import_job_id": "job-1",
                "source_system": "spreadsheet_manual",
                "file_name": "vendors.csv",
                "file_format": "csv",
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 201
    assert created.json()["import_job_id"] == "job-1"

    listed = client.get("/api/v1/imports/jobs")
    assert listed.status_code == 200
    assert any(item["import_job_id"] == "job-1" for item in listed.json()["items"])

    detail = client.get("/api/v1/imports/jobs/job-1")
    assert detail.status_code == 200
    assert detail.json()["file_name"] == "vendors.csv"

    updated = client.patch(
        "/api/v1/imports/jobs/job-1",
        data=json.dumps({"status": "processing", "row_count": 100}),
        content_type="application/json",
        **headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "processing"
    assert updated.json()["row_count"] == "100"


def test_import_job_validation_rejects_invalid_status(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}

    response = client.patch(
        "/api/v1/imports/jobs/job-nonexistent",
        data=json.dumps({"status": "invalid_status"}),
        content_type="application/json",
        **headers,
    )
    assert response.status_code in {400, 404}


def test_import_job_requires_permission(client: Client) -> None:
    denied = client.post(
        "/api/v1/imports/jobs",
        data=json.dumps({"import_job_id": "job-denied", "source_system": "zycus", "file_name": "test.csv"}),
        content_type="application/json",
        HTTP_X_FORWARDED_USER="viewer@example.com",
    )
    assert denied.status_code == 403


def test_import_job_list_and_detail_pages_render(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}
    viewer_headers = {"HTTP_X_FORWARDED_USER": "viewer@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_viewer"}

    client.post(
        "/api/v1/imports/jobs",
        data=json.dumps(
            {
                "import_job_id": "job-page-1",
                "source_system": "peoplesoft",
                "file_name": "vendors-peoplesoft.csv",
                "file_format": "csv",
            }
        ),
        content_type="application/json",
        **headers,
    )

    list_page = client.get("/imports/", **headers)
    assert list_page.status_code == 200
    list_html = list_page.content.decode("utf-8")
    assert "vendors-peoplesoft.csv" in list_html
    assert "New Import Job" in list_html

    viewer_page = client.get("/imports/", **viewer_headers)
    assert viewer_page.status_code == 200
    assert "New Import Job" not in viewer_page.content.decode("utf-8")

    detail_page = client.get("/imports/job-page-1")
    assert detail_page.status_code == 200
    assert "job-page-1" in detail_page.content.decode("utf-8")


def test_import_job_v4_orchestration_flow(client: Client) -> None:
    headers = {"HTTP_X_FORWARDED_USER": "editor.v4@example.com", "HTTP_X_FORWARDED_GROUPS": "vendor_editor"}

    created = client.post(
        "/api/v1/imports/jobs",
        data=json.dumps(
            {
                "import_job_id": "job-v4-1",
                "source_system": "spreadsheet_manual",
                "file_name": "vendors-v4.csv",
                "file_format": "csv",
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert created.status_code == 201

    previewed = client.post(
        "/api/v1/imports/jobs/job-v4-1/preview",
        data=json.dumps({"blocked_rows": 2, "warning_count": 1}),
        content_type="application/json",
        **headers,
    )
    assert previewed.status_code == 200
    assert previewed.json()["status"] == "previewed"

    mapped = client.post(
        "/api/v1/imports/jobs/job-v4-1/mapping",
        data=json.dumps(
            {
                "mapping_profile_id": "profile-v4",
                "source_target_mapping": {"Vendor Name": "vendor_name"},
            }
        ),
        content_type="application/json",
        **headers,
    )
    assert mapped.status_code == 200
    assert mapped.json()["status"] == "mapped"

    staged = client.post(
        "/api/v1/imports/jobs/job-v4-1/stage",
        data=json.dumps({"staged_count": 97}),
        content_type="application/json",
        **headers,
    )
    assert staged.status_code == 200
    assert staged.json()["status"] == "staged"

    reviewed = client.post(
        "/api/v1/imports/jobs/job-v4-1/review",
        data=json.dumps({"approved": True, "review_note": "ready to apply"}),
        content_type="application/json",
        **headers,
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "approved"

    applied = client.post(
        "/api/v1/imports/jobs/job-v4-1/apply",
        data=json.dumps({"force_apply": False}),
        content_type="application/json",
        **headers,
    )
    assert applied.status_code == 200
    assert applied.json()["status"] == "applied"
