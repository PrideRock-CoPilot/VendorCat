from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Any

from fastapi import Request

from vendor_catalog_app.config import AppConfig
from vendor_catalog_app.repository import UNKNOWN_USER_PRINCIPAL, VendorRepository
from vendor_catalog_app.security import ADMIN_PORTAL_ROLES, ROLE_CHOICES, ROLE_VIEWER, effective_roles
from vendor_catalog_app.web.context import UserContext
from vendor_catalog_app.web.flash import pop_flashes

ADMIN_ROLE_OVERRIDE_SESSION_KEY = "tvendor_admin_role_override"


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return AppConfig.from_env()


@lru_cache(maxsize=1)
def get_repo() -> VendorRepository:
    return VendorRepository(get_config())


def _resolve_user_principal(repo: VendorRepository, config: AppConfig, request: Request) -> str:
    forced_user = request.query_params.get("as_user")
    if config.use_mock and forced_user:
        return forced_user
    if config.use_mock:
        return os.getenv("TVENDOR_TEST_USER", "admin@example.com")
    return repo.get_current_user()


def _resolve_effective_roles(
    request: Request, raw_roles: set[str], known_roles: set[str] | None = None
) -> tuple[set[str], str | None]:
    session = request.scope.get("session")
    if not isinstance(session, dict):
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


def get_user_context(request: Request) -> UserContext:
    cached = getattr(request.state, "user_context", None)
    if cached is not None:
        return cached

    repo = get_repo()
    config = get_config()
    repo.ensure_runtime_tables()

    user_principal = _resolve_user_principal(repo, config, request)
    if user_principal == UNKNOWN_USER_PRINCIPAL:
        raw_roles = {ROLE_VIEWER}
    else:
        raw_roles = effective_roles(repo.bootstrap_user_access(user_principal))
    known_roles = set(repo.list_known_roles())
    roles, role_override = _resolve_effective_roles(request, raw_roles, known_roles)
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


def ensure_session_started(request: Request, context: UserContext) -> None:
    repo = get_repo()
    session_key = f"usage_session_started_for_{context.user_principal}"
    if request.session.get(session_key):
        return

    repo.log_usage_event(
        user_principal=context.user_principal,
        page_name="app",
        event_type="session_start",
        payload={"locked_mode": context.config.locked_mode, "use_mock": context.config.use_mock},
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
    try:
        doc_owner_options = repo.search_user_directory(q="", limit=200).to_dict("records")
    except Exception:
        doc_owner_options = []
    try:
        doc_source_options = repo.list_doc_source_options()
    except Exception:
        doc_source_options = []
    try:
        doc_tag_options = repo.list_doc_tag_options()
    except Exception:
        doc_tag_options = []
    try:
        owner_role_options = repo.list_owner_role_options()
    except Exception:
        owner_role_options = []
    try:
        assignment_type_options = repo.list_assignment_type_options()
    except Exception:
        assignment_type_options = []
    try:
        contact_type_options = repo.list_contact_type_options()
    except Exception:
        contact_type_options = []
    try:
        project_type_options = repo.list_project_type_options()
    except Exception:
        project_type_options = []
    try:
        offering_type_options = repo.list_offering_type_options()
    except Exception:
        offering_type_options = []
    try:
        offering_lob_options = repo.list_offering_lob_options()
    except Exception:
        offering_lob_options = []
    try:
        offering_service_type_options = repo.list_offering_service_type_options()
    except Exception:
        offering_service_type_options = []

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
        "testing_role_override": context.role_override or "",
        "testing_role_options": role_options,
        "fq_schema": context.config.fq_schema,
        "use_mock": context.config.use_mock,
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
