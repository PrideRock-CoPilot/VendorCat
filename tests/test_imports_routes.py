from __future__ import annotations

import re
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.core.runtime import get_config, get_repo
from vendor_catalog_app.web.routers import imports as imports_router

REVIEW_AREA_ORDER = [
    "vendor",
    "vendor_identifier",
    "vendor_owner",
    "vendor_contact",
    "offering",
    "offering_owner",
    "offering_contact",
    "contract",
    "project",
    "invoice",
    "payment",
]


@pytest.fixture()
def _clear_import_state() -> None:
    imports_router._IMPORT_PREVIEW_STORE.clear()
    yield
    imports_router._IMPORT_PREVIEW_STORE.clear()


def _preview_upload(
    client: TestClient,
    *,
    file_name: str,
    payload: bytes | str,
    source_system: str = "spreadsheet_manual",
    layout: str = "vendors",
    source_object: str = "unit-test-feed",
    format_hint: str = "auto",
    xml_record_path: str = "",
) -> object:
    return client.post(
        "/imports/preview",
        files={"file": (file_name, payload, "text/plain")},
        data={
            "layout": layout,
            "source_system": source_system,
            "source_object": source_object,
            "format_hint": format_hint,
            "xml_record_path": xml_record_path,
        },
        follow_redirects=False,
    )


def _extract_job_id_from_mapping_redirect(response) -> str:
    assert response.status_code == 303
    location = str(response.headers.get("location", ""))
    match = re.search(r"/imports/jobs/([^/]+)/mapping$", location)
    assert match is not None
    return str(match.group(1))


def test_import_template_download_returns_csv(
    _clear_import_state: None,
    isolated_local_db: Path,
) -> None:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)
    response = client.get("/imports/templates/vendors.csv")
    assert response.status_code == 200
    assert "text/csv" in str(response.headers.get("content-type", ""))
    assert "legal_name" in response.text
    assert "owner_org_id" in response.text


def test_import_upload_requires_source_system(
    _clear_import_state: None,
    isolated_local_db: Path,
) -> None:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/imports/preview",
        files={"file": ("vendors.csv", b"legal_name\nAcme\n", "text/csv")},
        data={"layout": "vendors", "source_system": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Select a valid Source System before continuing." in response.text


def test_import_preview_mapping_page_shows_columns_and_samples(
    _clear_import_state: None,
    isolated_local_db: Path,
) -> None:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)
    unique_name = f"Acme Imports V4 {uuid4().hex[:8]}"

    preview = _preview_upload(
        client,
        file_name="vendors.csv",
        payload=(
            "legal_name,display_name,owner_org_id,lifecycle_state,risk_tier\n"
            f"{unique_name},{unique_name},IT,draft,medium\n"
        ).encode("utf-8"),
    )
    job_id = _extract_job_id_from_mapping_redirect(preview)

    mapping = client.get(f"/imports/jobs/{job_id}/mapping")
    assert mapping.status_code == 200
    assert "Map Columns" in mapping.text
    assert "Column Mapping" in mapping.text
    assert "Sample Rows (First 5)" in mapping.text
    assert "Approval Gate:" in mapping.text
    assert "legal_name" in mapping.text


def test_import_preview_multi_file_creates_single_job_with_combined_rows(
    _clear_import_state: None,
    isolated_local_db: Path,
) -> None:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)
    repo = get_repo()

    response = client.post(
        "/imports/preview",
        files=[
            ("files", ("vendors_part_1.csv", b"legal_name\nAcme Multi A\n", "text/csv")),
            ("files", ("vendors_part_2.csv", b"legal_name\nAcme Multi B\n", "text/csv")),
        ],
        data={"layout": "vendors", "source_system": "spreadsheet_manual", "source_object": "multi-file-test"},
        follow_redirects=False,
    )
    job_id = _extract_job_id_from_mapping_redirect(response)
    job = repo.get_import_job(job_id)
    assert isinstance(job, dict)
    assert int(job.get("row_count") or 0) >= 2


def test_mapping_submit_pending_blocks_stage_until_admin_approval(
    _clear_import_state: None,
    isolated_local_db: Path,
) -> None:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)
    unique_name = f"Blue Ridge Imports {uuid4().hex[:8]}"

    preview = _preview_upload(
        client,
        file_name="vendors.csv",
        payload=(
            "legal_name,display_name,owner_org_id,lifecycle_state,risk_tier\n"
            f"{unique_name},{unique_name},FIN,draft,low\n"
        ).encode("utf-8"),
    )
    job_id = _extract_job_id_from_mapping_redirect(preview)

    submitted = client.post(
        f"/imports/jobs/{job_id}/mapping/submit",
        data={"proposed_profile_name": f"v4 test profile {uuid4().hex[:6]}"},
        follow_redirects=True,
    )
    assert submitted.status_code == 200
    assert "Mapping submitted for admin approval." in submitted.text

    blocked = client.post(
        f"/imports/jobs/{job_id}/stage",
        follow_redirects=True,
    )
    assert blocked.status_code == 200
    assert "pending admin approval" in blocked.text.lower()


