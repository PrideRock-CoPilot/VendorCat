from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.core.security import (
    CHANGE_APPROVAL_LEVELS,
    ROLE_CHOICES,
    change_action_choices,
)
from vendor_catalog_app.web.core.activity import ensure_session_started, log_page_view
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.admin.common import (
    ADMIN_SECTION_OWNERSHIP,
    LOOKUP_TYPE_LABELS,
    _date_value,
    _normalize_admin_section,
    _normalize_as_of_date,
    _normalize_lookup_status,
    _normalize_lookup_type,
)

router = APIRouter(prefix="/admin")


@router.get("")
def admin(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Admin Permissions")

    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    admin_section = _normalize_admin_section(request.query_params.get("section"))
    selected_lookup_type = _normalize_lookup_type(request.query_params.get("lookup_type"))
    selected_lookup_status = _normalize_lookup_status(request.query_params.get("status"))
    selected_as_of = _normalize_as_of_date(request.query_params.get("as_of"))

    role_definitions = repo.list_role_definitions()
    role_permissions = repo.list_role_permissions()
    permission_map: dict[str, list[str]] = {}
    for row in role_permissions.to_dict("records"):
        role_code = str(row.get("role_code") or "").strip()
        action_code = str(row.get("action_code") or "").strip().lower()
        if not role_code or action_code not in CHANGE_APPROVAL_LEVELS:
            continue
        if not bool(row.get("active_flag", True)):
            continue
        permission_map.setdefault(role_code, []).append(action_code)

    role_def_rows = []
    for row in role_definitions.to_dict("records"):
        role_code = str(row.get("role_code") or "").strip()
        if not role_code:
            continue
        actions = sorted(set(permission_map.get(role_code, [])))
        role_def_rows.append(
            {
                "role_code": role_code,
                "role_name": str(row.get("role_name") or role_code),
                "description": str(row.get("description") or ""),
                "approval_level": int(row.get("approval_level") or 0),
                "can_edit": bool(row.get("can_edit")),
                "can_report": bool(row.get("can_report")),
                "can_direct_apply": bool(row.get("can_direct_apply")),
                "active_flag": bool(row.get("active_flag", True)),
                "actions": actions,
                "actions_summary": ", ".join(actions) if actions else "(none)",
            }
        )

    known_roles = repo.list_known_roles() or list(ROLE_CHOICES)
    selected_lookup_rows_raw = repo.list_lookup_option_versions(
        selected_lookup_type,
        as_of_ts=selected_as_of,
        status_filter=selected_lookup_status,
    ).to_dict("records")
    selected_owner_source = str(request.query_params.get("source_owner") or "").strip()
    ownership_rows: list[dict[str, object]] = []
    if admin_section == ADMIN_SECTION_OWNERSHIP and selected_owner_source:
        try:
            ownership_rows = repo.list_owner_reassignment_assignments(selected_owner_source)
        except Exception as exc:
            add_flash(request, f"Could not load ownership assignments: {exc}", "error")
            ownership_rows = []
    selected_lookup_rows: list[dict[str, object]] = []
    for row in selected_lookup_rows_raw:
        try:
            sort_order = int(row.get("sort_order") or 0)
        except Exception:
            sort_order = 0
        selected_lookup_rows.append(
            {
                "option_id": str(row.get("option_id") or ""),
                "lookup_type": str(row.get("lookup_type") or selected_lookup_type),
                "option_code": str(row.get("option_code") or ""),
                "option_label": str(row.get("option_label") or ""),
                "sort_order": sort_order,
                "status": str(row.get("status") or "active"),
                "valid_from_ts": _date_value(row.get("valid_from_ts")),
                "valid_to_ts": _date_value(row.get("valid_to_ts")),
            }
        )

    active_rows_for_date = repo.list_lookup_option_versions(
        selected_lookup_type,
        as_of_ts=selected_as_of,
        status_filter="active",
    )
    next_sort_order = max(1, len(active_rows_for_date) + 1)

    context = base_template_context(
        request=request,
        context=user,
        title="Admin Portal",
        active_nav="admin",
        extra={
            "admin_section": admin_section,
            "grantable_roles": known_roles,
            "role_rows": repo.list_role_grants().to_dict("records"),
            "group_role_rows": repo.list_group_role_grants().to_dict("records"),
            "scope_rows": repo.list_scope_grants().to_dict("records"),
            "user_options": repo.search_user_directory(q="", limit=300).to_dict("records"),
            "role_definitions": role_def_rows,
            "role_code_options": known_roles,
            "change_actions": list(change_action_choices()),
            "lookup_type_options": list(LOOKUP_TYPE_LABELS.keys()),
            "lookup_type_labels": LOOKUP_TYPE_LABELS,
            "selected_lookup_type": selected_lookup_type,
            "selected_lookup_status": selected_lookup_status,
            "selected_as_of": selected_as_of,
            "selected_lookup_rows": selected_lookup_rows,
            "next_lookup_sort_order": next_sort_order,
            "selected_owner_source": selected_owner_source,
            "ownership_rows": ownership_rows,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "admin.html", context)

