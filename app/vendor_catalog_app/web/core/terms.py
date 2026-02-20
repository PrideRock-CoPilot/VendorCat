from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from vendor_catalog_app.core.env import (
    TVENDOR_TERMS_ENFORCEMENT_ENABLED,
    get_env_bool,
)
from vendor_catalog_app.core.repository_constants import UNKNOWN_USER_PRINCIPAL

TERMS_SETTING_KEY = "app.terms_acceptance"
TERMS_SESSION_KEY_PREFIX = "tvendor_terms_acceptance"
TERMS_DOCUMENT_SETTING_PRINCIPAL = "system:terms-policy"
TERMS_DOCUMENT_SETTING_KEY = "terms_document"
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


def _default_terms_payload() -> dict[str, str]:
    return {
        "title": TERMS_TITLE,
        "effective_date": TERMS_EFFECTIVE_DATE,
        "document_text": TERMS_DOCUMENT_TEXT.strip(),
    }


def _stored_terms_payload(repo) -> dict[str, str]:
    if repo is None:
        return {}
    try:
        payload = repo.get_user_setting(
            TERMS_DOCUMENT_SETTING_PRINCIPAL,
            TERMS_DOCUMENT_SETTING_KEY,
        )
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        "title": str(payload.get("title") or "").strip(),
        "effective_date": str(payload.get("effective_date") or "").strip(),
        "document_text": str(payload.get("document_text") or "").strip(),
    }


def _resolved_terms_payload(repo=None) -> dict[str, str]:
    defaults = _default_terms_payload()
    stored = _stored_terms_payload(repo)
    title = stored.get("title") or defaults["title"]
    effective_date = stored.get("effective_date") or defaults["effective_date"]
    document_text = stored.get("document_text") or defaults["document_text"]
    return {
        "title": title,
        "effective_date": effective_date,
        "document_text": document_text,
    }


def save_terms_document(
    *,
    repo,
    title: str,
    effective_date: str,
    document_text: str,
    updated_by: str,
) -> dict[str, str]:
    title_value = str(title or "").strip()
    effective_date_value = str(effective_date or "").strip()
    document_value = str(document_text or "").strip()
    actor = str(updated_by or "").strip() or TERMS_DOCUMENT_SETTING_PRINCIPAL

    if not title_value:
        raise ValueError("Agreement title is required.")
    if not effective_date_value:
        raise ValueError("Effective date is required.")
    if not document_value:
        raise ValueError("Agreement body is required.")

    payload = {
        "title": title_value,
        "effective_date": effective_date_value,
        "document_text": document_value,
        "updated_at": datetime.now(UTC).isoformat(),
        "updated_by": actor,
    }
    repo.save_user_setting(
        TERMS_DOCUMENT_SETTING_PRINCIPAL,
        TERMS_DOCUMENT_SETTING_KEY,
        payload,
    )
    return {
        "title": title_value,
        "effective_date": effective_date_value,
        "document_text": document_value,
    }


def terms_enforcement_enabled() -> bool:
    return get_env_bool(TVENDOR_TERMS_ENFORCEMENT_ENABLED, default=True)


def current_terms_version(*, repo=None) -> str:
    payload = _resolved_terms_payload(repo)
    digest_input = "\n".join(
        [
            payload["title"].strip(),
            payload["effective_date"].strip(),
            payload["document_text"].strip(),
        ]
    )
    digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
    return digest[:16]


def terms_sections(*, repo=None) -> list[str]:
    payload = _resolved_terms_payload(repo)
    sections = [part.strip() for part in payload["document_text"].split("\n\n")]
    return [section for section in sections if section]


def terms_document(*, repo=None) -> dict[str, Any]:
    payload = _resolved_terms_payload(repo)
    return {
        "title": payload["title"],
        "effective_date": payload["effective_date"],
        "version": current_terms_version(repo=repo),
        "sections": terms_sections(repo=repo),
        "document_text": payload["document_text"],
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

    version = current_terms_version(repo=repo)
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
    terms_payload = terms_document(repo=repo)
    version = str(terms_payload.get("version") or "").strip()
    if str(accepted_version or "").strip() != version:
        raise ValueError("Terms version is out of date. Refresh and review the latest terms.")

    now_iso = datetime.now(UTC).isoformat()
    user_agent = str(request.headers.get("user-agent") or "").strip()
    client_host = str(getattr(getattr(request, "client", None), "host", "") or "").strip()
    payload = {
        "accepted": True,
        "version": version,
        "accepted_at": now_iso,
        "effective_date": str(terms_payload.get("effective_date") or "").strip(),
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
