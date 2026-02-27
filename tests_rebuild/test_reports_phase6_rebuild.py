from __future__ import annotations

import json

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


ADMIN_HEADERS = {
    "HTTP_X_FORWARDED_USER": "admin@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_admin",
}
VIEWER_HEADERS = {
    "HTTP_X_FORWARDED_USER": "viewer@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_viewer",
}


def test_report_run_create_list_get_download_and_email_request() -> None:
    client = Client()

    response = client.post(
        "/api/v1/reports/runs",
        data=json.dumps(
            {
                "report_code": "vendor_summary",
                "filters": {"region": "us", "active_only": True},
                "output_format": "csv",
            }
        ),
        content_type="application/json",
        **ADMIN_HEADERS,
    )
    assert response.status_code == 201
    created = response.json()
    run_id = created["run_id"]
    assert created["report_code"] == "vendor_summary"
    assert created["status"] == "queued"

    patch_response = client.patch(
        f"/api/v1/reports/runs/{run_id}",
        data=json.dumps({"status": "completed", "row_count": 4}),
        content_type="application/json",
        **ADMIN_HEADERS,
    )
    assert patch_response.status_code == 200

    list_response = client.get("/api/v1/reports/runs", **ADMIN_HEADERS)
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert any(item["run_id"] == run_id for item in items)

    detail_response = client.get(f"/api/v1/reports/runs/{run_id}", **ADMIN_HEADERS)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["run_id"] == run_id
    assert detail["status"] == "completed"

    download_response = client.get(f"/api/v1/reports/runs/{run_id}/download", **ADMIN_HEADERS)
    assert download_response.status_code == 200
    assert download_response["Content-Type"].startswith("text/csv")
    assert b"vendor_summary" in download_response.content

    email_response = client.post(
        "/api/v1/reports/email-requests",
        data=json.dumps(
            {
                "run_id": run_id,
                "email_to": ["ops@example.com", "owner@example.com"],
            }
        ),
        content_type="application/json",
        **ADMIN_HEADERS,
    )
    assert email_response.status_code == 201
    email_payload = email_response.json()
    assert email_payload["run_id"] == run_id
    assert email_payload["email_to"] == ["ops@example.com", "owner@example.com"]


def test_report_run_validation_rejects_invalid_output_format() -> None:
    client = Client()
    response = client.post(
        "/api/v1/reports/runs",
        data=json.dumps(
            {
                "report_code": "vendor_summary",
                "filters": {},
                "output_format": "pdf",
            }
        ),
        content_type="application/json",
        **ADMIN_HEADERS,
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "invalid_request"


def test_report_permissions_enforced_for_mutations() -> None:
    client = Client()

    create_denied = client.post(
        "/api/v1/reports/runs",
        data=json.dumps(
            {
                "report_code": "vendor_summary",
                "filters": {},
                "output_format": "preview",
            }
        ),
        content_type="application/json",
        **VIEWER_HEADERS,
    )
    assert create_denied.status_code == 403

    # Viewer still has report.read and can list.
    list_allowed = client.get("/api/v1/reports/runs", **VIEWER_HEADERS)
    assert list_allowed.status_code == 200

    email_denied = client.post(
        "/api/v1/reports/email-requests",
        data=json.dumps({"run_id": "missing", "email_to": ["nobody@example.com"]}),
        content_type="application/json",
        **VIEWER_HEADERS,
    )
    assert email_denied.status_code == 403


def test_reports_pages_render() -> None:
    client = Client()
    create = client.post(
        "/api/v1/reports/runs",
        data=json.dumps(
            {
                "report_code": "page_report",
                "filters": {},
                "output_format": "preview",
            }
        ),
        content_type="application/json",
        **ADMIN_HEADERS,
    )
    assert create.status_code == 201
    run_id = create.json()["run_id"]

    list_page = client.get("/reports/", follow=True, **VIEWER_HEADERS)
    assert list_page.status_code == 200
    assert b"Reports" in list_page.content
    assert b"Run Report" not in list_page.content

    detail_page = client.get(f"/reports/{run_id}", follow=True, **VIEWER_HEADERS)
    assert detail_page.status_code == 200
    assert run_id.encode("utf-8") in detail_page.content


def test_reports_pages_restricted_without_report_read() -> None:
    client = Client()
    create = client.post(
        "/api/v1/reports/runs",
        data=json.dumps(
            {
                "report_code": "restricted_report",
                "filters": {},
                "output_format": "preview",
            }
        ),
        content_type="application/json",
        **ADMIN_HEADERS,
    )
    assert create.status_code == 201
    run_id = create.json()["run_id"]

    restricted_list = client.get(
        "/reports/",
        follow=True,
        HTTP_X_FORWARDED_USER="user.no.read@example.com",
        HTTP_X_FORWARDED_GROUPS="authenticated",
    )
    assert restricted_list.status_code == 200
    html = restricted_list.content.decode("utf-8")
    assert "Reports restricted" in html
    assert "Run Report" not in html

    restricted_detail = client.get(
        f"/reports/{run_id}",
        follow=True,
        HTTP_X_FORWARDED_USER="user.no.read@example.com",
        HTTP_X_FORWARDED_GROUPS="authenticated",
    )
    assert restricted_detail.status_code == 200
    assert "Report details are restricted for your current role." in restricted_detail.content.decode("utf-8")
