from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.core.runtime import get_config, get_repo


def _access_request_rows_for_user(repo, user_principal: str) -> list[dict]:
    principal = str(user_principal or "").strip()
    refs = {principal.lower()} if principal else set()
    try:
        login_identifier = str(repo.resolve_user_login_identifier(principal) or "").strip().lower()
        if login_identifier:
            refs.add(login_identifier)
    except Exception:
        pass
    try:
        actor_ref = str(repo._actor_ref(principal) or "").strip().lower()
        if actor_ref:
            refs.add(actor_ref)
    except Exception:
        pass
    rows = repo.list_change_requests(status="all").to_dict("records")
    out: list[dict] = []
    for row in rows:
        if str(row.get("change_type") or "").strip().lower() != "request_access":
            continue
        requestor = str(
            row.get("requestor_user_principal_raw")
            or row.get("requestor_user_principal")
            or ""
        ).strip().lower()
        if requestor not in refs:
            continue
        out.append(row)
    return out


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, isolated_local_db: Path) -> TestClient:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    return TestClient(app)


def test_access_request_page_shows_existing_request_status_and_locks_submit(client: TestClient) -> None:
    repo = get_repo()
    request_id = repo.create_access_request(
        requestor_user_principal="admin@example.com",
        requested_role="vendor_viewer",
        justification="Need read access for onboarding.",
    )

    response = client.get("/access/request")
    assert response.status_code == 200
    assert "Your Access Requests" in response.text
    assert request_id in response.text
    assert "Submitted" in response.text
    assert "Last Updated" in response.text
    assert "You already have an open access request." in response.text
    assert 'name="requested_role" required disabled' in response.text
    assert 'name="justification" rows="6" required disabled' in response.text
    assert 'title="An access request is already open for your account."' in response.text


def test_access_request_submit_is_blocked_when_open_request_exists(client: TestClient) -> None:
    repo = get_repo()
    repo.create_access_request(
        requestor_user_principal="admin@example.com",
        requested_role="vendor_viewer",
        justification="Need read access for onboarding.",
    )
    before_count = len(_access_request_rows_for_user(repo, "admin@example.com"))

    response = client.post(
        "/access/request",
        data={
            "requested_role": "vendor_auditor",
            "justification": "Need auditor access for controls review.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "An access request is already open for your account." in response.text

    after_count = len(_access_request_rows_for_user(repo, "admin@example.com"))
    assert after_count == before_count


def test_access_request_submit_allowed_after_terminal_decision(client: TestClient) -> None:
    repo = get_repo()
    request_id = repo.create_access_request(
        requestor_user_principal="admin@example.com",
        requested_role="vendor_viewer",
        justification="Need read access for onboarding.",
    )
    repo.update_change_request_status(
        change_request_id=request_id,
        new_status="rejected",
        actor_user_principal="admin@example.com",
        notes="Request closed for retargeting role.",
    )

    page = client.get("/access/request")
    assert page.status_code == 200
    assert "Rejected" in page.text

    before_count = len(_access_request_rows_for_user(repo, "admin@example.com"))
    submit = client.post(
        "/access/request",
        data={
            "requested_role": "vendor_auditor",
            "justification": "Need auditor role for quarterly validation.",
        },
        follow_redirects=False,
    )
    assert submit.status_code == 303
    assert str(submit.headers.get("location", "")) == "/access/request"

    after_count = len(_access_request_rows_for_user(repo, "admin@example.com"))
    assert after_count == before_count + 1


def test_roleless_user_can_submit_access_request(client: TestClient) -> None:
    repo = get_repo()
    principal = "bob.smith@example.com"
    for row in _access_request_rows_for_user(repo, principal):
        status_value = str(row.get("status") or "").strip().lower()
        if status_value in {"approved", "rejected"}:
            continue
        repo.update_change_request_status(
            change_request_id=str(row.get("change_request_id") or ""),
            new_status="rejected",
            actor_user_principal="admin@example.com",
            notes="Test cleanup: close prior open request.",
        )
    before_count = len(_access_request_rows_for_user(repo, principal))

    response = client.post(
        f"/access/request?as_user={principal}",
        data={
            "requested_role": "vendor_viewer",
            "justification": "Need read-only access for onboarding.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert str(response.headers.get("location", "")) == "/access/request"

    after_count = len(_access_request_rows_for_user(repo, principal))
    assert after_count == before_count + 1


def test_access_request_shows_thank_you_then_in_progress_on_reload(client: TestClient) -> None:
    repo = get_repo()
    principal = "bob.smith@example.com"
    for row in _access_request_rows_for_user(repo, principal):
        status_value = str(row.get("status") or "").strip().lower()
        if status_value in {"approved", "rejected"}:
            continue
        repo.update_change_request_status(
            change_request_id=str(row.get("change_request_id") or ""),
            new_status="rejected",
            actor_user_principal="admin@example.com",
            notes="Test cleanup: close prior open request.",
        )

    first_view = client.post(
        f"/access/request?as_user={principal}",
        data={
            "requested_role": "vendor_viewer",
            "justification": "Need access for status messaging test.",
        },
        follow_redirects=True,
    )
    assert first_view.status_code == 200
    assert "Thank you for submitting your access request." in first_view.text
    assert "Request ID:" in first_view.text
    assert "You already have an open access request." not in first_view.text
    assert "Your Access Requests" not in first_view.text

    second_view = client.get(f"/access/request?as_user={principal}")
    assert second_view.status_code == 200
    assert "Thank you for submitting your access request." not in second_view.text
    assert "You already have an open access request." in second_view.text
    assert "Your Access Requests" in second_view.text
