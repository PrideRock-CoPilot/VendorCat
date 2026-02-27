from __future__ import annotations

import sys
from pathlib import Path

from starlette.requests import Request

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.core.config import AppConfig
from vendor_catalog_app.core.security import ROLE_ADMIN, ROLE_VIEWER
from vendor_catalog_app.repository import UNKNOWN_USER_PRINCIPAL
from vendor_catalog_app.web.core import identity, user_context_service


class _FakeRepo:
    def __init__(self, current_user: str, roles: set[str]) -> None:
        self.current_user = current_user
        self.roles = roles
        self.policy_version = 1
        self.bootstrap_called = 0
        self.ensure_called = 0
        self.resolve_policy_called = 0
        self.synced_users: list[str] = []
        self.synced_identity_payloads: list[dict[str, str | None]] = []
        self.last_group_principals: set[str] = set()

    def ensure_runtime_tables(self) -> None:
        self.ensure_called += 1

    def get_current_user(self) -> str:
        return self.current_user

    def bootstrap_user_access(self, user_principal: str, group_principals: set[str] | None = None) -> set[str]:
        self.bootstrap_called += 1
        self.last_group_principals = set(group_principals or set())
        return self.roles

    def sync_user_directory_identity(self, **kwargs):
        login_identifier = str(kwargs.get("login_identifier") or "").strip()
        if login_identifier:
            self.synced_users.append(login_identifier)
        self.synced_identity_payloads.append(dict(kwargs))

    def list_known_roles(self) -> list[str]:
        return sorted(self.roles or {"vendor_viewer"})

    def resolve_role_policy(self, user_roles: set[str]) -> dict[str, object]:
        self.resolve_policy_called += 1
        can_submit_requests = bool(not user_roles or "vendor_viewer" in user_roles or "vendor_editor" in user_roles or "vendor_admin" in user_roles)
        return {
            "roles": sorted(user_roles),
            "can_edit": "vendor_editor" in user_roles or "vendor_admin" in user_roles,
            "can_report": True,
            "can_direct_apply": "vendor_admin" in user_roles,
            "can_submit_requests": can_submit_requests,
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
    monkeypatch.setattr(user_context_service, "get_repo", lambda: repo)
    monkeypatch.setattr(user_context_service, "get_config", lambda: config)
    monkeypatch.setattr(identity, "get_config", lambda: config)

    context = user_context_service.get_user_context(_request())

    assert context.user_principal == UNKNOWN_USER_PRINCIPAL
    assert context.roles == set()
    assert context.can_submit_requests is True
    assert repo.bootstrap_called == 0
    assert repo.ensure_called == 1


def test_non_unknown_user_uses_bootstrap_roles(monkeypatch) -> None:
    repo = _FakeRepo(current_user="editor@example.com", roles={"vendor_editor"})
    config = AppConfig("", "", "", use_local_db=False)
    monkeypatch.setattr(user_context_service, "get_repo", lambda: repo)
    monkeypatch.setattr(user_context_service, "get_config", lambda: config)
    monkeypatch.setattr(identity, "get_config", lambda: config)

    context = user_context_service.get_user_context(_request())

    assert context.user_principal == "editor@example.com"
    assert context.roles == {"vendor_editor"}
    assert repo.bootstrap_called == 1
    assert repo.ensure_called == 1


def test_forwarded_identity_header_takes_precedence(monkeypatch) -> None:
    repo = _FakeRepo(current_user="service_principal@databricks", roles={"vendor_editor"})
    config = AppConfig("", "", "", use_local_db=False)
    monkeypatch.setattr(user_context_service, "get_repo", lambda: repo)
    monkeypatch.setattr(user_context_service, "get_config", lambda: config)
    monkeypatch.setattr(identity, "get_config", lambda: config)
    request = _request(
        headers=[
            (b"x-forwarded-preferred-username", b"jane.doe@example.com"),
            (b"x-forwarded-email", b"jane.doe@example.com"),
        ]
    )

    context = user_context_service.get_user_context(request)

    assert context.user_principal == "jane.doe@example.com"
    assert context.roles == {"vendor_editor"}
    assert repo.bootstrap_called == 1
    assert "jane.doe@example.com" in repo.synced_users
    assert repo.synced_identity_payloads
    assert repo.synced_identity_payloads[-1].get("first_name") == "Jane"
    assert repo.synced_identity_payloads[-1].get("last_name") == "Doe"
    assert repo.synced_identity_payloads[-1].get("network_id") == "jane.doe"


def test_resolve_databricks_identity_uses_explicit_name_and_network_headers(monkeypatch) -> None:
    monkeypatch.setattr(identity, "get_config", lambda: AppConfig("", "", "", use_local_db=False, env="prod"))
    monkeypatch.setenv("TVENDOR_TRUST_FORWARDED_IDENTITY_HEADERS", "true")
    request = _request(
        headers=[
            (b"x-forwarded-preferred-username", b"jane.doe@example.com"),
            (b"x-forwarded-email", b"jane.doe@example.com"),
            (b"x-forwarded-user-id", b"1234567890123456"),
            (b"x-forwarded-given-name", b"Jane"),
            (b"x-forwarded-family-name", b"Doe"),
            (b"x-forwarded-name", b"Jane Doe"),
        ]
    )

    resolved_identity = identity.resolve_databricks_request_identity(request)

    assert resolved_identity["principal"] == "jane.doe@example.com"
    assert resolved_identity["email"] == "jane.doe@example.com"
    assert resolved_identity["network_id"] == "1234567890123456"
    assert resolved_identity["first_name"] == "Jane"
    assert resolved_identity["last_name"] == "Doe"
    assert resolved_identity["display_name"] == "Jane Doe"


def test_resolve_databricks_identity_uses_forwarded_user_for_network_id(monkeypatch) -> None:
    monkeypatch.setattr(identity, "get_config", lambda: AppConfig("", "", "", use_local_db=False, env="prod"))
    monkeypatch.setenv("TVENDOR_TRUST_FORWARDED_IDENTITY_HEADERS", "true")
    request = _request(
        headers=[
            (b"x-forwarded-preferred-username", b"user123@example.com"),
            (b"x-forwarded-user", b"CORP\\john_smith"),
        ]
    )

    resolved_identity = identity.resolve_databricks_request_identity(request)

    assert resolved_identity["principal"] == "user123@example.com"
    assert resolved_identity["email"] == "user123@example.com"
    assert resolved_identity["network_id"] == "john_smith"


def test_forwarded_group_principals_are_normalized_and_passed_to_bootstrap(monkeypatch) -> None:
    repo = _FakeRepo(current_user="service_principal@databricks", roles={"vendor_editor"})
    config = AppConfig("", "", "", use_local_db=False, env="prod")
    monkeypatch.setattr(user_context_service, "get_repo", lambda: repo)
    monkeypatch.setattr(user_context_service, "get_config", lambda: config)
    monkeypatch.setattr(identity, "get_config", lambda: config)
    monkeypatch.setenv("TVENDOR_TRUST_FORWARDED_IDENTITY_HEADERS", "true")
    monkeypatch.setenv("TVENDOR_FORWARDED_GROUP_HEADERS", "x-forwarded-groups")
    request = _request(
        headers=[
            (b"x-forwarded-preferred-username", b"group.member@example.com"),
            (b"x-forwarded-groups", b"AD-Vendor-Admins, Security Team"),
        ]
    )

    context = user_context_service.get_user_context(request)

    assert context.user_principal == "group.member@example.com"
    assert context.roles == {"vendor_editor"}
    assert "group:ad-vendor-admins" in repo.last_group_principals
    assert "group:security_team" in repo.last_group_principals


def test_display_name_formats_email_to_first_last() -> None:
    assert identity.display_name_for_principal("jane.doe@example.com") == "Jane Doe"


def test_display_name_formats_network_principal_to_first_last() -> None:
    assert identity.display_name_for_principal(r"CORP\john_smith") == "John Smith"


def test_display_name_single_token_gets_user_suffix() -> None:
    assert identity.display_name_for_principal("admin@example.com") == "Admin User"


def test_session_policy_snapshot_refreshes_on_policy_version_change(monkeypatch) -> None:
    repo = _FakeRepo(current_user="editor@example.com", roles={"vendor_editor"})
    config = AppConfig("", "", "", use_local_db=False)
    monkeypatch.setattr(user_context_service, "get_repo", lambda: repo)
    monkeypatch.setattr(user_context_service, "get_config", lambda: config)
    monkeypatch.setattr(identity, "get_config", lambda: config)
    session: dict = {}

    context_first = user_context_service.get_user_context(_request(session=session))
    assert context_first.roles == {"vendor_editor"}
    assert repo.bootstrap_called == 1
    assert repo.resolve_policy_called == 1

    repo.roles = {"vendor_admin"}
    context_cached = user_context_service.get_user_context(_request(session=session))
    assert context_cached.roles == {"vendor_editor"}
    assert repo.bootstrap_called == 1
    assert repo.resolve_policy_called == 1

    repo.policy_version = 2
    context_refreshed = user_context_service.get_user_context(_request(session=session))
    assert context_refreshed.roles == {"vendor_admin"}
    assert repo.bootstrap_called == 2
    assert repo.resolve_policy_called == 2


def test_dev_allow_all_access_forces_admin_role(monkeypatch) -> None:
    repo = _FakeRepo(current_user="viewer@example.com", roles={ROLE_VIEWER})
    config = AppConfig("", "", "", use_local_db=False, env="dev", dev_allow_all_access=True)
    monkeypatch.setattr(user_context_service, "get_repo", lambda: repo)
    monkeypatch.setattr(user_context_service, "get_config", lambda: config)
    monkeypatch.setattr(identity, "get_config", lambda: config)

    context = user_context_service.get_user_context(_request())

    assert context.roles == {ROLE_ADMIN}
    assert context.raw_roles == {ROLE_ADMIN}
    assert context.is_admin is True
    assert context.can_edit is True
    assert context.can_approve_requests is True
    assert context.has_admin_rights is True


def test_dev_allow_all_access_is_ignored_outside_dev(monkeypatch) -> None:
    repo = _FakeRepo(current_user="viewer@example.com", roles={ROLE_VIEWER})
    config = AppConfig("", "", "", use_local_db=False, env="prod", dev_allow_all_access=True)
    monkeypatch.setattr(user_context_service, "get_repo", lambda: repo)
    monkeypatch.setattr(user_context_service, "get_config", lambda: config)
    monkeypatch.setattr(identity, "get_config", lambda: config)

    context = user_context_service.get_user_context(_request())

    assert context.roles == {ROLE_VIEWER}


def test_dev_allow_all_access_replaces_unknown_principal(monkeypatch) -> None:
    repo = _FakeRepo(current_user=UNKNOWN_USER_PRINCIPAL, roles={ROLE_VIEWER})
    config = AppConfig("", "", "", use_local_db=False, env="dev", dev_allow_all_access=True)
    monkeypatch.setattr(user_context_service, "get_repo", lambda: repo)
    monkeypatch.setattr(user_context_service, "get_config", lambda: config)
    monkeypatch.setattr(identity, "get_config", lambda: config)
    monkeypatch.setenv("TVENDOR_TEST_USER", "dev.user@example.com")

    context = user_context_service.get_user_context(_request())

    assert context.user_principal == "dev.user@example.com"
    assert context.roles == {ROLE_ADMIN}
