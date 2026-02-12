from __future__ import annotations

import json
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
def client(monkeypatch: pytest.MonkeyPatch, isolated_local_db: Path) -> TestClient:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    return TestClient(app)


def test_admin_testing_role_override_changes_effective_permissions(client: TestClient) -> None:
    baseline = client.get("/vendors/new?return_to=%2Fvendors")
    assert baseline.status_code == 200

    set_override = client.post(
        "/admin/testing-role",
        data={"role_override": "vendor_viewer", "return_to": "/vendors/new?return_to=%2Fvendors"},
        follow_redirects=False,
    )
    assert set_override.status_code == 303

    viewer_attempt = client.get("/vendors/new?return_to=%2Fvendors", follow_redirects=False)
    assert viewer_attempt.status_code == 303
    assert viewer_attempt.headers["location"].startswith("/vendors")

    clear_override = client.post(
        "/admin/testing-role",
        data={"role_override": "", "return_to": "/vendors/new?return_to=%2Fvendors"},
        follow_redirects=False,
    )
    assert clear_override.status_code == 303

    restored = client.get("/vendors/new?return_to=%2Fvendors")
    assert restored.status_code == 200


def test_workflow_queue_supports_approve_decision(client: TestClient) -> None:
    submit = client.post(
        "/vendors/vnd-001/change-request",
        data={
            "return_to": "/vendors/vnd-001/changes",
            "change_type": "update_vendor_profile",
            "change_notes": "Route through workflow queue.",
        },
        follow_redirects=True,
    )
    assert submit.status_code == 200
    match = re.search(r"Change request submitted:\s*([0-9a-f-]{36})", submit.text)
    assert match is not None
    request_id = match.group(1)

    queue = client.get("/workflows?status=pending")
    assert queue.status_code == 200
    assert request_id in queue.text
    assert "/decision" not in queue.text

    decide = client.post(
        f"/workflows/{request_id}/decision",
        data={"decision": "approved", "notes": "Approved in test", "return_to": "/workflows?status=approved"},
        follow_redirects=False,
    )
    assert decide.status_code == 303

    approved = client.get("/workflows?status=approved")
    assert approved.status_code == 200
    assert request_id in approved.text


def test_system_admin_override_can_access_admin_but_cannot_edit_or_approve(client: TestClient) -> None:
    set_override = client.post(
        "/admin/testing-role",
        data={"role_override": "system_admin", "return_to": "/admin"},
        follow_redirects=False,
    )
    assert set_override.status_code == 303

    admin_page = client.get("/admin")
    assert admin_page.status_code == 200

    vendor_new = client.get("/vendors/new?return_to=%2Fvendors", follow_redirects=False)
    assert vendor_new.status_code == 303
    assert vendor_new.headers["location"].startswith("/vendors")

    decide = client.post(
        "/workflows/cr-002/decision",
        data={"decision": "approved", "notes": "Should be blocked", "return_to": "/workflows?status=pending"},
        follow_redirects=False,
    )
    assert decide.status_code == 303

    pending = client.get("/workflows?status=pending")
    assert pending.status_code == 200
    repo = get_repo()
    row = repo.get_change_request_by_id("cr-002")
    assert row is not None
    assert str(row.get("status") or "").lower() == "submitted"


def test_approver_override_can_approve_without_edit_access(client: TestClient) -> None:
    set_override = client.post(
        "/admin/testing-role",
        data={"role_override": "vendor_approver", "return_to": "/workflows?queue=my_approvals&status=pending"},
        follow_redirects=False,
    )
    assert set_override.status_code == 303

    vendor_new = client.get("/vendors/new?return_to=%2Fvendors", follow_redirects=False)
    assert vendor_new.status_code == 303

    queue = client.get("/workflows?queue=my_approvals&status=pending")
    assert queue.status_code == 200
    assert "cr-002" in queue.text

    decide = client.post(
        "/workflows/cr-002/decision",
        data={"decision": "approved", "notes": "Approved by approver role", "return_to": "/workflows?status=approved"},
        follow_redirects=False,
    )
    assert decide.status_code == 303

    approved = client.get("/workflows?status=approved")
    assert approved.status_code == 200
    assert "cr-002" in approved.text


