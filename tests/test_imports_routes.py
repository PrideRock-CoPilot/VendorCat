from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.core.runtime import get_config, get_repo
from vendor_catalog_app.web.routers import imports as imports_router


class _FakeConfig:
    locked_mode = False


class _FakeUser:
    can_edit = True
    user_principal = "admin@example.com"
    config = _FakeConfig()


class _FakeRepo:
    def __init__(self) -> None:
        self.created_vendors: list[dict[str, str]] = []
        self._settings: dict[tuple[str, str], dict[str, object]] = {}

    def search_vendors_typeahead(self, *, q: str = "", limit: int = 20):
        return pd.DataFrame(columns=["vendor_id", "label", "display_name", "legal_name", "lifecycle_state"])

    def get_vendor_profile(self, _vendor_id: str):
        return pd.DataFrame(columns=["vendor_id", "display_name", "legal_name"])

    def create_vendor_profile(self, **kwargs):
        self.created_vendors.append({k: str(v or "") for k, v in kwargs.items()})
        return "vnd-test-001"

    def apply_vendor_profile_update(self, **_kwargs):
        return {"request_id": "req-test", "change_event_id": "chg-test"}

    def get_offerings_by_ids(self, _offering_ids: list[str]):
        return pd.DataFrame(columns=["offering_id", "vendor_id", "offering_name"])

    def search_offerings_typeahead(self, *, vendor_id: str | None = None, q: str = "", limit: int = 20):
        return pd.DataFrame(columns=["offering_id", "vendor_id", "offering_name", "label"])

    def get_project_by_id(self, _project_id: str):
        return None

    def search_projects_typeahead(self, *, q: str = "", limit: int = 20):
        return pd.DataFrame(columns=["project_id", "project_name", "vendor_id", "label"])

    def update_offering_fields(self, **_kwargs):
        return {"request_id": "req-test", "change_event_id": "chg-test"}

    def create_offering(self, **_kwargs):
        return "off-test-001"

    def create_project(self, **_kwargs):
        return "prj-test-001"

    def update_project(self, **_kwargs):
        return {"request_id": "req-test", "change_event_id": "chg-test"}

    def get_user_setting(self, user_principal: str, setting_key: str):
        return dict(self._settings.get((str(user_principal), str(setting_key)), {}))

    def save_user_setting(self, user_principal: str, setting_key: str, setting_value):
        self._settings[(str(user_principal), str(setting_key))] = dict(setting_value or {})


@pytest.fixture()
def _clear_import_state() -> None:
    imports_router._IMPORT_PREVIEW_STORE.clear()
    yield
    imports_router._IMPORT_PREVIEW_STORE.clear()


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


def test_import_preview_and_apply_vendor_create(
    _clear_import_state: None,
    monkeypatch: pytest.MonkeyPatch,
    isolated_local_db: Path,
) -> None:
    fake_repo = _FakeRepo()
    monkeypatch.setattr(imports_router, "get_repo", lambda: fake_repo)
    monkeypatch.setattr(imports_router, "get_user_context", lambda _request: _FakeUser())
    monkeypatch.setattr(imports_router, "ensure_session_started", lambda _request, _user: None)
    monkeypatch.setattr(imports_router, "log_page_view", lambda _request, _user, _name: None)

    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)

    preview = client.post(
        "/imports/preview",
        files={
            "file": (
                "vendors.csv",
                (
                    b"vendor_id,legal_name,display_name,owner_org_id,lifecycle_state,risk_tier,"
                    b"support_contact_name,support_contact_type,support_email,support_phone\n"
                    b",Acme Cloud,Acme Cloud,IT,draft,medium,Acme Support,business,support@acme.com,555-0100\n"
                ),
                "text/csv",
            )
        },
        data={"layout": "vendors"},
    )
    assert preview.status_code == 200
    assert "Preview And Mapping" in preview.text
    assert "Bulk Action Defaults" in preview.text
    assert "Row Status" in preview.text
    assert "status-ready" in preview.text

    token_match = re.search(r'name="preview_token" value="([a-f0-9]+)"', preview.text)
    assert token_match is not None
    preview_token = token_match.group(1)

    applied = client.post(
        "/imports/apply",
        data={
            "preview_token": preview_token,
            "reason": "bulk load",
            "action_1": "new",
            "target_1": "",
        },
    )
    assert applied.status_code == 200
    assert fake_repo.created_vendors
    assert fake_repo.created_vendors[0]["legal_name"] == "Acme Cloud"


