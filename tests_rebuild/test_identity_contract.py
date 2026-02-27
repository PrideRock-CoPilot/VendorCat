from __future__ import annotations

from django.test import RequestFactory

from apps.core.contracts.identity import ANONYMOUS_PRINCIPAL, resolve_identity_context


def test_identity_header_precedence() -> None:
    request = RequestFactory().get(
        "/api/v1/identity",
        **{
            "HTTP_X_FORWARDED_PREFERRED_USERNAME": "preferred.user",
            "HTTP_X_FORWARDED_EMAIL": "email@example.com",
            "HTTP_X_FORWARDED_USER": "fallback.user",
            "HTTP_X_FORWARDED_GROUPS": "vendor_admin,invalid group,ops:read",
        },
    )

    identity = resolve_identity_context(request)
    assert identity.user_principal == "preferred.user"
    assert identity.auth_source == "forwarded_preferred_username"
    assert identity.groups == ("vendor_admin", "ops:read")


def test_identity_falls_back_to_email_when_preferred_is_invalid() -> None:
    request = RequestFactory().get(
        "/api/v1/identity",
        **{
            "HTTP_X_FORWARDED_PREFERRED_USERNAME": "bad principal with spaces",
            "HTTP_X_FORWARDED_EMAIL": "valid@example.com",
        },
    )

    identity = resolve_identity_context(request)
    assert identity.user_principal == "valid@example.com"
    assert identity.auth_source == "forwarded_email"
    assert identity.is_anonymous is False


def test_identity_uses_anonymous_fallback_when_headers_are_invalid() -> None:
    request = RequestFactory().get(
        "/api/v1/identity",
        **{
            "HTTP_X_FORWARDED_PREFERRED_USERNAME": "bad principal with spaces",
            "HTTP_X_FORWARDED_EMAIL": "invalid-email",
            "HTTP_X_FORWARDED_USER": "",
        },
    )

    identity = resolve_identity_context(request)
    assert identity.user_principal == ANONYMOUS_PRINCIPAL
    assert identity.auth_source == "anonymous_fallback"
    assert identity.is_anonymous is True


def test_identity_uses_local_dev_override_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("VC_RUNTIME_PROFILE", "local")
    monkeypatch.setenv("VC_DEV_IDENTITY_ENABLED", "true")
    monkeypatch.setenv("VC_DEV_USER", "dev.admin@example.com")
    monkeypatch.setenv("VC_DEV_NAME", "Dev Admin")
    monkeypatch.setenv("VC_DEV_GROUPS", "vendor_admin,workflow_reviewer")

    request = RequestFactory().get("/api/v1/identity")
    identity = resolve_identity_context(request)

    assert identity.user_principal == "dev.admin@example.com"
    assert identity.auth_source == "dev_env_override"
    assert identity.groups == ("vendor_admin", "workflow_reviewer")
    assert identity.is_anonymous is False
