from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.services import get_config, get_repo


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("TVENDOR_USE_MOCK", "1")
    monkeypatch.setenv("TVENDOR_TEST_USER", "admin@example.com")
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    return TestClient(app)


def test_create_project_and_add_demo(client: TestClient) -> None:
    create_response = client.post(
        "/vendors/vnd-001/projects/new",
        data={
            "return_to": "/vendors",
            "project_name": "Owner Transition Workstream",
            "project_type": "renewal",
            "status": "active",
            "start_date": "2026-02-01",
            "target_date": "2026-04-15",
            "owner_principal": "bob.smith@example.com",
            "description": "Reassign ownership from departing leader.",
            "linked_offerings": ["off-004"],
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 303
    match = re.search(r"/projects/(prj-[^/]+)/summary", create_response.headers["location"])
    assert match is not None
    project_id = match.group(1)

    list_response = client.get("/vendors/vnd-001/projects?return_to=%2Fvendors")
    assert list_response.status_code == 200
    assert "Owner Transition Workstream" in list_response.text

    demo_response = client.post(
        f"/vendors/vnd-001/projects/{project_id}/demos/new",
        data={
            "return_to": "/vendors",
            "demo_name": "Transition Demo Session",
            "demo_type": "workshop",
            "outcome": "follow_up",
            "score": "7.8",
            "linked_offering_id": "off-004",
            "notes": "Validate owner rollover process.",
        },
        follow_redirects=False,
    )
    assert demo_response.status_code == 303

    detail_response = client.get(f"/projects/{project_id}/demos?return_to=%2Fprojects")
    assert detail_response.status_code == 200
    assert "Transition Demo Session" in detail_response.text


def test_projects_home_and_new_page(client: TestClient) -> None:
    home = client.get("/projects")
    assert home.status_code == 200
    assert "Projects" in home.text
    assert "Global project workspace" in home.text

    new_page = client.get("/projects/new?return_to=%2Fprojects")
    assert new_page.status_code == 200
    assert "New Project" in new_page.text
    assert "Linked Vendors (optional)" in new_page.text


def test_create_project_without_vendor_then_attach_multiple(client: TestClient) -> None:
    create_response = client.post(
        "/projects/new",
        data={
            "return_to": "/projects",
            "project_name": "Vendorless Bootstrap Project",
            "project_type": "implementation",
            "status": "draft",
            "owner_principal": "pm@example.com",
            "description": "Create first, attach vendors later.",
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 303
    match = re.search(r"/projects/(prj-[^/]+)/summary", create_response.headers["location"])
    assert match is not None
    project_id = match.group(1)

    global_projects = client.get("/projects")
    assert global_projects.status_code == 200
    assert "Vendorless Bootstrap Project" in global_projects.text

    edit_response = client.post(
        f"/projects/{project_id}/edit",
        data={
            "return_to": "/projects",
            "project_name": "Vendorless Bootstrap Project",
            "project_type": "implementation",
            "status": "active",
            "linked_vendors": ["vnd-001", "vnd-002"],
            "linked_offerings": ["off-004", "off-003"],
            "reason": "Attach participating vendors and offerings",
        },
        follow_redirects=False,
    )
    assert edit_response.status_code == 303

    vendor_1_projects = client.get("/vendors/vnd-001/projects?return_to=%2Fvendors")
    assert vendor_1_projects.status_code == 200
    assert "Vendorless Bootstrap Project" in vendor_1_projects.text

    vendor_2_projects = client.get("/vendors/vnd-002/projects?return_to=%2Fvendors")
    assert vendor_2_projects.status_code == 200
    assert "Vendorless Bootstrap Project" in vendor_2_projects.text


def test_add_project_note_from_standalone_project_page(client: TestClient) -> None:
    create_project = client.post(
        "/vendors/vnd-001/projects/new",
        data={
            "return_to": "/projects",
            "project_name": "Notes Workflow Validation",
            "project_type": "implementation",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert create_project.status_code == 303
    match = re.search(r"/projects/(prj-[^/]+)/summary", create_project.headers["location"])
    assert match is not None
    project_id = match.group(1)

    add_note = client.post(
        f"/projects/{project_id}/notes/add",
        data={
            "return_to": f"/projects/{project_id}/notes",
            "note_text": "Owner changed from Bob Smith to Jane Doe.",
        },
        follow_redirects=False,
    )
    assert add_note.status_code == 303

    notes_page = client.get(f"/projects/{project_id}/notes?return_to=%2Fprojects")
    assert notes_page.status_code == 200
    assert "Owner changed from Bob Smith to Jane Doe." in notes_page.text
    assert "Note Text =" in notes_page.text


def test_quick_add_vendor_and_offering_from_project_tabs(client: TestClient) -> None:
    create_project = client.post(
        "/projects/new",
        data={
            "return_to": "/projects",
            "project_name": "Quick Add Mapping",
            "project_type": "implementation",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert create_project.status_code == 303
    match = re.search(r"/projects/(prj-[^/]+)/summary", create_project.headers["location"])
    assert match is not None
    project_id = match.group(1)

    add_vendor = client.post(
        f"/projects/{project_id}/vendors/add",
        data={"return_to": f"/projects/{project_id}/offerings", "vendor_id": "vnd-002", "reason": "Attach vendor"},
        follow_redirects=False,
    )
    assert add_vendor.status_code == 303

    add_offering = client.post(
        f"/projects/{project_id}/offerings/add",
        data={"return_to": f"/projects/{project_id}/offerings", "offering_id": "off-003", "reason": "Attach offering"},
        follow_redirects=False,
    )
    assert add_offering.status_code == 303

    vendor_projects = client.get("/vendors/vnd-002/projects?return_to=%2Fvendors")
    assert vendor_projects.status_code == 200
    assert "Quick Add Mapping" in vendor_projects.text

    offerings_page = client.get(f"/projects/{project_id}/offerings?return_to=%2Fprojects")
    assert offerings_page.status_code == 200
    assert "off-003" in offerings_page.text


def test_project_doc_link_without_vendor(client: TestClient) -> None:
    create_response = client.post(
        "/projects/new",
        data={
            "return_to": "/projects",
            "project_name": "Docs Before Vendors",
            "project_type": "poc",
            "status": "draft",
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 303
    match = re.search(r"/projects/(prj-[^/]+)/summary", create_response.headers["location"])
    assert match is not None
    project_id = match.group(1)

    add_doc = client.post(
        f"/projects/{project_id}/docs/link",
        data={
            "return_to": f"/projects/{project_id}/docs",
            "doc_url": "https://docs.google.com/document/d/abc123/edit",
            "doc_type": "",
            "doc_title": "",
            "tags": "notes",
            "owner": "pm@example.com",
        },
        follow_redirects=False,
    )
    assert add_doc.status_code == 303

    docs_page = client.get(f"/projects/{project_id}/docs?return_to=%2Fprojects")
    assert docs_page.status_code == 200
    assert "docs.google.com - edit" in docs_page.text


def test_project_offering_new_redirect_requires_vendor(client: TestClient) -> None:
    no_vendor = client.get("/projects/prj-001/offerings/new?return_to=%2Fprojects", follow_redirects=False)
    assert no_vendor.status_code == 303
    assert no_vendor.headers["location"].startswith("/projects/prj-001/offerings")

    with_vendor = client.get(
        "/projects/prj-001/offerings/new?vendor_id=vnd-001&return_to=%2Fprojects",
        follow_redirects=False,
    )
    assert with_vendor.status_code in (302, 303)
    assert with_vendor.headers["location"].startswith("/vendors/vnd-001/offerings/new")


def test_doc_links_infer_type_and_title_and_render(client: TestClient) -> None:
    vendor_link = "https://contoso.sharepoint.com/sites/vendors/Contract_2026.pdf"
    response = client.post(
        "/vendors/vnd-001/docs/link",
        data={
            "return_to": "/vendors",
            "doc_url": vendor_link,
            "doc_type": "",
            "doc_title": "",
            "tags": "contract",
            "owner": "procurement@example.com",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    summary = client.get("/vendors/vnd-001/summary?return_to=%2Fvendors")
    assert summary.status_code == 200
    assert "contoso.sharepoint.com - Contract_2026.pdf" in summary.text
    assert "sharepoint" in summary.text


def test_project_and_offering_doc_links_render(client: TestClient) -> None:
    create_project = client.post(
        "/vendors/vnd-001/projects/new",
        data={
            "return_to": "/vendors",
            "project_name": "Doc Hub Validation",
            "project_type": "poc",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert create_project.status_code == 303
    match = re.search(r"/projects/(prj-[^/]+)/summary", create_project.headers["location"])
    assert match is not None
    project_id = match.group(1)

    project_doc = client.post(
        f"/vendors/vnd-001/projects/{project_id}/docs/link",
        data={
            "return_to": "/vendors",
            "doc_url": "https://example.atlassian.net/wiki/spaces/SEC/pages/1234/Runbook",
            "doc_type": "",
            "doc_title": "",
            "tags": "runbook",
            "owner": "secops@example.com",
        },
        follow_redirects=False,
    )
    assert project_doc.status_code == 303

    offering_doc = client.post(
        "/vendors/vnd-001/offerings/off-004/docs/link",
        data={
            "return_to": "/vendors",
            "doc_url": "https://github.com/example/vendor-docs/blob/main/offering.md",
            "doc_type": "",
            "doc_title": "",
            "tags": "operations",
            "owner": "owner@example.com",
        },
        follow_redirects=False,
    )
    assert offering_doc.status_code == 303

    project_detail = client.get(f"/projects/{project_id}/docs?return_to=%2Fprojects")
    assert project_detail.status_code == 200
    assert "example.atlassian.net - Runbook" in project_detail.text

    offering_detail = client.get("/vendors/vnd-001/offerings/off-004?return_to=%2Fvendors")
    assert offering_detail.status_code == 200
    assert "github.com - offering.md" in offering_detail.text


def test_doc_link_owner_must_exist_in_user_directory(client: TestClient) -> None:
    response = client.post(
        "/vendors/vnd-001/docs/link",
        data={
            "return_to": "/vendors",
            "doc_url": "https://contoso.sharepoint.com/sites/vendors/Ownership_Check.pdf",
            "doc_type": "",
            "doc_title": "",
            "doc_fqdn": "",
            "tags": ["contract"],
            "owner": "not-a-user@example.com",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Owner must exist in the app user directory." in response.text


def test_doc_link_rejects_unknown_tag_not_in_admin_lookup(client: TestClient) -> None:
    response = client.post(
        "/vendors/vnd-001/docs/link",
        data={
            "return_to": "/vendors",
            "doc_url": "contoso.sharepoint.com/sites/vendors/folders/owner-handbook/",
            "doc_type": "",
            "doc_title": "",
            "tags": ["unknown_custom_tag"],
            "owner": "admin@example.com",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Tags must be selected from admin-managed options" in response.text
