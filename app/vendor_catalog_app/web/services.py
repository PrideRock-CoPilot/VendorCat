from __future__ import annotations

import logging
import os
import re
import time
from functools import lru_cache
from typing import Any

from fastapi import Request

from vendor_catalog_app.config import AppConfig
from vendor_catalog_app.env import (
    TVENDOR_ALLOW_TEST_ROLE_OVERRIDE,
    TVENDOR_TRUST_FORWARDED_IDENTITY_HEADERS,
    get_env_bool,
)
from vendor_catalog_app.repository_constants import (
    DEFAULT_ASSIGNMENT_TYPE_OPTIONS,
    DEFAULT_CONTACT_TYPE_OPTIONS,
    DEFAULT_DOC_SOURCE_OPTIONS,
    DEFAULT_DOC_TAG_OPTIONS,
    DEFAULT_OFFERING_LOB_CHOICES,
    DEFAULT_OFFERING_SERVICE_TYPE_CHOICES,
    DEFAULT_OFFERING_TYPE_CHOICES,
    DEFAULT_OWNER_ROLE_OPTIONS,
    DEFAULT_PROJECT_TYPE_OPTIONS,
    LOOKUP_TYPE_ASSIGNMENT_TYPE,
    LOOKUP_TYPE_CONTACT_TYPE,
    LOOKUP_TYPE_DOC_SOURCE,
    LOOKUP_TYPE_DOC_TAG,
    LOOKUP_TYPE_OFFERING_LOB,
    LOOKUP_TYPE_OFFERING_SERVICE_TYPE,
    LOOKUP_TYPE_OFFERING_TYPE,
    LOOKUP_TYPE_OWNER_ROLE,
    LOOKUP_TYPE_PROJECT_TYPE,
)
from vendor_catalog_app.repository import UNKNOWN_USER_PRINCIPAL, VendorRepository
from vendor_catalog_app.security import (
    ADMIN_PORTAL_ROLES,
    MAX_APPROVAL_LEVEL,
    MIN_APPROVAL_LEVEL,
    MIN_CHANGE_APPROVAL_LEVEL,
    ROLE_CHOICES,
    ROLE_VIEWER,
    effective_roles,
)
from vendor_catalog_app.web.context import UserContext
from vendor_catalog_app.web.flash import pop_flashes

ADMIN_ROLE_OVERRIDE_SESSION_KEY = "tvendor_admin_role_override"
IDENTITY_SYNC_SESSION_KEY_PREFIX = "tvendor_identity_synced_at"
POLICY_SNAPSHOT_SESSION_KEY_PREFIX = "tvendor_policy_snapshot"
LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return AppConfig.from_env()


@lru_cache(maxsize=1)
def get_repo() -> VendorRepository:
    return VendorRepository(get_config())


def trust_forwarded_identity_headers(config: AppConfig) -> bool:
    return get_env_bool(
        TVENDOR_TRUST_FORWARDED_IDENTITY_HEADERS,
        default=config.is_dev_env,
    )


def testing_role_override_enabled(config: AppConfig) -> bool:
    return get_env_bool(
        TVENDOR_ALLOW_TEST_ROLE_OVERRIDE,
        default=config.is_dev_env,
    )


