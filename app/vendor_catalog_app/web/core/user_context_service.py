from __future__ import annotations

import logging
import os
import time
from typing import Any

from fastapi import Request

from vendor_catalog_app.core.config import AppConfig
from vendor_catalog_app.repository import UNKNOWN_USER_PRINCIPAL, VendorRepository
from vendor_catalog_app.core.security import (
    ADMIN_PORTAL_ROLES,
    ROLE_ADMIN,
    ROLE_CHOICES,
)
from vendor_catalog_app.web.core.context import UserContext
from vendor_catalog_app.web.core.identity import (
    resolve_databricks_request_group_principals,
    resolve_databricks_request_identity,
)
from vendor_catalog_app.web.core.runtime import get_config, get_repo, testing_role_override_enabled


ADMIN_ROLE_OVERRIDE_SESSION_KEY = "tvendor_admin_role_override"
IDENTITY_SYNC_SESSION_KEY_PREFIX = "tvendor_identity_synced_at"
POLICY_SNAPSHOT_SESSION_KEY_PREFIX = "tvendor_policy_snapshot"

LOGGER = logging.getLogger(__name__)


def _resolve_user_principal(
    repo: VendorRepository,
    config: AppConfig,
    request: Request,
    forwarded_identity: dict[str, str] | None = None,
) -> str:
    use_local_db = bool(getattr(config, "use_local_db", False))
    is_dev_env = bool(getattr(config, "is_dev_env", False))
    forced_user = request.query_params.get("as_user")
    if use_local_db and is_dev_env and forced_user:
        return forced_user
    if use_local_db and is_dev_env:
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


def get_user_context(request: Request) -> UserContext:
    cached = getattr(request.state, "user_context", None)
    if cached is not None:
        return cached

    repo = get_repo()
    config = get_config()
    dev_allow_all_access = bool(
        getattr(config, "is_dev_env", False)
        and getattr(config, "dev_allow_all_access", False)
    )
    repo.ensure_runtime_tables()
    forwarded_identity = resolve_databricks_request_identity(request)

    user_principal = _resolve_user_principal(repo, config, request, forwarded_identity)
    if dev_allow_all_access and user_principal == UNKNOWN_USER_PRINCIPAL:
        # Dev convenience mode: avoid anonymous principal while forcing admin access.
        fallback_dev_user = str(os.getenv("TVENDOR_TEST_USER", "dev_admin@example.com") or "").strip()
        if fallback_dev_user:
            user_principal = fallback_dev_user
    group_principals = (
        resolve_databricks_request_group_principals(request)
        if user_principal != UNKNOWN_USER_PRINCIPAL
        else set()
    )
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
                snapshot_groups = sorted(
                    {
                        str(item).strip().lower()
                        for item in (raw_snapshot.get("group_principals") or [])
                        if str(item).strip()
                    }
                )
                snapshot_dev_allow_all_access = bool(raw_snapshot.get("dev_allow_all_access", False))
                is_fresh = (now_ts - captured_at) < snapshot_ttl_sec
                if (
                    is_fresh
                    and snapshot_version == policy_version
                    and snapshot_override == role_override_session
                    and snapshot_groups == sorted(group_principals)
                    and snapshot_dev_allow_all_access == dev_allow_all_access
                ):
                    snapshot = raw_snapshot
            except Exception:
                snapshot = None

    if snapshot is not None:
        raw_roles = {
            str(item).strip()
            for item in (snapshot.get("raw_roles") or [])
            if str(item).strip()
        }
        roles = {
            str(item).strip()
            for item in (snapshot.get("roles") or [])
            if str(item).strip()
        } or set(raw_roles)
        role_override = str(snapshot.get("role_override") or "").strip() or None
        role_policy = snapshot.get("role_policy") if isinstance(snapshot.get("role_policy"), dict) else None
    else:
        if user_principal == UNKNOWN_USER_PRINCIPAL:
            raw_roles = set()
        else:
            raw_roles = repo.bootstrap_user_access(
                user_principal,
                group_principals=group_principals,
            )
        known_roles = set(repo.list_known_roles())
        roles, role_override = _resolve_effective_roles(
            request,
            raw_roles,
            known_roles,
            allow_testing_override=testing_role_override_enabled(config),
        )
        role_policy = repo.resolve_role_policy(roles)
        if dev_allow_all_access:
            raw_roles = {ROLE_ADMIN}
            roles = {ROLE_ADMIN}
            role_override = None
            role_policy = repo.resolve_role_policy(roles)
        if isinstance(session, dict) and snapshot_ttl_sec > 0:
            session[snapshot_key] = {
                "captured_at": now_ts,
                "policy_version": policy_version,
                "raw_roles": sorted(raw_roles),
                "roles": sorted(roles),
                "role_override": role_override or "",
                "group_principals": sorted(group_principals),
                "role_policy": dict(role_policy or {}),
                "dev_allow_all_access": dev_allow_all_access,
            }

    if dev_allow_all_access and ROLE_ADMIN not in roles:
        raw_roles = {ROLE_ADMIN}
        roles = {ROLE_ADMIN}
        role_override = None
        role_policy = repo.resolve_role_policy(roles)

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
