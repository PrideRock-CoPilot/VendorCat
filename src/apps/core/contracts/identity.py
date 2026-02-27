from __future__ import annotations

import os
import re
from dataclasses import dataclass

from django.http import HttpRequest

ANONYMOUS_PRINCIPAL = "anonymous@example.local"
_PRINCIPAL_RE = re.compile(r"^[A-Za-z0-9._@\\-]{3,255}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_GROUP_RE = re.compile(r"^[A-Za-z0-9:_./-]{1,128}$")


@dataclass(frozen=True)
class IdentityContext:
    user_principal: str
    preferred_username: str
    email: str
    display_name: str
    groups: tuple[str, ...]
    auth_source: str
    is_anonymous: bool


def _is_valid_principal(value: str) -> bool:
    return bool(_PRINCIPAL_RE.fullmatch(value))


def _is_valid_email(value: str) -> bool:
    return bool(_EMAIL_RE.fullmatch(value))


def _parse_groups(raw: str) -> tuple[str, ...]:
    groups: list[str] = []
    for item in raw.split(","):
        candidate = item.strip()
        if candidate and _GROUP_RE.fullmatch(candidate):
            groups.append(candidate)
    return tuple(groups)


def _derive_display_name(principal: str, supplied_name: str) -> str:
    if supplied_name:
        return supplied_name
    if "@" in principal:
        return principal.split("@", 1)[0]
    if "\\" in principal:
        return principal.split("\\", 1)[-1]
    return principal


def resolve_identity_context(request: HttpRequest) -> IdentityContext:
    preferred = str(request.headers.get("X-Forwarded-Preferred-Username", "")).strip()
    email = str(request.headers.get("X-Forwarded-Email", "")).strip()
    fallback = str(request.headers.get("X-Forwarded-User", "")).strip()
    display_name_header = str(request.headers.get("X-Forwarded-Name", "")).strip()
    groups_raw = str(request.headers.get("X-Forwarded-Groups", "")).strip()

    principal = ANONYMOUS_PRINCIPAL
    auth_source = "anonymous_fallback"

    if preferred and _is_valid_principal(preferred):
        principal = preferred
        auth_source = "forwarded_preferred_username"
    elif email and _is_valid_email(email):
        principal = email
        auth_source = "forwarded_email"
    elif fallback and _is_valid_principal(fallback):
        principal = fallback
        auth_source = "forwarded_user"

    groups = _parse_groups(groups_raw)
    display = _derive_display_name(principal, display_name_header)

    runtime_profile = str(os.getenv("VC_RUNTIME_PROFILE", "")).strip().lower()
    dev_identity_enabled = str(os.getenv("VC_DEV_IDENTITY_ENABLED", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    if principal == ANONYMOUS_PRINCIPAL and dev_identity_enabled and runtime_profile in {"local", "dev", "development"}:
        dev_user = str(os.getenv("VC_DEV_USER", "")).strip()
        dev_email = str(os.getenv("VC_DEV_EMAIL", "")).strip()
        dev_name = str(os.getenv("VC_DEV_NAME", "")).strip()
        dev_groups = _parse_groups(str(os.getenv("VC_DEV_GROUPS", "")).strip())

        dev_principal = ""
        if dev_user and _is_valid_principal(dev_user):
            dev_principal = dev_user
        elif dev_email and _is_valid_email(dev_email):
            dev_principal = dev_email

        if dev_principal:
            display = _derive_display_name(dev_principal, dev_name)
            return IdentityContext(
                user_principal=dev_principal,
                preferred_username=dev_user,
                email=dev_email,
                display_name=display,
                groups=dev_groups,
                auth_source="dev_env_override",
                is_anonymous=False,
            )

    return IdentityContext(
        user_principal=principal,
        preferred_username=preferred,
        email=email,
        display_name=display,
        groups=groups,
        auth_source=auth_source,
        is_anonymous=principal == ANONYMOUS_PRINCIPAL,
    )
