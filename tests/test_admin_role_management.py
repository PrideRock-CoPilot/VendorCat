from __future__ import annotations

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


def test_admin_can_create_custom_role_and_use_testing_override(client: TestClient) -> None:
    save = client.post(
        "/admin/roles/save",
        data={
            "role_code": "vendor_note_editor",
            "role_name": "Vendor Note Editor",
            "description": "Can edit and submit notes.",
            "approval_level": "1",
            "can_edit": "on",
            "can_report": "on",
            "perm_add_project_note": "on",
        },
        follow_redirects=False,
    )
    assert save.status_code == 303

    admin_page = client.get("/admin")
    assert admin_page.status_code == 200
    assert "vendor_note_editor" in admin_page.text

    set_override = client.post(
        "/admin/testing-role",
        data={"role_override": "vendor_note_editor", "return_to": "/vendors/new?return_to=%2Fvendors"},
        follow_redirects=False,
    )
    assert set_override.status_code == 303

    with_override = client.get("/vendors/new?return_to=%2Fvendors")
    assert with_override.status_code == 200


def test_admin_can_grant_custom_role_to_user(client: TestClient) -> None:
    client.post(
        "/admin/roles/save",
        data={
            "role_code": "vendor_custom_reporter",
            "role_name": "Vendor Custom Reporter",
            "description": "Custom reporting role.",
            "approval_level": "0",
            "can_report": "on",
        },
        follow_redirects=False,
    )

    grant = client.post(
        "/admin/grant-role",
        data={"target_user": "custom.user@example.com", "role_code": "vendor_custom_reporter"},
        follow_redirects=False,
    )
    assert grant.status_code == 303

    admin_page = client.get("/admin")
    assert admin_page.status_code == 200
    assert "custom.user@example.com" in admin_page.text
    assert "vendor_custom_reporter" in admin_page.text