def test_import_preview_quick_mode_rejects_non_template_headers(
    _clear_import_state: None,
    monkeypatch: pytest.MonkeyPatch,
    isolated_local_db: Path,
) -> None:
    fake_repo = _FakeRepo()
    monkeypatch.setattr(imports_router, "get_repo", lambda: fake_repo)
    monkeypatch.setattr(imports_router, "get_user_context", lambda _request: _FakeUser())
    monkeypatch.setattr(imports_router, "ensure_session_started", lambda _request, _user: None)
    monkeypatch.setattr(imports_router, "log_page_view", lambda _request, _user, _name: None)

    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)

    preview = client.post(
        "/imports/preview",
        files={"file": ("vendors.csv", b"legal_name,owner_org_id\nAcme Cloud,IT\n", "text/csv")},
        data={"layout": "vendors", "flow_mode": "quick"},
        follow_redirects=True,
    )
    assert preview.status_code == 200
    assert "Approved layout mismatch for quick upload" in preview.text


def test_import_remap_xml_and_save_mapping_profile(
    _clear_import_state: None,
    monkeypatch: pytest.MonkeyPatch,
    isolated_local_db: Path,
) -> None:
    fake_repo = _FakeRepo()
    monkeypatch.setattr(imports_router, "get_repo", lambda: fake_repo)
    monkeypatch.setattr(imports_router, "get_user_context", lambda _request: _FakeUser())
    monkeypatch.setattr(imports_router, "ensure_session_started", lambda _request, _user: None)
    monkeypatch.setattr(imports_router, "log_page_view", lambda _request, _user, _name: None)

    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)

    xml_payload = (
        "<vendors>"
        "<vendor>"
        "<company_name>Blue Ridge Procurement Services Inc</company_name>"
        "<company_display>Blue Ridge Procurement</company_display>"
        "<owner_org>FIN-OPS</owner_org>"
        "<contact><email>care@blueridgeproc.example</email><phone>1-800-555-1102</phone></contact>"
        "</vendor>"
        "</vendors>"
    )
    preview = client.post(
        "/imports/preview",
        files={"file": ("vendors.xml", xml_payload, "application/xml")},
        data={"layout": "vendors", "flow_mode": "wizard", "format_hint": "xml"},
    )
    assert preview.status_code == 200
    assert "vendor.company_name" in preview.text

    token_match = re.search(r'name="preview_token" value="([a-f0-9]+)"', preview.text)
    assert token_match is not None
    preview_token = token_match.group(1)

    remap = client.post(
        "/imports/remap",
        data={
            "preview_token": preview_token,
            "mapping_profile_name": "xml vendor profile",
            "source_field_keys": [
                "vendor.company_name",
                "vendor.company_display",
                "vendor.owner_org",
                "vendor.contact.email",
                "vendor.contact.phone",
            ],
            "source_target_keys": [
                "vendor.legal_name",
                "vendor.display_name",
                "vendor.owner_org_id",
                "vendor_contact.email",
                "vendor_contact.phone",
            ],
        },
    )
    assert remap.status_code == 200
    assert "Blue Ridge Procurement Services Inc" in remap.text

    settings_rows = list(fake_repo._settings.values())
    assert settings_rows
    profiles = list((settings_rows[0] or {}).get("profiles") or [])
    assert profiles
    profile_id = str(profiles[0].get("profile_id") or "")
    assert profile_id

    preview_with_profile = client.post(
        "/imports/preview",
        files={"file": ("vendors.xml", xml_payload, "application/xml")},
        data={
            "layout": "vendors",
            "flow_mode": "wizard",
            "format_hint": "xml",
            "mapping_profile_id": profile_id,
        },
    )
    assert preview_with_profile.status_code == 200
    assert "Blue Ridge Procurement Services Inc" in preview_with_profile.text

