from __future__ import annotations

import sys
from pathlib import Path

from starlette.requests import Request

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.config import AppConfig
from vendor_catalog_app.repository import UNKNOWN_USER_PRINCIPAL
from vendor_catalog_app.security import ROLE_VIEWER
from vendor_catalog_app.web import services


class _FakeRepo:
    def __init__(self, current_user: str, roles: set[str]) -> None:
        self.current_user = current_user
        self.roles = roles
        self.policy_version = 1
        self.bootstrap_called = 0
        self.ensure_called = 0
        self.resolve_policy_called = 0
        self.synced_users: list[str] = []

    def ensure_runtime_tables(self) -> None:
        self.ensure_called += 1

    def get_current_user(self) -> str:
        return self.current_user

    def bootstrap_user_access(self, user_principal: str) -> set[str]:
        self.bootstrap_called += 1
        return self.roles

    def sync_user_directory_identity(self, **kwargs):
        login_identifier = str(kwargs.get("login_identifier") or "").strip()
        if login_identifier:
            self.synced_users.append(login_identifier)

    def list_known_roles(self) -> list[str]:
        return sorted(self.roles or {"vendor_viewer"})

    def resolve_role_policy(self, user_roles: set[str]) -> dict[str, object]:
        self.resolve_policy_called += 1
        return {
            "roles": sorted(user_roles),
            "can_edit": "vendor_editor" in user_roles or "vendor_admin" in user_roles,
            "can_report": True,
            "can_direct_apply": "vendor_admin" in user_roles,
            "approval_level": 10 if "vendor_admin" in user_roles else (4 if "vendor_editor" in user_roles else 0),
            "allowed_change_actions": [],
        }

    def get_security_policy_version(self) -> int:
        return self.policy_version


def _request(
    path: str = "/dashboard",
    headers: list[tuple[bytes, bytes]] | None = None,
    session: dict | None = None,
) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": b"",
            "headers": headers or [],
            "session": session if session is not None else {},
        }
    )


def test_unknown_user_gets_viewer_without_bootstrap(monkeypatch) -> None:
    repo = _FakeRepo(current_user=UNKNOWN_USER_PRINCIPAL, roles={"vendor_admin"})
    config = AppConfig("", "", "", use_local_db=False)
    monkeypatch.setattr(services, "get_repo", lambda: repo)
    monkeypatch.setattr(services, "get_config", lambda: config)

    context = services.get_user_context(_request())

    assert context.user_principal == UNKNOWN_USER_PRINCIPAL
    assert context.roles == {ROLE_VIEWER}
    assert repo.bootstrap_called == 0
    assert repo.ensure_called == 1


def test_non_unknown_user_uses_bootstrap_roles(monkeypatch) -> None:
    repo = _FakeRepo(current_user="editor@example.com", roles={"vendor_editor"})
    config = AppConfig("", "", "", use_local_db=False)
    monkeypatch.setattr(services, "get_repo", lambda: repo)
    monkeypatch.setattr(services, "get_config", lambda: config)

    context = services.get_user_context(_request())

    assert context.user_principal == "editor@example.com"
    assert context.roles == {"vendor_editor"}
    assert repo.bootstrap_called == 1
    assert repo.ensure_called == 1


def test_forwarded_identity_header_takes_precedence(monkeypatch) -> None:
    repo = _FakeRepo(current_user="service_principal@databricks", roles={"vendor_editor"})
    config = AppConfig("", "", "", use_local_db=False)
    monkeypatch.setattr(services, "get_repo", lambda: repo)
    monkeypatch.setattr(services, "get_config", lambda: config)
    request = _request(
        headers=[
            (b"x-forwarded-preferred-username", b"jane.doe@example.com"),
            (b"x-forwarded-email", b"jane.doe@example.com"),
        ]
    )

    context = services.get_user_context(request)

    assert context.user_principal == "jane.doe@example.com"
    assert context.roles == {"vendor_editor"}
    assert repo.bootstrap_called == 1
    assert "jane.doe@example.com" in repo.synced_users


def test_display_name_formats_email_to_first_last() -> None:
    assert services._display_name_for_principal("jane.doe@example.com") == "Jane Doe"


def test_display_name_formats_network_principal_to_first_last() -> None:
    assert services._display_name_for_principal(r"CORP\john_smith") == "John Smith"


def test_display_name_single_token_gets_user_suffix() -> None:
    assert services._display_name_for_principal("admin@example.com") == "Admin User"


def test_session_policy_snapshot_refreshes_on_policy_version_change(monkeypatch) -> None:
    repo = _FakeRepo(current_user="editor@example.com", roles={"vendor_editor"})
    config = AppConfig("", "", "", use_local_db=False)
    monkeypatch.setattr(services, "get_repo", lambda: repo)
    monkeypatch.setattr(services, "get_config", lambda: config)
    session: dict = {}

    context_first = services.get_user_context(_request(session=session))
    assert context_first.roles == {"vendor_editor"}
    assert repo.bootstrap_called == 1
    assert repo.resolve_policy_called == 1

    repo.roles = {"vendor_admin"}
    context_cached = services.get_user_context(_request(session=session))
    assert context_cached.roles == {"vendor_editor"}
    assert repo.bootstrap_called == 1
    assert repo.resolve_policy_called == 1

    repo.policy_version = 2
    context_refreshed = services.get_user_context(_request(session=session))
    assert context_refreshed.roles == {"vendor_admin"}
    assert repo.bootstrap_called == 2
    assert repo.resolve_policy_called == 2
