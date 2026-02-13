from __future__ import annotations

from typing import Any

from fastapi import Request

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
from vendor_catalog_app.security import (
    MAX_APPROVAL_LEVEL,
    MIN_APPROVAL_LEVEL,
    MIN_CHANGE_APPROVAL_LEVEL,
    ROLE_CHOICES,
)
from vendor_catalog_app.web.core.context import UserContext
from vendor_catalog_app.web.core.identity import display_name_for_principal
from vendor_catalog_app.web.core.runtime import get_repo, testing_role_override_enabled
from vendor_catalog_app.web.http.flash import pop_flashes
from vendor_catalog_app.web.security.controls import CSRF_SESSION_KEY


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


def base_template_context(
    request: Request,
    context: UserContext,
    title: str,
    active_nav: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repo = get_repo()
    config = context.config
    config_fq_schema = str(getattr(config, "fq_schema", "") or "")
    config_use_local_db = bool(getattr(config, "use_local_db", False))
    config_local_db_path = str(getattr(config, "local_db_path", "") or "")
    config_locked_mode = bool(getattr(config, "locked_mode", False))
    raw_roles = {
        str(item).strip()
        for item in (getattr(context, "raw_roles", set()) or set())
        if str(item).strip()
    }
    roles = {
        str(item).strip()
        for item in (getattr(context, "roles", set()) or set())
        if str(item).strip()
    }
    can_edit = bool(getattr(context, "can_edit", False))
    can_report = bool(getattr(context, "can_report", False))
    can_submit_requests = bool(getattr(context, "can_submit_requests", False))
    can_approve_requests = bool(getattr(context, "can_approve_requests", False))
    can_access_workflows = bool(getattr(context, "can_access_workflows", False))
    can_direct_apply = bool(getattr(context, "can_direct_apply", False))
    is_admin = bool(getattr(context, "is_admin", False))
    has_admin_rights = bool(getattr(context, "has_admin_rights", False))
    role_override = str(getattr(context, "role_override", "") or "")
    try:
        approval_level = int(getattr(context, "approval_level", 0) or 0)
    except Exception:
        approval_level = 0
    user_display_name = display_name_for_principal(context.user_principal)
    try:
        user_display_name = repo.get_user_display_name(context.user_principal)
    except Exception:
        user_display_name = display_name_for_principal(context.user_principal)

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

    csrf_token = str(getattr(request.state, "csrf_token", "") or "").strip()
    if not csrf_token:
        session = request.scope.get("session")
        if isinstance(session, dict):
            csrf_token = str(session.get(CSRF_SESSION_KEY, "")).strip()

    payload: dict[str, Any] = {
        "request": request,
        "title": title,
        "active_nav": active_nav,
        "user_principal": context.user_principal,
        "user_display_name": user_display_name,
        "raw_roles": sorted(raw_roles),
        "roles": sorted(roles),
        "can_edit": can_edit,
        "can_report": can_report,
        "can_submit_requests": can_submit_requests,
        "can_approve_requests": can_approve_requests,
        "can_access_workflows": can_access_workflows,
        "can_direct_apply": can_direct_apply,
        "is_admin": is_admin,
        "has_admin_rights": has_admin_rights,
        "approval_level": approval_level,
        "approval_level_min": MIN_APPROVAL_LEVEL,
        "approval_level_max": MAX_APPROVAL_LEVEL,
        "change_approval_level_min": MIN_CHANGE_APPROVAL_LEVEL,
        "role_approval_level_options": list(range(MIN_APPROVAL_LEVEL, MAX_APPROVAL_LEVEL + 1)),
        "change_approval_level_options": list(range(MIN_CHANGE_APPROVAL_LEVEL, MAX_APPROVAL_LEVEL + 1)),
        "testing_role_override": role_override,
        "testing_role_override_enabled": bool(testing_override_allowed),
        "testing_role_options": role_options,
        "fq_schema": config_fq_schema,
        "use_local_db": config_use_local_db,
        "local_db_path": config_local_db_path,
        "locked_mode": config_locked_mode,
        "csrf_token": csrf_token,
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
