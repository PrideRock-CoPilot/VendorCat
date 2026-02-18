from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from vendor_catalog_app.core.env import (
    TVENDOR_TERMS_ENFORCEMENT_ENABLED,
    get_env_bool,
)
from vendor_catalog_app.core.repository_constants import UNKNOWN_USER_PRINCIPAL

TERMS_SETTING_KEY = "app.terms_acceptance"
TERMS_SESSION_KEY_PREFIX = "tvendor_terms_acceptance"
TERMS_TITLE = "Internal Proof-of-Concept Use Notice"
TERMS_EFFECTIVE_DATE = "February 18, 2026"
TERMS_DOCUMENT_TEXT = """
Internal Proof-of-Concept Use and Data Handling Acknowledgment

This application is provided exclusively for internal exploratory use and controlled evaluation activities.
It is a proof-of-concept platform intended to validate product direction, workflows, and integration patterns.

By continuing, you acknowledge and agree to the following binding conditions:

1. Internal Use Only.
Access and usage are restricted to authorized internal personnel and approved internal business functions.
External distribution, public demonstration, or third-party operational reliance is prohibited unless expressly approved in writing.

2. Not Approved for Enterprise Data.
This proof-of-concept environment is not authorized for enterprise production data, regulated data, or business-critical records.
Users must not upload, process, or store sensitive, confidential, restricted, or regulated data in this environment.

3. No Production Reliance.
Service levels, controls, and data safeguards expected of a production platform are not guaranteed.
Outputs must not be treated as authoritative systems of record or production-grade decision support.

4. User Responsibility.
You are accountable for ensuring all submitted content is non-production and appropriate for a proof-of-concept context.
Any misuse may result in immediate access revocation and further governance review.

5. Terms Versioning and Re-Acceptance.
These terms may be updated periodically.
Continued use requires re-acceptance whenever a revised version is published.
"""


def terms_enforcement_enabled() -> bool:
    return get_env_bool(TVENDOR_TERMS_ENFORCEMENT_ENABLED, default=True)


def current_terms_version() -> str:
    digest = hashlib.sha256(TERMS_DOCUMENT_TEXT.strip().encode("utf-8")).hexdigest()
    return digest[:16]


def terms_sections() -> list[str]:
    sections = [part.strip() for part in TERMS_DOCUMENT_TEXT.strip().split("\n\n")]
    return [section for section in sections if section]


def terms_document() -> dict[str, Any]:
    return {
        "title": TERMS_TITLE,
        "effective_date": TERMS_EFFECTIVE_DATE,
        "version": current_terms_version(),
        "sections": terms_sections(),
    }


def _session_key(user_principal: str) -> str:
    return f"{TERMS_SESSION_KEY_PREFIX}:{str(user_principal or '').strip().lower()}"


def _is_acceptance_valid(setting_payload: dict[str, Any], *, expected_version: str) -> bool:
    accepted = bool(setting_payload.get("accepted", False))
    accepted_version = str(setting_payload.get("version") or "").strip()
    return accepted and accepted_version == expected_version


def has_current_terms_acceptance(*, request, repo, user_principal: str) -> bool:
    if not terms_enforcement_enabled():
        return True
    principal = str(user_principal or "").strip()
    if not principal or principal == UNKNOWN_USER_PRINCIPAL:
        return False

    version = current_terms_version()
    session = request.scope.get("session")
    session_key = _session_key(principal)
    if isinstance(session, dict):
        session_payload = session.get(session_key)
        if isinstance(session_payload, dict) and _is_acceptance_valid(session_payload, expected_version=version):
            return True

    stored = {}
    try:
        stored = repo.get_user_setting(principal, TERMS_SETTING_KEY) or {}
    except Exception:
        stored = {}
    accepted = _is_acceptance_valid(stored, expected_version=version)
    if accepted and isinstance(session, dict):
        session[session_key] = {
            "accepted": True,
            "version": version,
            "accepted_at": str(stored.get("accepted_at") or ""),
        }
    return accepted


def record_terms_acceptance(
    *,
    request,
    repo,
    user_principal: str,
    accepted_version: str,
) -> None:
    principal = str(user_principal or "").strip()
    if not principal or principal == UNKNOWN_USER_PRINCIPAL:
        raise ValueError("A valid user identity is required to accept terms.")
    version = current_terms_version()
    if str(accepted_version or "").strip() != version:
        raise ValueError("Terms version is out of date. Refresh and review the latest terms.")

    now_iso = datetime.now(timezone.utc).isoformat()
    user_agent = str(request.headers.get("user-agent") or "").strip()
    client_host = str(getattr(getattr(request, "client", None), "host", "") or "").strip()
    payload = {
        "accepted": True,
        "version": version,
        "accepted_at": now_iso,
        "effective_date": TERMS_EFFECTIVE_DATE,
        "user_agent": user_agent[:400],
        "client_host": client_host[:120],
    }
    repo.save_user_setting(principal, TERMS_SETTING_KEY, payload)
    session = request.scope.get("session")
    if isinstance(session, dict):
        session[_session_key(principal)] = {
            "accepted": True,
            "version": version,
            "accepted_at": now_iso,
        }