def test_viewer_can_submit_change_request_with_assignee_and_higher_level(client: TestClient) -> None:
    set_override = client.post(
        "/admin/testing-role",
        data={"role_override": "vendor_viewer", "return_to": "/vendors/vnd-001/changes?return_to=%2Fvendors"},
        follow_redirects=False,
    )
    assert set_override.status_code == 303

    changes_page = client.get("/vendors/vnd-001/changes?return_to=%2Fvendors")
    assert changes_page.status_code == 200
    assert "Submit Change Request" in changes_page.text
    assert "Assigned Approver" in changes_page.text

    submit = client.post(
        "/vendors/vnd-001/change-request",
        data={
            "return_to": "/vendors",
            "change_type": "update_vendor_profile",
            "change_notes": "Viewer-submitted request",
            "approval_level_required": "9",
            "assigned_approver": "approver@example.com",
        },
        follow_redirects=True,
    )
    assert submit.status_code == 200
    match = re.search(r"Change request submitted:\s*([0-9a-f-]{36})", submit.text)
    assert match is not None
    request_id = match.group(1)

    repo = get_repo()
    row = repo.get_change_request_by_id(request_id)
    assert row is not None
    payload = json.loads(str(row.get("requested_payload_json") or "{}"))
    meta = payload.get("_meta", {})
    assert int(meta.get("approval_level_required") or 0) == 9
    assert str(meta.get("assigned_approver") or "") == "approver@example.com"

    queue = client.get("/workflows?queue=my_submissions&status=all")
    assert queue.status_code == 200
    assert request_id in queue.text


def test_workflow_request_detail_shows_change_payload(client: TestClient) -> None:
    repo = get_repo()
    request_id = repo.create_vendor_change_request(
        vendor_id="vnd-001",
        requestor_user_principal="admin@example.com",
        change_type="update_vendor_profile",
        payload={
            "updates": {"risk_tier": "critical", "owner_org_id": "IT-ENT"},
            "reason": "Risk reassessment",
            "_meta": {"assigned_approver": "approver@example.com"},
        },
    )

    detail = client.get(f"/workflows/{request_id}?return_to=%2Fworkflows%3Fqueue%3Dmy_approvals")
    assert detail.status_code == 200
    assert "Applies To" in detail.text
    assert "/vendors/vnd-001/summary" in detail.text
    assert "Change Review" in detail.text
    assert "updates.risk_tier" in detail.text
    assert "changed" in detail.text
    assert "critical" in detail.text
    assert "Raw Payload" not in detail.text


def test_pending_approvals_respects_business_unit_scope(client: TestClient) -> None:
    repo = get_repo()
    in_scope_request = repo.create_vendor_change_request(
        vendor_id="vnd-001",  # IT-ENT for admin scope
        requestor_user_principal="admin@example.com",
        change_type="update_vendor_profile",
        payload={"updates": {"risk_tier": "high"}, "reason": "IT update"},
    )
    out_scope_request = repo.create_vendor_change_request(
        vendor_id="vnd-002",  # SALES-OPS
        requestor_user_principal="admin@example.com",
        change_type="update_vendor_profile",
        payload={"updates": {"risk_tier": "low"}, "reason": "Sales update"},
    )

    set_override = client.post(
        "/admin/testing-role",
        data={"role_override": "vendor_approver", "return_to": "/workflows/pending-approvals"},
        follow_redirects=False,
    )
    assert set_override.status_code == 303

    pending = client.get("/workflows/pending-approvals", follow_redirects=True)
    assert pending.status_code == 200
    assert "Pending Approvals" in pending.text
    assert in_scope_request in pending.text
    assert out_scope_request not in pending.text


def test_workflow_decision_status_is_admin_managed(client: TestClient) -> None:
    save_lookup = client.post(
        "/admin/lookup/save",
        data={
            "lookup_type": "workflow_status",
            "option_code": "awaiting_info",
            "option_label": "Awaiting Info",
            "sort_order": "5",
            "valid_from_ts": "2025-01-01",
            "valid_to_ts": "9999-12-31",
        },
        follow_redirects=False,
    )
    assert save_lookup.status_code == 303

    submit = client.post(
        "/vendors/vnd-001/change-request",
        data={
            "return_to": "/vendors/vnd-001/changes",
            "change_type": "update_vendor_profile",
            "change_notes": "Needs additional details",
        },
        follow_redirects=True,
    )
    assert submit.status_code == 200
    match = re.search(r"Change request submitted:\s*([0-9a-f-]{36})", submit.text)
    assert match is not None
    request_id = match.group(1)

    detail = client.get(f"/workflows/{request_id}?return_to=%2Fworkflows%3Fstatus%3Dpending")
    assert detail.status_code == 200
    assert '<option value="awaiting_info">Awaiting Info</option>' in detail.text

    decide = client.post(
        f"/workflows/{request_id}/decision",
        data={"decision": "awaiting_info", "notes": "Waiting for owner response", "return_to": "/workflows?status=all"},
        follow_redirects=False,
    )
    assert decide.status_code == 303

    repo = get_repo()
    row = repo.get_change_request_by_id(request_id)
    assert row is not None
    assert str(row.get("status") or "").lower() == "awaiting_info"

    queued = client.get("/workflows?status=awaiting_info&queue=all")
    assert queued.status_code == 200
    assert request_id in queued.text

