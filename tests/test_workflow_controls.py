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

    decide = client.post(
        f"/workflows/{request_id}/decision",
        data={"decision": "approved", "notes": "Approved in test", "return_to": "/workflows?status=approved"},
        follow_redirects=False,
    )
    assert decide.status_code == 303

    approved = client.get("/workflows?status=approved")
    assert approved.status_code == 200
    assert request_id in approved.text