def _sanitize_header_identity_value(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if any(ch in text for ch in ("\r", "\n", "\t", "\x00")):
        return ""
    if len(text) > 320:
        return ""
    return text


def _first_header(request: Request, names: list[str]) -> str:
    for name in names:
        raw = _sanitize_header_identity_value(str(request.headers.get(name, "")))
        if raw:
            return raw
    return ""


def resolve_databricks_request_identity(request: Request) -> dict[str, str]:
    config = get_config()
    if not trust_forwarded_identity_headers(config):
        return {
            "principal": "",
            "email": "",
            "network_id": "",
            "first_name": "",
            "last_name": "",
            "display_name": "",
        }
    email = _first_header(request, ["x-forwarded-email"])
    preferred_username = _first_header(request, ["x-forwarded-preferred-username"])
    forwarded_user = _first_header(request, ["x-forwarded-user"])

    principal = preferred_username or email or forwarded_user
    network_id = ""
    if principal and "@" not in principal:
        network_id = principal.split("\\")[-1].split("/")[-1]

    first_name = ""
    last_name = ""
    display_name = ""
    if principal:
        parsed_name = _display_name_for_principal(principal)
        display_name = parsed_name if parsed_name != "Unknown User" else ""
        parts = [part for part in display_name.split(" ") if part and part.lower() != "user"]
        if parts:
            first_name = parts[0]
            last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    return {
        "principal": principal,
        "email": email or (principal if "@" in principal else ""),
        "network_id": network_id,
        "first_name": first_name,
        "last_name": last_name,
        "display_name": display_name,
    }


def _resolve_user_principal(
    repo: VendorRepository,
    config: AppConfig,
    request: Request,
    forwarded_identity: dict[str, str] | None = None,
) -> str:
    forced_user = request.query_params.get("as_user")
    if config.use_local_db and config.is_dev_env and forced_user:
        return forced_user
    if config.use_local_db and config.is_dev_env:
        return os.getenv("TVENDOR_TEST_USER", UNKNOWN_USER_PRINCIPAL)
    identity = forwarded_identity or {}
    principal = str(identity.get("principal") or "").strip()
    if principal:
        return principal
    return repo.get_current_user()


def _resolve_effective_roles(
    request: Request,
    raw_roles: set[str],
    known_roles: set[str] | None = None,
    *,
    allow_testing_override: bool = True,
) -> tuple[set[str], str | None]:
    session = request.scope.get("session")
    if not isinstance(session, dict):
        return raw_roles, None

    if not allow_testing_override:
        session.pop(ADMIN_ROLE_OVERRIDE_SESSION_KEY, None)
        return raw_roles, None

    if not set(ADMIN_PORTAL_ROLES).intersection(raw_roles):
        session.pop(ADMIN_ROLE_OVERRIDE_SESSION_KEY, None)
        return raw_roles, None

    override = str(session.get(ADMIN_ROLE_OVERRIDE_SESSION_KEY, "")).strip()
    if not override:
        return raw_roles, None
    allowed = set(known_roles or set()) or set(ROLE_CHOICES)
    if override not in allowed:
        session.pop(ADMIN_ROLE_OVERRIDE_SESSION_KEY, None)
        return raw_roles, None
    return {override}, override


def _display_name_for_principal(user_principal: str) -> str:
    raw = str(user_principal or "").strip()
    if not raw:
        return "Unknown User"

    normalized = raw.split("\\")[-1].split("/")[-1]
    if "@" in normalized:
        normalized = normalized.split("@", 1)[0]
    normalized = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", normalized)
    normalized = re.sub(r"[._-]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return "Unknown User"

    parts = [part.capitalize() for part in normalized.split(" ") if part]
    if not parts:
        return "Unknown User"
    if len(parts) == 1:
        return f"{parts[0]} User"
    return " ".join(parts)


def _lookup_values(
    lookup_rows: list[dict[str, Any]],
    *,
    lookup_type: str,
    prefer_label: bool,
    fallback: list[str],
) -> list[str]:
    options: list[str] = []
    seen: set[str] = set()
    for row in lookup_rows:
        if str(row.get("lookup_type") or "").strip().lower() != lookup_type:
            continue
        code = str(row.get("option_code") or "").strip()
        label = str(row.get("option_label") or "").strip()
        value = label if prefer_label else code.lower()
        if not value:
            value = (code or label).strip()
        if not value:
            continue
        normalized = value.lower() if not prefer_label else value
        if normalized in seen:
            continue
        seen.add(normalized)
        options.append(value)
    return options or list(fallback)


def get_user_context(request: Request) -> UserContext:
    cached = getattr(request.state, "user_context", None)
    if cached is not None:
        return cached

    repo = get_repo()
    config = get_config()
    repo.ensure_runtime_tables()
    forwarded_identity = resolve_databricks_request_identity(request)

    user_principal = _resolve_user_principal(repo, config, request, forwarded_identity)
    if user_principal != UNKNOWN_USER_PRINCIPAL:
        session = request.scope.get("session")
        sync_ttl_sec = max(0, int(str(os.getenv("TVENDOR_IDENTITY_SYNC_TTL_SEC", "300")).strip() or "300"))
        should_sync = True
        session_key = f"{IDENTITY_SYNC_SESSION_KEY_PREFIX}:{user_principal}"
        now_ts = int(time.time())
        if isinstance(session, dict) and sync_ttl_sec > 0:
            last_synced = int(str(session.get(session_key, "0")).strip() or "0")
            should_sync = (now_ts - last_synced) >= sync_ttl_sec
        if should_sync:
            try:
                repo.sync_user_directory_identity(
                    login_identifier=user_principal,
                    email=forwarded_identity.get("email") or None,
                    network_id=forwarded_identity.get("network_id") or None,
                    first_name=forwarded_identity.get("first_name") or None,
                    last_name=forwarded_identity.get("last_name") or None,
                    display_name=forwarded_identity.get("display_name") or None,
                )
                if isinstance(session, dict):
                    session[session_key] = now_ts
            except Exception:
                LOGGER.warning("Failed to sync user directory identity for '%s'.", user_principal, exc_info=True)
    session = request.scope.get("session")
    snapshot_key = f"{POLICY_SNAPSHOT_SESSION_KEY_PREFIX}:{user_principal}"
    snapshot_ttl_sec = max(0, int(str(os.getenv("TVENDOR_POLICY_SNAPSHOT_TTL_SEC", "300")).strip() or "300"))
    now_ts = int(time.time())
    policy_version = repo.get_security_policy_version()
    role_override_session = ""
    if isinstance(session, dict):
        role_override_session = str(session.get(ADMIN_ROLE_OVERRIDE_SESSION_KEY, "")).strip()

    snapshot: dict[str, Any] | None = None
    if isinstance(session, dict) and snapshot_ttl_sec > 0:
        raw_snapshot = session.get(snapshot_key)
        if isinstance(raw_snapshot, dict):
            try:
                captured_at = int(raw_snapshot.get("captured_at") or 0)
                snapshot_version = int(raw_snapshot.get("policy_version") or 0)
                snapshot_override = str(raw_snapshot.get("role_override") or "").strip()
                is_fresh = (now_ts - captured_at) < snapshot_ttl_sec
                if is_fresh and snapshot_version == policy_version and snapshot_override == role_override_session:
                    snapshot = raw_snapshot
            except Exception:
                snapshot = None

    if snapshot is not None:
        raw_roles = {
            str(item).strip()
            for item in (snapshot.get("raw_roles") or [])
            if str(item).strip()
        } or {ROLE_VIEWER}
        roles = {
            str(item).strip()
            for item in (snapshot.get("roles") or [])
            if str(item).strip()
        } or set(raw_roles)
        role_override = str(snapshot.get("role_override") or "").strip() or None
        role_policy = snapshot.get("role_policy") if isinstance(snapshot.get("role_policy"), dict) else None
    else:
        if user_principal == UNKNOWN_USER_PRINCIPAL:
            raw_roles = {ROLE_VIEWER}
        else:
            raw_roles = effective_roles(repo.bootstrap_user_access(user_principal))
        known_roles = set(repo.list_known_roles())
        roles, role_override = _resolve_effective_roles(
            request,
            raw_roles,
            known_roles,
            allow_testing_override=testing_role_override_enabled(config),
        )
        role_policy = repo.resolve_role_policy(roles)
        if isinstance(session, dict) and snapshot_ttl_sec > 0:
            session[snapshot_key] = {
                "captured_at": now_ts,
                "policy_version": policy_version,
                "raw_roles": sorted(raw_roles),
                "roles": sorted(roles),
                "role_override": role_override or "",
                "role_policy": dict(role_policy or {}),
            }

    context = UserContext(
        user_principal=user_principal,
        roles=roles,
        raw_roles=raw_roles,
        config=config,
        role_override=role_override,
        role_policy=role_policy,
    )
    request.state.user_context = context
    return context


def ensure_session_started(request: Request, context: UserContext) -> None:
    repo = get_repo()
    session_key = f"usage_session_started_for_{context.user_principal}"
    if request.session.get(session_key):
        return

    repo.log_usage_event(
        user_principal=context.user_principal,
        page_name="app",
        event_type="session_start",
        payload={"locked_mode": context.config.locked_mode},
    )
    request.session[session_key] = True


def log_page_view(request: Request, context: UserContext, page_name: str) -> None:
    repo = get_repo()
    session_key = f"usage_last_page_for_{context.user_principal}"
    if request.session.get(session_key) == page_name:
        return
    repo.log_usage_event(
        user_principal=context.user_principal,
        page_name=page_name,
        event_type="page_view",
        payload=None,
    )
    request.session[session_key] = page_name


def base_template_context(
    request: Request,
    context: UserContext,
    title: str,
    active_nav: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repo = get_repo()
    user_display_name = _display_name_for_principal(context.user_principal)
    try:
        user_display_name = repo.get_user_display_name(context.user_principal)
    except Exception:
        user_display_name = _display_name_for_principal(context.user_principal)

    role_options = list(ROLE_CHOICES)
    try:
        role_options = repo.list_known_roles()
    except Exception:
        role_options = list(ROLE_CHOICES)
    testing_override_allowed = testing_role_override_enabled(context.config)
    if not testing_override_allowed:
        role_options = []
    try:
        doc_owner_options = repo.search_user_directory(q="", limit=200).to_dict("records")
    except Exception:
        doc_owner_options = []
    doc_source_options = list(DEFAULT_DOC_SOURCE_OPTIONS)
    doc_tag_options = list(DEFAULT_DOC_TAG_OPTIONS)
    owner_role_options = list(DEFAULT_OWNER_ROLE_OPTIONS)
    assignment_type_options = list(DEFAULT_ASSIGNMENT_TYPE_OPTIONS)
    contact_type_options = list(DEFAULT_CONTACT_TYPE_OPTIONS)
    project_type_options = list(DEFAULT_PROJECT_TYPE_OPTIONS)
    offering_type_options = [label for _, label in DEFAULT_OFFERING_TYPE_CHOICES]
    offering_lob_options = [label for _, label in DEFAULT_OFFERING_LOB_CHOICES]
    offering_service_type_options = [label for _, label in DEFAULT_OFFERING_SERVICE_TYPE_CHOICES]
    try:
        lookup_df = repo.list_lookup_options(active_only=True)
        lookup_rows = lookup_df.to_dict("records") if not lookup_df.empty else []
        doc_source_options = _lookup_values(
            lookup_rows,
            lookup_type=LOOKUP_TYPE_DOC_SOURCE,
            prefer_label=False,
            fallback=doc_source_options,
        )
        doc_tag_options = _lookup_values(
            lookup_rows,
            lookup_type=LOOKUP_TYPE_DOC_TAG,
            prefer_label=False,
            fallback=doc_tag_options,
        )
        owner_role_options = _lookup_values(
            lookup_rows,
            lookup_type=LOOKUP_TYPE_OWNER_ROLE,
            prefer_label=False,
            fallback=owner_role_options,
        )
        assignment_type_options = _lookup_values(
            lookup_rows,
            lookup_type=LOOKUP_TYPE_ASSIGNMENT_TYPE,
            prefer_label=False,
            fallback=assignment_type_options,
        )
        contact_type_options = _lookup_values(
            lookup_rows,
            lookup_type=LOOKUP_TYPE_CONTACT_TYPE,
            prefer_label=False,
            fallback=contact_type_options,
        )
        project_type_options = _lookup_values(
            lookup_rows,
            lookup_type=LOOKUP_TYPE_PROJECT_TYPE,
            prefer_label=False,
            fallback=project_type_options,
        )
        offering_type_options = _lookup_values(
            lookup_rows,
            lookup_type=LOOKUP_TYPE_OFFERING_TYPE,
            prefer_label=True,
            fallback=offering_type_options,
        )
        offering_lob_options = _lookup_values(
            lookup_rows,
            lookup_type=LOOKUP_TYPE_OFFERING_LOB,
            prefer_label=True,
            fallback=offering_lob_options,
        )
        offering_service_type_options = _lookup_values(
            lookup_rows,
            lookup_type=LOOKUP_TYPE_OFFERING_SERVICE_TYPE,
            prefer_label=True,
            fallback=offering_service_type_options,
        )
    except Exception:
        pass

    payload: dict[str, Any] = {
        "request": request,
        "title": title,
        "active_nav": active_nav,
        "user_principal": context.user_principal,
        "user_display_name": user_display_name,
        "raw_roles": sorted(list(context.raw_roles)),
        "roles": sorted(list(context.roles)),
        "can_edit": context.can_edit,
        "can_report": context.can_report,
        "can_submit_requests": context.can_submit_requests,
        "can_approve_requests": context.can_approve_requests,
        "can_access_workflows": context.can_access_workflows,
        "can_direct_apply": context.can_direct_apply,
        "is_admin": context.is_admin,
        "has_admin_rights": context.has_admin_rights,
        "approval_level": context.approval_level,
        "approval_level_min": MIN_APPROVAL_LEVEL,
        "approval_level_max": MAX_APPROVAL_LEVEL,
        "change_approval_level_min": MIN_CHANGE_APPROVAL_LEVEL,
        "role_approval_level_options": list(range(MIN_APPROVAL_LEVEL, MAX_APPROVAL_LEVEL + 1)),
        "change_approval_level_options": list(range(MIN_CHANGE_APPROVAL_LEVEL, MAX_APPROVAL_LEVEL + 1)),
        "testing_role_override": context.role_override or "",
        "testing_role_override_enabled": bool(testing_override_allowed),
        "testing_role_options": role_options,
        "fq_schema": context.config.fq_schema,
        "use_local_db": context.config.use_local_db,
        "local_db_path": context.config.local_db_path,
        "locked_mode": context.config.locked_mode,
        "flashes": pop_flashes(request),
        "doc_source_options": doc_source_options,
        "doc_tag_options": doc_tag_options,
        "doc_owner_options": doc_owner_options,
        "owner_role_options": owner_role_options,
        "assignment_type_options": assignment_type_options,
        "contact_type_options": contact_type_options,
        "project_type_options": project_type_options,
        "offering_type_options": offering_type_options,
        "offering_lob_options": offering_lob_options,
        "offering_service_type_options": offering_service_type_options,
    }
    if extra:
        payload.update(extra)
    return payload
