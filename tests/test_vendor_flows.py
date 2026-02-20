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
from vendor_catalog_app.web.core.runtime import get_config, get_repo
from vendor_catalog_app.web.routers.demos.common import parse_template_questions_from_form


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, isolated_local_db: Path) -> TestClient:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    return TestClient(app)


def test_vendors_page_renders(client: TestClient) -> None:
    response = client.get("/vendors")
    assert response.status_code == 200
    assert "Vendor 360" in response.text


def test_vendor_list_empty_state_shows_next_actions(client: TestClient) -> None:
    response = client.get("/vendors?q=__no_match_vendor__")
    assert response.status_code == 200
    assert "No Vendors Found" in response.text
    assert "Clear Filters" in response.text
    assert "Create Vendor" in response.text


def test_vendor_new_requires_edit_permissions(client: TestClient) -> None:
    response = client.get("/vendors/new?as_user=bob.smith@example.com", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/access/request"


def test_create_vendor_and_find_in_list(client: TestClient) -> None:
    response = client.post(
        "/vendors/new",
        data={
            "return_to": "/vendors",
            "legal_name": "Acme Vendor LLC",
            "display_name": "Acme",
            "lifecycle_state": "draft",
            "owner_org_id": "IT-ENT",
            "risk_tier": "low",
            "source_system": "manual",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    match = re.search(r"/vendors/(vnd-[^/]+)/summary", location)
    assert match is not None
    vendor_id = match.group(1)

    list_response = client.get(f"/vendors?search={vendor_id}")
    assert list_response.status_code == 200
    assert vendor_id in list_response.text
    assert "Acme" in list_response.text


def test_create_vendor_validation_keeps_values_and_marks_owner_org(client: TestClient) -> None:
    response = client.post(
        "/vendors/new",
        data={
            "return_to": "/vendors",
            "legal_name": "Validation Vendor LLC",
            "display_name": "Validation Vendor",
            "lifecycle_state": "draft",
            "owner_org_choice": "__new__",
            "new_owner_org_id": "",
            "risk_tier": "low",
            "source_system": "manual",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Enter a new Line of Business." in response.text
    assert "Validation Vendor LLC" in response.text
    assert 'class="input-error"' in response.text


def test_create_offering_and_map_unassigned_records(client: TestClient) -> None:
    new_offering_response = client.post(
        "/vendors/vnd-003/offerings/new",
        data={
            "return_to": "/vendors",
            "offering_name": "Legacy Bridge",
            "offering_type": "SaaS",
            "lifecycle_state": "draft",
            "criticality_tier": "tier_2",
        },
        follow_redirects=False,
    )
    assert new_offering_response.status_code == 303
    match = re.search(r"/vendors/vnd-003/offerings/(off-[^?]+)", new_offering_response.headers["location"])
    assert match is not None
    offering_id = match.group(1)

    map_contract_response = client.post(
        "/vendors/vnd-003/map-contract",
        data={
            "return_to": "/vendors/vnd-003/offerings",
            "contract_id": "ctr-001",
            "offering_id": offering_id,
            "reason": "Map legacy contract",
        },
        follow_redirects=False,
    )
    assert map_contract_response.status_code == 303

    map_demo_response = client.post(
        "/vendors/vnd-003/map-demo",
        data={
            "return_to": "/vendors/vnd-003/offerings",
            "demo_id": "demo-002",
            "offering_id": offering_id,
            "reason": "Map legacy demo",
        },
        follow_redirects=False,
    )
    assert map_demo_response.status_code == 303

    offerings_page = client.get("/vendors/vnd-003/offerings?return_to=%2Fvendors")
    assert offerings_page.status_code == 200
    assert "Legacy Bridge" in offerings_page.text
    assert "No unassigned contracts." in offerings_page.text
    assert "No unassigned demos." in offerings_page.text

    offering_detail_page = client.get(f"/vendors/vnd-003/offerings/{offering_id}?return_to=%2Fvendors")
    assert offering_detail_page.status_code == 200
    assert "ctr-001" in offering_detail_page.text
    assert "demo-002" in offering_detail_page.text
    assert "section-nav-card sticky-section-nav" in offering_detail_page.text


def test_bulk_map_unassigned_records_to_offering(client: TestClient) -> None:
    new_offering_response = client.post(
        "/vendors/vnd-003/offerings/new",
        data={
            "return_to": "/vendors",
            "offering_name": "Bulk Mapping Offering",
            "offering_type": "SaaS",
            "lifecycle_state": "draft",
            "criticality_tier": "tier_2",
        },
        follow_redirects=False,
    )
    assert new_offering_response.status_code == 303
    match = re.search(r"/vendors/vnd-003/offerings/(off-[^?]+)", new_offering_response.headers["location"])
    assert match is not None
    offering_id = match.group(1)

    bulk_contract_response = client.post(
        "/vendors/vnd-003/map-contracts/bulk",
        data={
            "return_to": "/vendors/vnd-003/offerings",
            "offering_id": offering_id,
            "contract_ids": "ctr-001",
            "reason": "Bulk map contracts",
        },
        follow_redirects=False,
    )
    assert bulk_contract_response.status_code == 303

    bulk_demo_response = client.post(
        "/vendors/vnd-003/map-demos/bulk",
        data={
            "return_to": "/vendors/vnd-003/offerings",
            "offering_id": offering_id,
            "demo_ids": "demo-002",
            "reason": "Bulk map demos",
        },
        follow_redirects=False,
    )
    assert bulk_demo_response.status_code == 303

    offerings_page = client.get("/vendors/vnd-003/offerings?return_to=%2Fvendors")
    assert offerings_page.status_code == 200
    assert "No unassigned contracts." in offerings_page.text
    assert "No unassigned demos." in offerings_page.text
    assert "bulk-map-contracts-form" in offerings_page.text
    assert "bulk-map-demos-form" in offerings_page.text

    offering_detail_page = client.get(f"/vendors/vnd-003/offerings/{offering_id}?return_to=%2Fvendors")
    assert offering_detail_page.status_code == 200
    assert "ctr-001" in offering_detail_page.text
    assert "demo-002" in offering_detail_page.text
    assert "section-nav-card sticky-section-nav" in offering_detail_page.text


def test_offering_type_uses_dropdown_in_new_and_edit_forms(client: TestClient) -> None:
    new_form = client.get("/vendors/vnd-001/offerings/new?return_to=%2Fvendors")
    assert new_form.status_code == 200
    assert '<select name="offering_type">' in new_form.text
    assert '<select name="lob">' in new_form.text
    assert '<select name="service_type">' in new_form.text
    assert '<option value="SaaS">' in new_form.text

    edit_form = client.get("/vendors/vnd-001/offerings/off-001?return_to=%2Fvendors&edit=1")
    assert edit_form.status_code == 200
    assert '<select name="offering_type">' in edit_form.text
    assert '<select name="lob">' in edit_form.text
    assert '<select name="service_type">' in edit_form.text
    assert '<option value="SaaS" selected' in edit_form.text
    assert '<option value="Enterprise" selected' in edit_form.text
    assert '<option value="Application" selected' in edit_form.text


def test_offering_create_with_lob_and_service_type_persists_to_detail(client: TestClient) -> None:
    create = client.post(
        "/vendors/vnd-003/offerings/new",
        data={
            "return_to": "/vendors",
            "offering_name": "Legacy Bridge",
            "offering_type": "SaaS",
            "lob": "Finance",
            "service_type": "Platform",
            "lifecycle_state": "active",
            "criticality_tier": "tier_2",
        },
        follow_redirects=False,
    )
    assert create.status_code == 303
    match = re.search(r"/vendors/vnd-003/offerings/(off-[^?]+)", create.headers["location"])
    assert match is not None
    offering_id = match.group(1)

    detail = client.get(f"/vendors/vnd-003/offerings/{offering_id}?return_to=%2Fvendors")
    assert detail.status_code == 200
    assert "Finance" in detail.text
    assert "Platform" in detail.text


def test_vendor_offerings_empty_state_shows_next_actions(client: TestClient) -> None:
    offerings_page = client.get("/vendors/vnd-003/offerings?return_to=%2Fvendors")
    assert offerings_page.status_code == 200
    assert "No Offerings Found" in offerings_page.text
    assert "Create Offering" in offerings_page.text
    assert "Open Vendor Summary" in offerings_page.text


def test_create_offering_rejects_invalid_offering_type(client: TestClient) -> None:
    response = client.post(
        "/vendors/vnd-003/offerings/new",
        data={
            "return_to": "/vendors",
            "offering_name": "Legacy Bridge",
            "offering_type": "invalid_type",
            "lifecycle_state": "draft",
            "criticality_tier": "tier_2",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Offering type must be one of:" in response.text


def test_search_matches_related_contract_and_owner_data(client: TestClient) -> None:
    by_contract = client.get("/vendors?search=ctr-101")
    assert by_contract.status_code == 200
    assert "Microsoft" in by_contract.text

    by_owner = client.get("/vendors?search=cloud-platform@example.com")
    assert by_owner.status_code == 200
    assert "Microsoft" in by_owner.text


def test_vendor_merge_center_executes_merge_and_hides_merged_source_by_default(client: TestClient) -> None:
    create_survivor = client.post(
        "/vendors/new",
        data={
            "return_to": "/vendors",
            "legal_name": "Merge Survivor LLC",
            "display_name": "Merge Survivor",
            "lifecycle_state": "active",
            "owner_org_id": "IT-ENT",
            "risk_tier": "low",
            "source_system": "manual",
        },
        follow_redirects=False,
    )
    assert create_survivor.status_code == 303
    survivor_match = re.search(r"/vendors/(vnd-[^/]+)/summary", create_survivor.headers["location"])
    assert survivor_match is not None
    survivor_vendor_id = survivor_match.group(1)

    create_source = client.post(
        "/vendors/new",
        data={
            "return_to": "/vendors",
            "legal_name": "Merge Source LLC",
            "display_name": "Merge Source",
            "lifecycle_state": "active",
            "owner_org_id": "IT-ENT",
            "risk_tier": "medium",
            "source_system": "manual",
        },
        follow_redirects=False,
    )
    assert create_source.status_code == 303
    source_match = re.search(r"/vendors/(vnd-[^/]+)/summary", create_source.headers["location"])
    assert source_match is not None
    source_vendor_id = source_match.group(1)

    source_offering = client.post(
        f"/vendors/{source_vendor_id}/offerings/new",
        data={
            "return_to": "/vendors",
            "offering_name": "Merge Source Offering",
            "offering_type": "SaaS",
            "lifecycle_state": "draft",
            "criticality_tier": "tier_2",
        },
        follow_redirects=False,
    )
    assert source_offering.status_code == 303

    preview = client.get(
        f"/vendors/merge-center?survivor_vendor_id={survivor_vendor_id}&source_vendor_id={source_vendor_id}"
    )
    assert preview.status_code == 200
    assert "Merge Preview" in preview.text

    execute = client.post(
        "/vendors/merge-center/execute",
        data={
            "survivor_vendor_id": survivor_vendor_id,
            "source_vendor_id": source_vendor_id,
            "merge_reason": "test merge center",
        },
        follow_redirects=False,
    )
    assert execute.status_code == 303
    assert execute.headers["location"].startswith(f"/vendors/{survivor_vendor_id}/summary")

    repo = get_repo()
    source_after = repo.get_vendor_profile(source_vendor_id)
    assert not source_after.empty
    source_row = source_after.iloc[0].to_dict()
    assert str(source_row.get("merged_into_vendor_id") or "").strip() == survivor_vendor_id
    assert str(source_row.get("lifecycle_state") or "").strip().lower() == "inactive"

    default_rows, _default_total = repo.list_vendors_page(search_text=source_vendor_id, include_merged=False)
    assert source_vendor_id not in set(default_rows.get("vendor_id", []).astype(str).tolist())

    merged_rows, _merged_total = repo.list_vendors_page(search_text=source_vendor_id, include_merged=True)
    assert source_vendor_id in set(merged_rows.get("vendor_id", []).astype(str).tolist())


def test_vendor_detail_redirects_to_canonical_vendor_after_merge(client: TestClient) -> None:
    create_survivor = client.post(
        "/vendors/new",
        data={
            "return_to": "/vendors",
            "legal_name": "Canonical Survivor LLC",
            "display_name": "Canonical Survivor",
            "lifecycle_state": "active",
            "owner_org_id": "IT-ENT",
            "risk_tier": "low",
            "source_system": "manual",
        },
        follow_redirects=False,
    )
    assert create_survivor.status_code == 303
    survivor_match = re.search(r"/vendors/(vnd-[^/]+)/summary", create_survivor.headers["location"])
    assert survivor_match is not None
    survivor_vendor_id = survivor_match.group(1)

    create_source = client.post(
        "/vendors/new",
        data={
            "return_to": "/vendors",
            "legal_name": "Canonical Source LLC",
            "display_name": "Canonical Source",
            "lifecycle_state": "active",
            "owner_org_id": "IT-ENT",
            "risk_tier": "medium",
            "source_system": "manual",
        },
        follow_redirects=False,
    )
    assert create_source.status_code == 303
    source_match = re.search(r"/vendors/(vnd-[^/]+)/summary", create_source.headers["location"])
    assert source_match is not None
    source_vendor_id = source_match.group(1)

    merge_execute = client.post(
        "/vendors/merge-center/execute",
        data={
            "survivor_vendor_id": survivor_vendor_id,
            "source_vendor_id": source_vendor_id,
            "merge_reason": "canonical redirect test",
        },
        follow_redirects=False,
    )
    assert merge_execute.status_code == 303

    source_summary = client.get(f"/vendors/{source_vendor_id}/summary", follow_redirects=False)
    assert source_summary.status_code == 303
    assert source_summary.headers["location"].startswith(f"/vendors/{survivor_vendor_id}/summary")

def test_vendor_list_server_side_pagination_and_sort(client: TestClient) -> None:
    page_one = client.get("/vendors?page=1&page_size=1&sort_by=vendor_name&sort_dir=asc")
    assert page_one.status_code == 200
    assert "Page 1 of 3" in page_one.text
    assert "vnd-003" in page_one.text

    page_two = client.get("/vendors?page=2&page_size=1&sort_by=vendor_name&sort_dir=asc")
    assert page_two.status_code == 200
    assert "Page 2 of 3" in page_two.text
    assert "vnd-001" in page_two.text

    page_desc = client.get("/vendors?page=1&page_size=1&sort_by=vendor_name&sort_dir=desc")
    assert page_desc.status_code == 200
    assert "vnd-002" in page_desc.text


def test_vendor_list_uses_q_and_persists_list_preferences(client: TestClient) -> None:
    by_q = client.get("/vendors?q=ctr-101")
    assert by_q.status_code == 200
    assert "Microsoft" in by_q.text

    saved_pref = client.get("/vendors?page_size=10&sort_by=updated_at&sort_dir=desc")
    assert saved_pref.status_code == 200

    restored = client.get("/vendors")
    assert restored.status_code == 200
    assert 'name="sort_by" value="updated_at"' in restored.text
    assert 'name="sort_dir" value="desc"' in restored.text
    assert '<option value="10" selected' in restored.text


def test_typeahead_vendor_offering_and_project_api(client: TestClient) -> None:
    vendor_response = client.get("/api/vendors/search?q=micro&limit=5")
    assert vendor_response.status_code == 200
    vendor_payload = vendor_response.json()
    vendor_ids = {row.get("vendor_id") for row in vendor_payload.get("items", [])}
    assert "vnd-001" in vendor_ids

    offering_response = client.get("/api/offerings/search?vendor_id=vnd-001&q=azure&limit=10")
    assert offering_response.status_code == 200
    offering_payload = offering_response.json()
    offering_items = offering_payload.get("items", [])
    assert any(str(row.get("offering_id")) == "off-002" for row in offering_items)
    assert all(str(row.get("vendor_id")) == "vnd-001" for row in offering_items)

    project_response = client.get("/api/projects/search?q=Defender&limit=10")
    assert project_response.status_code == 200
    project_payload = project_response.json()
    assert any("Defender" in str(row.get("label", "")) for row in project_payload.get("items", []))

    user_response = client.get("/api/users/search?q=admin&limit=10")
    assert user_response.status_code == 200
    user_payload = user_response.json()
    user_items = user_payload.get("items", [])
    admin_row = next((row for row in user_items if str(row.get("login_identifier")) == "admin@example.com"), None)
    assert admin_row is not None
    assert str(admin_row.get("display_name") or "").strip() != ""
    assert str(admin_row.get("email") or "").strip() != ""

    contract_response = client.get("/api/contracts/search?q=MS-2024&limit=10")
    assert contract_response.status_code == 200
    contract_payload = contract_response.json()
    contract_items = contract_payload.get("items", [])
    assert any(str(row.get("contract_id")) == "ctr-101" for row in contract_items)
    assert any("MS-2024-001" in str(row.get("label", "")) for row in contract_items)

    contact_seed = client.post(
        "/vendors/vnd-002/contacts/add",
        data={
            "return_to": "/vendors/vnd-002/ownership",
            "full_name": "Taylor Ops",
            "contact_type": "support",
            "email": "taylor.ops@example.com",
            "phone": "555-0999",
            "reason": "Seed contact for typeahead.",
        },
        follow_redirects=False,
    )
    assert contact_seed.status_code == 303

    contact_response = client.get("/api/contacts/search?q=taylor&limit=10")
    assert contact_response.status_code == 200
    contact_payload = contact_response.json()
    contact_items = contact_payload.get("items", [])
    assert any(str(row.get("full_name") or "").strip() == "Taylor Ops" for row in contact_items)


def test_contract_and_demo_forms_use_expected_inputs(client: TestClient) -> None:
    contracts_page = client.get("/contracts")
    assert contracts_page.status_code == 200
    assert "Manage Contracts In Vendor 360" in contracts_page.text
    assert 'action="/contracts/cancel"' not in contracts_page.text

    demos_page = client.get("/demos")
    assert demos_page.status_code == 200
    assert "data-demo-vendor-search" in demos_page.text
    assert "data-demo-offering-search" in demos_page.text
    assert "/api/vendors/search" in demos_page.text
    assert "/api/offerings/search" in demos_page.text


def test_demo_review_form_template_and_submission_flow(client: TestClient) -> None:
    review_page = client.get("/demos/demo-005/review-form")
    assert review_page.status_code == 200
    assert "Template Designer" in review_page.text

    template_save = client.post(
        "/demos/demo-005/review-form/template",
        data={
            "template_title": "Enterprise Demo Scorecard",
            "instructions": "Use weighted scoring for enterprise review.",
            "attach_now": "1",
            "question_label[]": ["Business Fit", "Security Model", "Deployment Readiness"],
            "question_type[]": ["scale", "boolean", "multi_choice"],
            "question_weight[]": ["2.0", "1.0", "1.5"],
            "scale_min[]": ["1", "1", "1"],
            "scale_max[]": ["5", "5", "5"],
            "scale_step[]": ["1", "1", "1"],
            "option_labels[]": ["", "Yes, No", "Cloud Native, Hybrid, On Prem"],
            "option_weights[]": ["", "1, 0", "1, 0.6, 0.2"],
            "question_help_text[]": ["Score strategic fit", "Security gate", "Preferred deployment model"],
        },
        follow_redirects=False,
    )
    assert template_save.status_code == 303

    review_submit = client.post(
        "/demos/demo-005/review-form/submit",
        data={
            "answer_business_fit": "4",
            "answer_security_model": "yes",
            "answer_deployment_readiness": "cloud_native",
            "review_comment": "Strong overall fit with minor support concerns.",
        },
        follow_redirects=False,
    )
    assert review_submit.status_code == 303

    review_update = client.post(
        "/demos/demo-005/review-form/submit",
        data={
            "answer_business_fit": "5",
            "answer_security_model": "yes",
            "answer_deployment_readiness": "hybrid",
            "review_comment": "Updated after architecture review.",
        },
        follow_redirects=False,
    )
    assert review_update.status_code == 303

    refreshed = client.get("/demos/demo-005/review-form")
    assert refreshed.status_code == 200
    assert "Enterprise Demo Scorecard" in refreshed.text
    assert "Business Fit" in refreshed.text
    assert "Security Model" in refreshed.text
    assert "Deployment Readiness" in refreshed.text
    assert "Updated after architecture review." in refreshed.text
    assert "Submissions" in refreshed.text


def test_demo_workspace_supports_stage_tracking_and_scorecard_views(client: TestClient) -> None:
    workspace = client.get("/demos/demo-005")
    assert workspace.status_code == 200
    assert "Demo Workspace" in workspace.text
    assert "Lifecycle Stages" in workspace.text
    assert "Scoring Cards" in workspace.text

    stage_update = client.post(
        "/demos/demo-005/stage",
        data={
            "stage": "scoring",
            "notes": "Technical and security scoring session started.",
        },
        follow_redirects=False,
    )
    assert stage_update.status_code == 303

    refreshed = client.get("/demos/demo-005")
    assert refreshed.status_code == 200
    assert "Technical and security scoring session started." in refreshed.text


def test_demo_forms_library_supports_version_copy_delete_and_preview(client: TestClient) -> None:
    forms_page = client.get("/demos/forms")
    assert forms_page.status_code == 200
    assert "Demo Forms Library" in forms_page.text
    assert "data-open-demo-designer" in forms_page.text
    assert "demo-form-designer-template" in forms_page.text
    assert "Export JSON" in forms_page.text
    assert "Import JSON" in forms_page.text
    assert "Clear Draft" in forms_page.text
    assert "prop-option-table-body" in forms_page.text

    auto_open_page = client.get("/demos/forms?designer=1")
    assert auto_open_page.status_code == 200
    assert "shouldAutoOpenDesigner = true" in auto_open_page.text

    create_response = client.post(
        "/demos/forms/save",
        data={
            "template_title": "Lifecycle Evaluation Form",
            "instructions": "Evaluate capability and readiness.",
            "question_label[]": ["Business Fit", "Security Gate"],
            "question_type[]": ["scale", "boolean"],
            "question_weight[]": ["1.5", "1"],
            "question_required[]": ["true", "true"],
            "question_layout[]": ["vertical", "horizontal"],
            "question_placeholder[]": ["", ""],
            "allow_multiple[]": ["false", "false"],
            "scale_min[]": ["1", "1"],
            "scale_max[]": ["5", "5"],
            "scale_step[]": ["1", "1"],
            "option_labels[]": ["", "Yes, No"],
            "option_weights[]": ["", "1, 0"],
            "question_help_text[]": ["Score strategic fit", "Pass or fail gate"],
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 303
    create_location = create_response.headers.get("location", "")
    match = re.search(r"template_key=(frm-[a-z0-9-]+)", create_location)
    assert match is not None
    template_key = match.group(1)

    edit_response = client.post(
        "/demos/forms/save",
        data={
            "template_key": template_key,
            "template_title": "Lifecycle Evaluation Form",
            "instructions": "Evaluate capability, security, and adoption readiness.",
            "question_label[]": ["Business Fit", "Security Gate"],
            "question_type[]": ["scale", "boolean"],
            "question_weight[]": ["2", "1"],
            "question_required[]": ["true", "true"],
            "question_layout[]": ["vertical", "horizontal"],
            "question_placeholder[]": ["", ""],
            "allow_multiple[]": ["false", "false"],
            "scale_min[]": ["1", "1"],
            "scale_max[]": ["5", "5"],
            "scale_step[]": ["1", "1"],
            "option_labels[]": ["", "Yes, No"],
            "option_weights[]": ["", "1, 0"],
            "question_help_text[]": ["Score strategic fit", "Pass or fail gate"],
        },
        follow_redirects=False,
    )
    assert edit_response.status_code == 303

    preview_response = client.get(f"/demos/forms/{template_key}/preview")
    assert preview_response.status_code == 200
    assert "Form Preview" in preview_response.text
    assert "Lifecycle Evaluation Form" in preview_response.text

    copy_response = client.post(
        f"/demos/forms/{template_key}/copy",
        follow_redirects=False,
    )
    assert copy_response.status_code == 303
    copy_location = copy_response.headers.get("location", "")
    copy_match = re.search(r"template_key=(frm-[a-z0-9-]+)", copy_location)
    assert copy_match is not None
    copied_key = copy_match.group(1)
    assert copied_key != template_key

    delete_response = client.post(
        f"/demos/forms/{template_key}/delete",
        follow_redirects=False,
    )
    assert delete_response.status_code == 303

    active_listing = client.get("/demos/forms")
    assert active_listing.status_code == 200
    assert template_key not in active_listing.text

    inactive_listing = client.get(f"/demos/forms?include_inactive=1&q={template_key}")
    assert inactive_listing.status_code == 200
    assert template_key in inactive_listing.text
    assert "deleted" in inactive_listing.text.lower()
    assert "Star Rating (1-5)" in forms_page.text
    assert "Likert Scale" in forms_page.text
    assert "Dropdown Select" in forms_page.text
    assert "Short Text" in forms_page.text
    assert "Long Comment" in forms_page.text
    assert "Section Header" in forms_page.text


def test_vendor_contracts_page_supports_add_and_cancel(client: TestClient) -> None:
    add_response = client.post(
        "/vendors/vnd-001/contracts/add",
        data={
            "return_to": "/vendors/vnd-001/contracts?return_to=%2Fvendors",
            "contract_number": "MS-2026-NEW",
            "offering_id": "off-002",
            "contract_status": "active",
            "start_date": "2026-03-01",
            "end_date": "2027-02-28",
            "annual_value": "125000.50",
            "reason": "Add new offering license contract",
        },
        follow_redirects=False,
    )
    assert add_response.status_code == 303

    contracts_page = client.get("/vendors/vnd-001/contracts?return_to=%2Fvendors")
    assert contracts_page.status_code == 200
    assert "MS-2026-NEW" in contracts_page.text
    assert "Cancel Contract" in contracts_page.text
    assert 'name="reason_code"' in contracts_page.text
    assert "Select cancellation reason" in contracts_page.text

    contract_search = client.get("/api/contracts/search?q=MS-2026-NEW&limit=5")
    assert contract_search.status_code == 200
    payload = contract_search.json()
    contract_id = ""
    for row in payload.get("items", []):
        if str(row.get("contract_number") or "") == "MS-2026-NEW":
            contract_id = str(row.get("contract_id") or "").strip()
            break
    assert contract_id

    update_response = client.post(
        f"/vendors/vnd-001/contracts/{contract_id}/update",
        data={
            "return_to": "/vendors/vnd-001/contracts?return_to=%2Fvendors",
            "contract_number": "MS-2026-UPDATED",
            "offering_id": "off-002",
            "contract_status": "active",
            "start_date": "2026-03-01",
            "end_date": "2027-02-28",
            "annual_value": "130000.00",
            "reason": "Correct contract metadata",
        },
        follow_redirects=False,
    )
    assert update_response.status_code == 303

    contracts_after_update = client.get("/vendors/vnd-001/contracts?return_to=%2Fvendors")
    assert contracts_after_update.status_code == 200
    assert "MS-2026-UPDATED" in contracts_after_update.text

    cancel_response = client.post(
        f"/vendors/vnd-001/contracts/{contract_id}/cancel",
        data={
            "return_to": "/vendors/vnd-001/contracts?return_to=%2Fvendors",
            "reason_code": "business_change",
            "notes": "Contract retired after scope consolidation",
        },
        follow_redirects=False,
    )
    assert cancel_response.status_code == 303

    contracts_after_cancel = client.get("/vendors/vnd-001/contracts?return_to=%2Fvendors")
    assert contracts_after_cancel.status_code == 200
    assert "MS-2026-UPDATED" in contracts_after_cancel.text
    assert "cancelled" in contracts_after_cancel.text.lower()


def test_offering_delivery_supports_add_contract(client: TestClient) -> None:
    add_response = client.post(
        "/vendors/vnd-001/contracts/add",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-002?section=delivery&return_to=%2Fvendors",
            "contract_number": "MS-2026-OFFERING",
            "offering_id": "off-002",
            "contract_status": "active",
            "start_date": "2026-04-01",
            "end_date": "2027-03-31",
            "annual_value": "88000",
            "reason": "Add app-specific license contract",
        },
        follow_redirects=False,
    )
    assert add_response.status_code == 303

    delivery_page = client.get("/vendors/vnd-001/offerings/off-002?section=delivery&return_to=%2Fvendors")
    assert delivery_page.status_code == 200
    assert "MS-2026-OFFERING" in delivery_page.text


def test_vendor_change_trail_shows_field_level_diff(client: TestClient) -> None:
    update_response = client.post(
        "/vendors/vnd-001/direct-update",
        data={
            "return_to": "/vendors/vnd-001/changes",
            "legal_name": "Microsoft Corporation",
            "display_name": "Microsoft",
            "lifecycle_state": "active",
            "owner_org_id": "IT-ENT",
            "risk_tier": "high",
            "reason": "Escalate risk after review",
        },
        follow_redirects=False,
    )
    assert update_response.status_code == 303

    changes_page = client.get("/vendors/vnd-001/changes?return_to=%2Fvendors")
    assert changes_page.status_code == 200
    assert ("Risk Tier: medium -&gt; high" in changes_page.text) or ("Risk Tier: medium -> high" in changes_page.text)


def test_vendor_summary_includes_active_lob_and_service_type_values(client: TestClient) -> None:
    response = client.get("/vendors/vnd-001/summary?return_to=%2Fvendors")
    assert response.status_code == 200
    assert "active_lobs" in response.text
    assert "active_service_types" in response.text
    assert "Enterprise, IT" in response.text
    assert "Application, Infrastructure" in response.text


def test_vendor_summary_falls_back_to_draft_offering_lob_and_service_type_values(client: TestClient) -> None:
    vendor_response = client.post(
        "/vendors/new",
        data={
            "return_to": "/vendors",
            "legal_name": "Fallback Metrics Vendor LLC",
            "display_name": "Fallback Metrics Vendor",
            "lifecycle_state": "draft",
            "owner_org_id": "IT-ENT",
            "risk_tier": "low",
            "source_system": "manual",
        },
        follow_redirects=False,
    )
    assert vendor_response.status_code == 303
    vendor_match = re.search(r"/vendors/(vnd-[^/]+)/summary", vendor_response.headers["location"])
    assert vendor_match is not None
    vendor_id = vendor_match.group(1)

    offering_response = client.post(
        f"/vendors/{vendor_id}/offerings/new",
        data={
            "return_to": "/vendors",
            "offering_name": "Draft Metrics Offering",
            "offering_type": "SaaS",
            "lob": "Finance",
            "service_type": "Platform",
            "lifecycle_state": "draft",
            "criticality_tier": "tier_2",
        },
        follow_redirects=False,
    )
    assert offering_response.status_code == 303

    summary = client.get(f"/vendors/{vendor_id}/summary?return_to=%2Fvendors")
    assert summary.status_code == 200
    assert "Finance" in summary.text
    assert "Platform" in summary.text


def test_vendor_ownership_allows_adding_owner_lob_and_contact(client: TestClient) -> None:
    owner_response = client.post(
        "/vendors/vnd-002/owners/add",
        data={
            "return_to": "/vendors/vnd-002/ownership",
            "owner_user_principal": "owner@example.com",
            "owner_role": "business_owner",
            "reason": "Add current service owner.",
        },
        follow_redirects=False,
    )
    assert owner_response.status_code == 303

    lob_response = client.post(
        "/vendors/vnd-002/ownership/lob/update",
        data={
            "return_to": "/vendors/vnd-002/ownership",
            "lob": "Finance",
            "reason": "Set single LOB org value.",
        },
        follow_redirects=False,
    )
    assert lob_response.status_code == 303

    contact_response = client.post(
        "/vendors/vnd-002/contacts/add",
        data={
            "return_to": "/vendors/vnd-002/ownership",
            "full_name": "Taylor Ops",
            "contact_type": "support",
            "email": "taylor.ops@example.com",
            "phone": "555-0999",
            "reason": "Primary support contact.",
        },
        follow_redirects=False,
    )
    assert contact_response.status_code == 303

    ownership_page = client.get("/vendors/vnd-002/ownership?return_to=%2Fvendors")
    assert ownership_page.status_code == 200
    assert "owner@example.com" in ownership_page.text
    assert "Line of Business" in ownership_page.text
    assert "Finance" in ownership_page.text
    assert "Taylor Ops" in ownership_page.text
    assert "vendor-owner-search-filter" in ownership_page.text
    assert "vendor-contact-search-filter" in ownership_page.text
    assert "vendor-owner-add-template" in ownership_page.text
    assert "vendor-contact-add-template" in ownership_page.text
    assert "vendor-lob-update-template" in ownership_page.text
    assert 'type="checkbox"' in ownership_page.text
    assert 'name="primary_lob"' in ownership_page.text
    assert 'name="lobs"' in ownership_page.text
    assert 'name="reason_code"' in ownership_page.text


def test_vendor_ownership_lob_update_supports_explicit_primary_lob(client: TestClient) -> None:
    response = client.post(
        "/vendors/vnd-002/ownership/lob/update",
        data={
            "return_to": "/vendors/vnd-002/ownership",
            "lobs": ["Finance", "Security"],
            "primary_lob": "Security",
            "reason_code": "ownership_alignment",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    profile = get_repo().get_vendor_profile("vnd-002")
    assert not profile.empty
    assert str(profile.iloc[0].get("owner_org_id") or "").strip() == "Security"

    assignments = get_repo().get_vendor_org_assignments("vnd-002")
    active_assignments = assignments[
        ~assignments["active_flag"].astype(str).str.strip().str.lower().isin({"0", "false", "no", "n"})
    ]
    active_lobs = {str(item).strip() for item in active_assignments["org_id"].tolist() if str(item).strip()}
    assert {"Finance", "Security"}.issubset(active_lobs)


def test_vendor_ownership_lobs_render_primary_then_alphabetical(client: TestClient) -> None:
    response = client.post(
        "/vendors/vnd-002/ownership/lob/update",
        data={
            "return_to": "/vendors/vnd-002/ownership",
            "lobs": ["Security", "Finance", "Enterprise"],
            "primary_lob": "Security",
            "reason_code": "ownership_alignment",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    ownership_page = client.get("/vendors/vnd-002/ownership?return_to=%2Fvendors")
    assert ownership_page.status_code == 200

    lob_section_match = re.search(
        r"Lines of Business</th>.*?<ul[^>]*>(.*?)</ul>",
        ownership_page.text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert lob_section_match is not None

    rendered_items = re.findall(r"<li>\s*(.*?)\s*</li>", lob_section_match.group(1), flags=re.IGNORECASE | re.DOTALL)
    normalized_items = [re.sub(r"\s+", " ", item).strip() for item in rendered_items]
    assert normalized_items
    assert normalized_items[0] == "Security (Primary)"

    trailing_items = normalized_items[1:]
    trailing_lobs = [item.replace(" (Primary)", "") for item in trailing_items]
    assert trailing_lobs == sorted(trailing_lobs, key=str.lower)
    assert "Enterprise" in trailing_lobs
    assert "Finance" in trailing_lobs


def test_vendor_ownership_drawer_prepopulates_active_lobs_and_bulk_controls(client: TestClient) -> None:
    response = client.post(
        "/vendors/vnd-002/ownership/lob/update",
        data={
            "return_to": "/vendors/vnd-002/ownership",
            "lobs": ["Security", "Finance", "Enterprise"],
            "primary_lob": "Security",
            "reason_code": "ownership_alignment",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    ownership_page = client.get("/vendors/vnd-002/ownership?return_to=%2Fvendors")
    assert ownership_page.status_code == 200
    assert "data-vendor-select-all-lobs" in ownership_page.text
    assert "data-vendor-clear-all-lobs" in ownership_page.text

    assignments = get_repo().get_vendor_org_assignments("vnd-002")
    active_assignments = assignments[
        ~assignments["active_flag"].astype(str).str.strip().str.lower().isin({"0", "false", "no", "n"})
    ]
    active_lobs = sorted({str(item).strip() for item in active_assignments["org_id"].tolist() if str(item).strip()})
    assert active_lobs

    rendered_lob_values = set(
        re.findall(r'name="lobs"[^>]*value="([^"]+)"', ownership_page.text, flags=re.IGNORECASE)
    )
    assert rendered_lob_values

    for lob_value in active_lobs:
        if lob_value not in rendered_lob_values:
            continue
        checked_pattern = re.compile(
            rf'name="lobs"[^>]*value="{re.escape(lob_value)}"[^>]*checked|value="{re.escape(lob_value)}"[^>]*name="lobs"[^>]*checked',
            flags=re.IGNORECASE,
        )
        assert checked_pattern.search(ownership_page.text) is not None

    unmanaged_lobs = [lob_value for lob_value in active_lobs if lob_value not in rendered_lob_values]
    for lob_value in unmanaged_lobs:
        assert f"{lob_value} (Current, unmanaged)" in ownership_page.text


def test_vendor_ownership_lob_update_allows_no_primary_lob(client: TestClient) -> None:
    response = client.post(
        "/vendors/vnd-002/ownership/lob/update",
        data={
            "return_to": "/vendors/vnd-002/ownership",
            "lobs": ["Finance", "Security"],
            "primary_lob": "",
            "reason_code": "ownership_alignment",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    profile = get_repo().get_vendor_profile("vnd-002")
    assert not profile.empty
    owner_org_value = str(profile.iloc[0].get("owner_org_id") or "").strip()
    assert owner_org_value == ""

    assignments = get_repo().get_vendor_org_assignments("vnd-002")
    active_assignments = assignments[
        ~assignments["active_flag"].astype(str).str.strip().str.lower().isin({"0", "false", "no", "n"})
    ]
    active_lobs = {str(item).strip() for item in active_assignments["org_id"].tolist() if str(item).strip()}
    assert {"Finance", "Security"}.issubset(active_lobs)


def test_vendor_contact_add_supports_name_fallback_from_email(client: TestClient) -> None:
    response = client.post(
        "/vendors/vnd-002/contacts/add",
        data={
            "return_to": "/vendors/vnd-002/ownership",
            "full_name": "",
            "contact_type": "support",
            "email": "fallback.contact@example.com",
            "phone": "555-0108",
            "reason": "Fallback name from email.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    ownership_page = client.get("/vendors/vnd-002/ownership?return_to=%2Fvendors")
    assert ownership_page.status_code == 200
    assert "fallback.contact@example.com" in ownership_page.text


def test_offering_ownership_allows_adding_owner_and_contact(client: TestClient) -> None:
    owner_response = client.post(
        "/vendors/vnd-001/offerings/off-004/owners/add",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors",
            "owner_user_principal": "pm@example.com",
            "owner_role": "business_owner",
            "reason": "Assign offering owner.",
        },
        follow_redirects=False,
    )
    assert owner_response.status_code == 303

    contact_response = client.post(
        "/vendors/vnd-001/offerings/off-004/contacts/add",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors",
            "full_name": "Offering Contact",
            "contact_type": "support",
            "email": "secops@example.com",
            "phone": "555-0119",
            "reason": "Assign offering support contact.",
        },
        follow_redirects=False,
    )
    assert contact_response.status_code == 303

    ownership_page = client.get("/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors")
    assert ownership_page.status_code == 200
    assert "pm@example.com" in ownership_page.text

    owner_rows = get_repo().get_vendor_offering_business_owners("vnd-001")
    owner_rows = owner_rows[
        (owner_rows["offering_id"].astype(str) == "off-004")
        & (owner_rows["owner_user_principal"].astype(str) == "pm@example.com")
    ]
    assert not owner_rows.empty
    owner_id = str(owner_rows.iloc[0]["offering_owner_id"])

    owner_update = client.post(
        f"/vendors/vnd-001/offerings/off-004/owners/{owner_id}/update",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors",
            "owner_user_principal": "pm@example.com",
            "owner_role": "security_owner",
            "reason": "Role update.",
        },
        follow_redirects=False,
    )
    assert owner_update.status_code == 303

    ownership_page = client.get("/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors")
    assert ownership_page.status_code == 200
    assert "pm@example.com" in ownership_page.text
    assert "Offering Contact" in ownership_page.text
    assert "secops@example.com" in ownership_page.text
    assert "security_owner" in ownership_page.text
    assert "owner-search-filter" in ownership_page.text
    assert "contact-search-filter" in ownership_page.text
    assert "Add Owner" in ownership_page.text
    assert "Add Contact" in ownership_page.text
    assert "offering-contact-add-template" in ownership_page.text
    assert "Contact Name <span class=\"field-error\">*</span>" not in ownership_page.text
    assert 'name="reason_code"' in ownership_page.text
    assert "Confirm Remove" in ownership_page.text


def test_offering_ownership_rejects_unknown_owner_before_save(client: TestClient) -> None:
    response = client.post(
        "/vendors/vnd-001/offerings/off-004/owners/add",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors",
            "owner_user_principal": "",
            "owner_user_principal_display_name": "Not A Real Directory User",
            "owner_role": "business_owner",
            "reason": "Validation test.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Owner must exist in the app user directory." in response.text


def test_offering_contact_add_allows_non_directory_contact_lookup_values(client: TestClient) -> None:
    response = client.post(
        "/vendors/vnd-001/offerings/off-004/contacts/add",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors",
            "full_name": "Bob Smith",
            "contact_type": "support",
            "email": "bob.smith@xyzcorp.com",
            "phone": "555-0123",
            "reason": "Add external contact.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get("/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors")
    assert page.status_code == 200
    assert "Bob Smith" in page.text
    assert "bob.smith@xyzcorp.com" in page.text


def test_offering_ownership_shows_employee_directory_warning_banner(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_owner = client.post(
        "/vendors/vnd-001/offerings/off-004/owners/add",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors",
            "owner_user_principal": "pm@example.com",
            "owner_role": "business_owner",
            "reason": "Assign owner.",
        },
        follow_redirects=False,
    )
    assert add_owner.status_code == 303

    repo = get_repo()

    def _fake_status_map(principals):
        return {
            str(item).strip().lower(): {
                "principal": str(item).strip(),
                "status": "missing",
                "active": False,
                "login_identifier": None,
                "display_name": None,
            }
            for item in principals
        }

    monkeypatch.setattr(repo, "get_employee_directory_status_map", _fake_status_map)
    response = client.get("/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors")
    assert response.status_code == 200
    assert "reference users not active in employee directory" in response.text
    assert "owner-status-badge missing" in response.text


def test_offering_ownership_org_updates_single_lob_value(client: TestClient) -> None:
    response = client.post(
        "/vendors/vnd-001/offerings/off-004/ownership/lob/update",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors",
            "lobs": ["Finance"],
            "reason_code": "ownership_alignment",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get("/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors")
    assert page.status_code == 200
    assert "Line of Business" in page.text
    assert "Finance" in page.text
    assert 'name="lobs"' in page.text
    assert 'name="primary_lob"' in page.text
    assert 'type="checkbox"' in page.text
    assert 'name="reason_code"' in page.text
    assert "data-offering-select-all-lobs" in page.text
    assert "data-offering-clear-all-lobs" in page.text


def test_offering_ownership_drawer_shows_unmanaged_current_lob(client: TestClient) -> None:
    update_result = get_repo().update_offering_fields(
        vendor_id="vnd-001",
        offering_id="off-004",
        actor_user_principal="pm@example.com",
        updates={"lob": "SEC-OPS"},
        reason="Seed unmanaged legacy value for drawer rendering.",
    )
    assert update_result.get("request_id")

    page = client.get("/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors")
    assert page.status_code == 200
    assert "SEC-OPS (Current, unmanaged)" in page.text


def test_offering_ownership_lob_update_supports_explicit_primary_lob(client: TestClient) -> None:
    response = client.post(
        "/vendors/vnd-001/offerings/off-004/ownership/lob/update",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors",
            "lobs": ["Finance", "Security"],
            "primary_lob": "Security",
            "reason_code": "ownership_alignment",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    offering = get_repo().get_offering_record("vnd-001", "off-004")
    assert offering is not None
    assert str(offering.get("lob") or "").strip() == "Security"


def test_offering_ownership_lob_update_allows_no_primary_lob(client: TestClient) -> None:
    response = client.post(
        "/vendors/vnd-001/offerings/off-004/ownership/lob/update",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors",
            "lobs": ["Finance", "Security"],
            "primary_lob": "",
            "reason_code": "ownership_alignment",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    offering = get_repo().get_offering_record("vnd-001", "off-004")
    assert offering is not None
    assert str(offering.get("lob") or "").strip() == ""


def test_offering_owner_bulk_reassign_updates_multiple_assignments(client: TestClient) -> None:
    add_owner_one = client.post(
        "/vendors/vnd-001/offerings/off-001/owners/add",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-001?section=ownership&return_to=%2Fvendors",
            "owner_user_principal": "pm@example.com",
            "owner_role": "business_owner",
            "reason": "Assign owner one.",
        },
        follow_redirects=False,
    )
    assert add_owner_one.status_code == 303

    add_owner_two = client.post(
        "/vendors/vnd-001/offerings/off-004/owners/add",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors",
            "owner_user_principal": "pm@example.com",
            "owner_role": "technical_owner",
            "reason": "Assign owner two.",
        },
        follow_redirects=False,
    )
    assert add_owner_two.status_code == 303

    reassign = client.post(
        "/vendors/vnd-001/offerings/owners/reassign",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors",
            "from_owner_user_principal": "pm@example.com",
            "to_owner_user_principal": "admin@example.com",
            "reason_code": "employee_inactive",
        },
        follow_redirects=False,
    )
    assert reassign.status_code == 303

    owners = get_repo().get_vendor_offering_business_owners("vnd-001")
    active_owners = owners[~owners["active_flag"].astype(str).str.strip().str.lower().isin({"0", "false", "no", "n"})]
    pm_active = active_owners[active_owners["owner_user_principal"].astype(str).str.lower() == "pm@example.com"]
    assert pm_active.empty
    admin_active = active_owners[active_owners["owner_user_principal"].astype(str).str.lower() == "admin@example.com"]
    assert len(admin_active) >= 2


def test_offering_owner_bulk_reassign_supports_legacy_source_not_in_directory(client: TestClient) -> None:
    repo = get_repo()
    legacy_owner = "stubborn.legacy.owner@example.com"
    owner_id = repo._new_id("oown")
    now = repo._now()
    actor_ref = repo._actor_ref("admin@example.com")
    repo._execute_file(
        "inserts/add_offering_owner.sql",
        params=(
            owner_id,
            "off-004",
            legacy_owner,
            "technical_owner",
            True,
            now,
            actor_ref,
        ),
        core_offering_business_owner=repo._table("core_offering_business_owner"),
    )

    reassign = client.post(
        "/vendors/vnd-001/offerings/owners/reassign",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors",
            "from_owner_user_principal": legacy_owner,
            "to_owner_user_principal": "admin@example.com",
            "reason_code": "employee_inactive",
        },
        follow_redirects=False,
    )
    assert reassign.status_code == 303

    owners = repo.get_vendor_offering_business_owners("vnd-001")
    target_row = owners[owners["offering_owner_id"].astype(str) == owner_id]
    assert not target_row.empty
    assert str(target_row.iloc[0]["owner_user_principal"]).strip().lower() == "admin@example.com"


def test_offering_ownership_inactive_owner_shows_reassign_not_edit_action(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    add_owner = client.post(
        "/vendors/vnd-001/offerings/off-004/owners/add",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors",
            "owner_user_principal": "pm@example.com",
            "owner_role": "business_owner",
            "reason": "Assign owner for inactive action test.",
        },
        follow_redirects=False,
    )
    assert add_owner.status_code == 303

    repo = get_repo()
    owners = repo.get_vendor_offering_business_owners("vnd-001")
    owner_rows = owners[
        (owners["offering_id"].astype(str) == "off-004")
        & (owners["owner_user_principal"].astype(str).str.lower() == "pm@example.com")
    ]
    assert not owner_rows.empty
    owner_id = str(owner_rows.iloc[0]["offering_owner_id"])

    def _missing_status(principals):
        return {
            str(item).strip().lower(): {
                "principal": str(item).strip(),
                "status": "missing",
                "active": False,
                "login_identifier": None,
                "display_name": None,
            }
            for item in principals
        }

    monkeypatch.setattr(repo, "get_employee_directory_status_map", _missing_status)

    response = client.get("/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors")
    assert response.status_code == 200
    assert f"offering-owner-reassign-single-template-{owner_id}" in response.text
    assert f"offering-owner-edit-template-{owner_id}" not in response.text
    assert "Open Reassign All" in response.text


def test_offering_owner_single_reassign_updates_only_selected_assignment(client: TestClient) -> None:
    repo = get_repo()
    owner_one = repo.add_offering_owner(
        vendor_id="vnd-001",
        offering_id="off-001",
        owner_user_principal="pm@example.com",
        owner_role="business_owner",
        actor_user_principal="admin@example.com",
    )
    owner_two = repo.add_offering_owner(
        vendor_id="vnd-001",
        offering_id="off-004",
        owner_user_principal="pm@example.com",
        owner_role="technical_owner",
        actor_user_principal="admin@example.com",
    )

    reassign = client.post(
        f"/vendors/vnd-001/offerings/off-004/owners/{owner_two}/reassign",
        data={
            "return_to": "/vendors/vnd-001/offerings/off-004?section=ownership&return_to=%2Fvendors",
            "to_owner_user_principal": "admin@example.com",
            "reason_code": "role_transition",
        },
        follow_redirects=False,
    )
    assert reassign.status_code == 303

    owners = repo.get_vendor_offering_business_owners("vnd-001")
    row_one = owners[owners["offering_owner_id"].astype(str) == str(owner_one)]
    row_two = owners[owners["offering_owner_id"].astype(str) == str(owner_two)]
    assert not row_one.empty and not row_two.empty
    assert str(row_one.iloc[0]["owner_user_principal"]).strip().lower() == "pm@example.com"
    assert str(row_two.iloc[0]["owner_user_principal"]).strip().lower() == "admin@example.com"


def test_parse_template_questions_preserves_optional_required_flag() -> None:
    class FakeForm:
        def __init__(self, values):
            self._values = values

        def getlist(self, key):
            return self._values.get(key, [])

    form = FakeForm(
        {
            "question_label[]": ["Optional Comment"],
            "question_type[]": ["multi_choice"],
            "question_weight[]": ["1"],
            "question_required[]": ["false"],
            "question_layout[]": ["vertical"],
            "question_placeholder[]": [""],
            "allow_multiple[]": ["true"],
            "scale_min[]": ["1"],
            "scale_max[]": ["5"],
            "scale_step[]": ["1"],
            "option_labels[]": ["Excellent, Good, Poor"],
            "option_weights[]": ["1, 0.7, 0.2"],
            "question_help_text[]": ["Optional sentiment check."],
        }
    )

    parsed = parse_template_questions_from_form(form)
    assert len(parsed) == 1
    assert parsed[0]["required"] is False


def test_parse_template_questions_supports_extended_question_types() -> None:
    class FakeForm:
        def __init__(self, values):
            self._values = values

        def getlist(self, key):
            return self._values.get(key, [])

    form = FakeForm(
        {
            "question_label[]": [
                "Overall rating",
                "Business sentiment",
                "Reviewer note",
                "Section intro",
                "Decision option",
            ],
            "question_type[]": [
                "star_rating",
                "likert_scale",
                "long_text",
                "section_header",
                "dropdown_select",
            ],
            "question_weight[]": ["1", "1.5", "0", "0", "1"],
            "question_required[]": ["true", "true", "false", "false", "true"],
            "question_layout[]": ["vertical", "horizontal", "vertical", "vertical", "dropdown"],
            "question_placeholder[]": ["", "", "Enter notes", "", ""],
            "allow_multiple[]": ["false", "false", "false", "false", "false"],
            "scale_min[]": ["1", "1", "1", "1", "1"],
            "scale_max[]": ["5", "5", "5", "5", "5"],
            "scale_step[]": ["1", "1", "1", "1", "1"],
            "option_labels[]": [
                "",
                "Strongly Disagree, Disagree, Neutral, Agree, Strongly Agree",
                "",
                "",
                "Select, Defer",
            ],
            "option_weights[]": ["", "1,2,3,4,5", "", "", "1,0"],
            "question_help_text[]": ["", "", "", "", ""],
        }
    )

    parsed = parse_template_questions_from_form(form)
    by_type = {row["question_type"]: row for row in parsed}
    assert "star_rating" in by_type
    assert by_type["star_rating"]["scale_min"] == 1.0
    assert by_type["star_rating"]["scale_max"] == 5.0
    assert "likert_scale" in by_type
    assert len(by_type["likert_scale"]["options"]) == 5
    assert "long_text" in by_type
    assert by_type["long_text"]["max_answer_weight"] == 0.0
    assert "section_header" in by_type
    assert by_type["section_header"]["required"] is False
    assert by_type["section_header"]["max_answer_weight"] == 0.0
    assert "dropdown_select" in by_type
    assert by_type["dropdown_select"]["layout"] == "dropdown"


def test_offering_sectioned_page_supports_operational_profile_updates(client: TestClient) -> None:
    summary_page = client.get("/vendors/vnd-001/offerings/off-004?return_to=%2Fvendors")
    assert summary_page.status_code == 200
    assert "Offering Summary" in summary_page.text
    assert "Data Flow" in summary_page.text
    assert "Data Exchange Snapshot" not in summary_page.text

    update_response = client.post(
        "/vendors/vnd-001/offerings/off-004/profile/save",
        data={
            "return_to": "/vendors",
            "source_section": "profile",
            "estimated_monthly_cost": "24500",
            "integration_method": "Connector API",
            "implementation_notes": "Regional rollout complete.",
            "data_sent": "Alert metadata and incidents",
            "data_received": "Security events and policy posture",
            "reason": "Baseline profile update",
        },
        follow_redirects=False,
    )
    assert update_response.status_code == 303
    assert "section=profile" in update_response.headers["location"]

    profile_page = client.get("/vendors/vnd-001/offerings/off-004?section=profile&return_to=%2Fvendors")
    assert profile_page.status_code == 200
    assert "Regional rollout complete." in profile_page.text
    assert "24500" in profile_page.text


def test_offering_dataflow_section_can_capture_inbound_outbound_details(client: TestClient) -> None:
    dataflow_page = client.get("/vendors/vnd-001/offerings/off-004?section=dataflow&return_to=%2Fvendors")
    assert dataflow_page.status_code == 200
    assert "Data Feeds" in dataflow_page.text
    assert "Inbound Feeds" in dataflow_page.text
    assert "Outbound Feeds" in dataflow_page.text
    assert "Incoming Data Flow" not in dataflow_page.text
    assert "Outgoing Data Flow" not in dataflow_page.text
    assert "+ Add Data Feed" in dataflow_page.text


def test_offering_dataflow_supports_multiple_rows_per_direction(client: TestClient) -> None:
    first_add = client.post(
        "/vendors/vnd-001/offerings/off-004/dataflows/add",
        data={
            "return_to": "/vendors",
            "direction": "inbound",
            "flow_name": "Billing API feed",
            "method": "api",
            "data_description": "Invoice status and payment events",
            "endpoint_details": "https://vendor.example.com/api/v1/billing",
            "identifiers": "account_id, invoice_id",
            "reporting_layer": "uc.silver_billing",
            "owner_user_principal": "admin@example.com",
            "reason": "Capture first inbound feed",
        },
        follow_redirects=False,
    )
    assert first_add.status_code == 303
    assert "section=dataflow" in first_add.headers["location"]

    second_add = client.post(
        "/vendors/vnd-001/offerings/off-004/dataflows/add",
        data={
            "return_to": "/vendors",
            "direction": "inbound",
            "flow_name": "Service desk file drop",
            "method": "file_transfer",
            "data_description": "Daily incident extract",
            "endpoint_details": "sftp://partner/drop/incidents",
            "reason": "Capture second inbound feed",
        },
        follow_redirects=False,
    )
    assert second_add.status_code == 303

    outbound_add = client.post(
        "/vendors/vnd-001/offerings/off-004/dataflows/add",
        data={
            "return_to": "/vendors",
            "direction": "outbound",
            "flow_name": "Finance reconciliation export",
            "method": "cloud_to_cloud",
            "data_description": "Monthly spend reconciliation payload",
            "creation_process": "Delta table snapshot",
            "delivery_process": "Cross-account share",
            "owner_user_principal": "admin@example.com",
            "reason": "Capture outbound feed",
        },
        follow_redirects=False,
    )
    assert outbound_add.status_code == 303

    dataflow_page = client.get("/vendors/vnd-001/offerings/off-004?section=dataflow&return_to=%2Fvendors")
    assert dataflow_page.status_code == 200
    assert "Billing API feed" in dataflow_page.text
    assert "Service desk file drop" in dataflow_page.text
    assert "Finance reconciliation export" in dataflow_page.text
    assert "edit_data_flow_id=" in dataflow_page.text

    edit_match = re.search(r"edit_data_flow_id=(odf-[^&]+)&", dataflow_page.text)
    assert edit_match is not None
    edit_id = edit_match.group(1)
    update_response = client.post(
        "/vendors/vnd-001/offerings/off-004/dataflows/update",
        data={
            "return_to": "/vendors",
            "data_flow_id": edit_id,
            "direction": "inbound",
            "flow_name": "Billing API feed (updated)",
            "method": "api",
            "data_description": "Updated billing payload",
            "endpoint_details": "https://vendor.example.com/api/v2/billing",
            "identifiers": "account_id, invoice_id, statement_id",
            "reporting_layer": "uc.gold_billing",
            "creation_process": "",
            "delivery_process": "",
            "owner_user_principal": "admin@example.com",
            "notes": "Updated feed shape",
            "reason": "Refresh feed definition",
        },
        follow_redirects=False,
    )
    assert update_response.status_code == 303
    updated_page = client.get("/vendors/vnd-001/offerings/off-004?section=dataflow&return_to=%2Fvendors")
    assert updated_page.status_code == 200
    assert "Billing API feed (updated)" in updated_page.text

    match = re.search(r'name="data_flow_id" value="(odf-[^"]+)"', dataflow_page.text)
    assert match is not None
    remove_id = match.group(1)
    remove_response = client.post(
        "/vendors/vnd-001/offerings/off-004/dataflows/remove",
        data={
            "return_to": "/vendors",
            "data_flow_id": remove_id,
            "reason": "Remove obsolete feed",
        },
        follow_redirects=False,
    )
    assert remove_response.status_code == 303

    after_remove = client.get("/vendors/vnd-001/offerings/off-004?section=dataflow&return_to=%2Fvendors")
    assert after_remove.status_code == 200
    assert "Billing API feed (updated)" not in after_remove.text
    assert "Billing API feed" in after_remove.text
    assert "Finance reconciliation export" in after_remove.text


def test_offering_tickets_and_notes_can_be_added(client: TestClient) -> None:
    ticket_response = client.post(
        "/vendors/vnd-001/offerings/off-004/tickets/add",
        data={
            "return_to": "/vendors",
            "title": "Defender tenant onboarding issue",
            "ticket_system": "ServiceNow",
            "external_ticket_id": "INC-9001",
            "status": "open",
            "priority": "high",
            "opened_date": "2026-02-10",
            "notes": "Escalated with vendor support.",
        },
        follow_redirects=False,
    )
    assert ticket_response.status_code == 303
    assert "section=tickets" in ticket_response.headers["location"]

    note_response = client.post(
        "/vendors/vnd-001/offerings/off-004/notes/add",
        data={
            "return_to": "/vendors",
            "note_type": "issue",
            "note_text": "API latency increased after tenant policy update.",
        },
        follow_redirects=False,
    )
    assert note_response.status_code == 303
    assert "section=notes" in note_response.headers["location"]

    tickets_page = client.get("/vendors/vnd-001/offerings/off-004?section=tickets&return_to=%2Fvendors")
    assert tickets_page.status_code == 200
    assert "INC-9001" in tickets_page.text
    assert "Defender tenant onboarding issue" in tickets_page.text

    notes_page = client.get("/vendors/vnd-001/offerings/off-004?section=notes&return_to=%2Fvendors")
    assert notes_page.status_code == 200
    assert "API latency increased after tenant policy update." in notes_page.text