def test_admin_import_mappings_page_lists_pending_requests(
    _clear_import_state: None,
    isolated_local_db: Path,
) -> None:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)
    repo = get_repo()
    unique_name = f"Queued Vendor {uuid4().hex[:8]}"

    preview = _preview_upload(
        client,
        file_name="vendors.csv",
        payload=(
            "legal_name,display_name,owner_org_id,lifecycle_state,risk_tier\n"
            f"{unique_name},{unique_name},FIN,draft,low\n"
        ).encode("utf-8"),
    )
    job_id = _extract_job_id_from_mapping_redirect(preview)
    _ = client.post(
        f"/imports/jobs/{job_id}/mapping/submit",
        data={"proposed_profile_name": f"queue-profile-{uuid4().hex[:6]}"},
        follow_redirects=False,
    )
    job = repo.get_import_job(job_id)
    assert isinstance(job, dict)
    request_id = str(job.get("mapping_request_id") or "").strip()
    assert request_id

    admin_page = client.get("/admin/import-mappings?status=pending")
    assert admin_page.status_code == 200
    assert "Import Mappings" in admin_page.text
    assert request_id in admin_page.text


def test_admin_mapping_approval_unblocks_stage_review_and_apply(
    _clear_import_state: None,
    isolated_local_db: Path,
) -> None:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)
    repo = get_repo()
    unique_name = f"Operational Vendor {uuid4().hex[:10]}"

    preview = _preview_upload(
        client,
        file_name="vendors.csv",
        payload=(
            "legal_name,display_name,owner_org_id,lifecycle_state,risk_tier\n"
            f"{unique_name},{unique_name},OPS,draft,medium\n"
        ).encode("utf-8"),
    )
    job_id = _extract_job_id_from_mapping_redirect(preview)

    _ = client.post(
        f"/imports/jobs/{job_id}/mapping/submit",
        data={"proposed_profile_name": f"ops-profile-{uuid4().hex[:6]}"},
        follow_redirects=False,
    )

    job = repo.get_import_job(job_id)
    assert isinstance(job, dict)
    request_id = str(job.get("mapping_request_id") or "").strip()
    assert request_id

    reviewed = client.post(
        "/admin/import-mappings/review",
        data={
            "profile_request_id": request_id,
            "decision": "approved",
            "review_note": "approved by test",
            "status": "pending",
        },
        follow_redirects=False,
    )
    assert reviewed.status_code == 303

    staged = client.post(
        f"/imports/jobs/{job_id}/stage",
        follow_redirects=False,
    )
    assert staged.status_code == 303
    assert str(staged.headers.get("location", "")).endswith(f"/imports/jobs/{job_id}/review/vendor")

    for index, area_key in enumerate(REVIEW_AREA_ORDER):
        confirm = client.post(
            f"/imports/jobs/{job_id}/review/{area_key}/confirm",
            data={},
            follow_redirects=False,
        )
        assert confirm.status_code == 303
        location = str(confirm.headers.get("location", ""))
        if index < len(REVIEW_AREA_ORDER) - 1:
            assert location.endswith(f"/imports/jobs/{job_id}/review/{REVIEW_AREA_ORDER[index + 1]}")
        else:
            assert location.endswith(f"/imports/jobs/{job_id}/final")

    final_page = client.get(f"/imports/jobs/{job_id}/final")
    assert final_page.status_code == 200
    assert "Final Review And Apply" in final_page.text
    assert "Apply Import" in final_page.text

    applied = client.post(
        f"/imports/jobs/{job_id}/apply",
        data={"final_confirm": "true", "reason": "approved test apply"},
        follow_redirects=True,
    )
    assert applied.status_code == 200
    assert "Apply Results" in applied.text

    refreshed = repo.get_import_job(job_id)
    assert isinstance(refreshed, dict)
    assert str(refreshed.get("status") or "").strip().lower() in {"applied", "applied_with_errors"}


def test_import_preview_xml_with_record_path_shows_nested_columns(
    _clear_import_state: None,
    isolated_local_db: Path,
) -> None:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)

    xml_payload = (
        "<root><vendors>"
        "<vendor><company_name>Alpha Co</company_name><owner_org>FIN</owner_org></vendor>"
        "<vendor><company_name>Beta Co</company_name><owner_org>IT</owner_org></vendor>"
        "</vendors></root>"
    )
    preview = _preview_upload(
        client,
        file_name="vendors.xml",
        payload=xml_payload,
        format_hint="xml",
        xml_record_path="root.vendors.vendor",
    )
    job_id = _extract_job_id_from_mapping_redirect(preview)
    mapping = client.get(f"/imports/jobs/{job_id}/mapping")
    assert mapping.status_code == 200
    assert "vendor.company_name" in mapping.text
    assert "Alpha Co" in mapping.text


def test_import_preview_wizard_xml_fixture_autodetects_vendor_records(
    _clear_import_state: None,
    isolated_local_db: Path,
) -> None:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)

    fixture_path = Path("tests/fixtures/imports_dummy/wizard/vendors_contracts_contacts.xml")
    payload = fixture_path.read_bytes()
    preview = _preview_upload(
        client,
        file_name=fixture_path.name,
        payload=payload,
        format_hint="auto",
    )
    job_id = _extract_job_id_from_mapping_redirect(preview)
    mapping = client.get(f"/imports/jobs/{job_id}/mapping")
    assert mapping.status_code == 200
    assert "vendorrecord.vendor.legal_name" in mapping.text
    assert "Total: 2" in mapping.text
    assert "legal_name is required for new records." not in mapping.text


def test_imports_tour_dismiss_persists_user_setting(
    _clear_import_state: None,
    isolated_local_db: Path,
) -> None:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)

    dismiss = client.post("/imports/tour/dismiss", json={"dismissed": True})
    assert dismiss.status_code == 200
    payload = dismiss.json()
    assert payload.get("ok") is True

    repo = get_repo()
    principal = repo.get_current_user()
    setting = repo.get_user_setting(principal, "imports.guided_tour.v2")
    assert bool(setting.get("dismissed")) is True
    assert str(setting.get("version") or "").strip() == "v2"
