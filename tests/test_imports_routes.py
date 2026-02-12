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


@pytest.fixture()
def _clear_import_state() -> None:
    imports_router._IMPORT_PREVIEW_STORE.clear()
    yield
    imports_router._IMPORT_PREVIEW_STORE.clear()


def test_import_template_download_returns_csv(_clear_import_state: None) -> None:
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
) -> None:
    fake_repo = _FakeRepo()
    monkeypatch.setattr(imports_router, "get_repo", lambda: fake_repo)
    monkeypatch.setattr(imports_router, "get_user_context", lambda _request: _FakeUser())
    monkeypatch.setattr(imports_router, "ensure_session_started", lambda _request, _user: None)
    monkeypatch.setattr(imports_router, "log_page_view", lambda _request, _user, _name: None)

    app = create_app()
    client = TestClient(app)

    preview = client.post(
        "/imports/preview",
        files={"file": ("vendors.csv", b"legal_name,owner_org_id\nAcme Cloud,IT\n", "text/csv")},
        data={"layout": "vendors"},
    )
    assert preview.status_code == 200
    assert "Preview And Mapping" in preview.text

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

