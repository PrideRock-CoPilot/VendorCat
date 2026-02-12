from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.repository import (
    LOOKUP_TYPE_ASSIGNMENT_TYPE,
    LOOKUP_TYPE_CONTACT_TYPE,
    LOOKUP_TYPE_DOC_SOURCE,
    LOOKUP_TYPE_DOC_TAG,
    LOOKUP_TYPE_OFFERING_LOB,
    LOOKUP_TYPE_OFFERING_SERVICE_TYPE,
    LOOKUP_TYPE_OFFERING_TYPE,
    LOOKUP_TYPE_OWNER_ROLE,
    LOOKUP_TYPE_PROJECT_TYPE,
    LOOKUP_TYPE_WORKFLOW_STATUS,
)
from vendor_catalog_app.security import (
    CHANGE_APPROVAL_LEVELS,
    MAX_APPROVAL_LEVEL,
    MIN_APPROVAL_LEVEL,
    ROLE_CHOICES,
    change_action_choices,
)
from vendor_catalog_app.web.flash import add_flash
from vendor_catalog_app.web.services import (
    ADMIN_ROLE_OVERRIDE_SESSION_KEY,
    base_template_context,
    ensure_session_started,
    get_repo,
    get_user_context,
    log_page_view,
    testing_role_override_enabled,
)

LOGGER = logging.getLogger(__name__)


router = APIRouter(prefix="/admin")
ROLE_CODE_PATTERN = re.compile(r"^[a-z0-9_][a-z0-9_-]{2,63}$")
LOOKUP_CODE_PATTERN = re.compile(r"^[a-z0-9_][a-z0-9_-]{1,63}$")
ADMIN_SECTION_ACCESS = "access"
ADMIN_SECTION_DEFAULTS = "defaults"
LOOKUP_STATUS_OPTIONS = {"all", "active", "historical", "future"}
LOOKUP_TYPE_LABELS = {
    LOOKUP_TYPE_DOC_SOURCE: "Document Sources",
    LOOKUP_TYPE_DOC_TAG: "Document Tags",
    LOOKUP_TYPE_OWNER_ROLE: "Owner Roles",
    LOOKUP_TYPE_ASSIGNMENT_TYPE: "Assignment Types",
    LOOKUP_TYPE_CONTACT_TYPE: "Contact Types",
    LOOKUP_TYPE_PROJECT_TYPE: "Project Types",
    LOOKUP_TYPE_OFFERING_TYPE: "Offering Types",
    LOOKUP_TYPE_OFFERING_LOB: "Offering LOB",
    LOOKUP_TYPE_OFFERING_SERVICE_TYPE: "Offering Service Types",
    LOOKUP_TYPE_WORKFLOW_STATUS: "Workflow Statuses",
}


def _admin_redirect_url(
    *,
    section: str,
    lookup_type: str | None = None,
    lookup_status: str | None = None,
    as_of: str | None = None,
) -> str:
    if section == ADMIN_SECTION_DEFAULTS:
        selected_lookup = lookup_type if lookup_type in LOOKUP_TYPE_LABELS else LOOKUP_TYPE_DOC_SOURCE
        selected_status = lookup_status if lookup_status in LOOKUP_STATUS_OPTIONS else "active"
        selected_as_of = str(as_of or "").strip() or datetime.now(timezone.utc).date().isoformat()
        return (
            f"/admin?section={ADMIN_SECTION_DEFAULTS}&lookup_type={selected_lookup}"
            f"&status={selected_status}&as_of={selected_as_of}"
        )
    return f"/admin?section={ADMIN_SECTION_ACCESS}"


def _normalize_admin_section(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    if value in {ADMIN_SECTION_ACCESS, ADMIN_SECTION_DEFAULTS}:
        return value
    return ADMIN_SECTION_ACCESS


def _normalize_lookup_type(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    if value in LOOKUP_TYPE_LABELS:
        return value
    return LOOKUP_TYPE_DOC_SOURCE


def _slug_lookup_code(value: str) -> str:
    normalized = re.sub(r"\s+", "_", str(value or "").strip().lower())
    normalized = re.sub(r"[^a-z0-9_-]", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def _normalize_lookup_status(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    if value in LOOKUP_STATUS_OPTIONS:
        return value
    return "active"


def _normalize_as_of_date(raw: str | None) -> str:
    value = str(raw or "").strip()
    if value:
        try:
            return datetime.fromisoformat(value).date().isoformat()
        except Exception:
            LOGGER.debug("Invalid as_of date '%s'; falling back to current UTC date.", value, exc_info=True)
    return datetime.now(timezone.utc).date().isoformat()


def _date_value(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return raw[:10]


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
        },
    )
    return request.app.state.templates.TemplateResponse(request, "admin.html", context)


@router.post("/grant-role")
async def grant_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    target_user = str(form.get("target_user", "")).strip()
    role_code = str(form.get("role_code", "")).strip().lower()
    if not target_user or not role_code:
        add_flash(request, "User and role are required.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    target_user = repo.resolve_user_login_identifier(target_user) or target_user
    if role_code not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, f"Role `{role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    try:
        repo.grant_role(target_user_principal=target_user, role_code=role_code, granted_by=user.user_principal)
    except Exception as exc:
        add_flash(request, f"Could not grant role: {exc}", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="grant_role",
        payload={"target_user": target_user, "role_code": role_code},
    )
    add_flash(request, "Role grant recorded.", "success")
    return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)


@router.post("/change-role")
async def change_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    target_user = str(form.get("target_user", "")).strip()
    current_role_code = str(form.get("current_role_code", "")).strip().lower()
    new_role_code = str(form.get("new_role_code", "")).strip().lower()
    if not target_user or not current_role_code or not new_role_code:
        add_flash(request, "User, current role, and new role are required.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    target_user = repo.resolve_user_login_identifier(target_user) or target_user
    if new_role_code not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, f"Role `{new_role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if current_role_code == new_role_code:
        add_flash(request, "Role is already set to that value.", "success")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    try:
        repo.change_role_grant(
            target_user_principal=target_user,
            current_role_code=current_role_code,
            new_role_code=new_role_code,
            granted_by=user.user_principal,
        )
    except Exception as exc:
        add_flash(request, f"Could not change role: {exc}", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="change_role",
        payload={
            "target_user": target_user,
            "current_role_code": current_role_code,
            "new_role_code": new_role_code,
        },
    )
    add_flash(request, "Role updated.", "success")
    return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)


@router.post("/grant-group-role")
async def grant_group_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    target_group = str(form.get("target_group", "")).strip()
    role_code = str(form.get("role_code", "")).strip().lower()
    if not target_group or not role_code:
        add_flash(request, "Group and role are required.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if role_code not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, f"Role `{role_code}` is not defined. Create it in Role Catalog first.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    normalized_group = repo.normalize_group_principal(target_group)
    if not normalized_group:
        add_flash(request, "Group principal is invalid. Use a valid group identifier.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    try:
        repo.grant_group_role(group_principal=normalized_group, role_code=role_code, granted_by=user.user_principal)
    except Exception as exc:
        add_flash(request, f"Could not grant group role: {exc}", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="grant_group_role",
        payload={"target_group": normalized_group, "role_code": role_code},
    )
    add_flash(request, "Group role grant recorded.", "success")
    return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)


@router.post("/grant-scope")
async def grant_scope(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    target_user = str(form.get("target_user", "")).strip()
    org_id = str(form.get("org_id", "")).strip()
    scope_level = str(form.get("scope_level", "")).strip()
    if not target_user or not org_id or not scope_level:
        add_flash(request, "User, org, and scope level are required.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    repo.grant_org_scope(
        target_user_principal=target_user,
        org_id=org_id,
        scope_level=scope_level,
        granted_by=user.user_principal,
    )
    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="grant_scope",
        payload={"target_user": target_user, "org_id": org_id, "scope_level": scope_level},
    )
    add_flash(request, "Org scope grant recorded.", "success")
    return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)


@router.post("/roles/save")
async def save_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    role_code = str(form.get("role_code", "")).strip().lower()
    role_name = str(form.get("role_name", "")).strip()
    description = str(form.get("description", "")).strip()
    approval_level_raw = str(form.get("approval_level", "0")).strip()

    if not ROLE_CODE_PATTERN.match(role_code):
        add_flash(
            request,
            "Role code must be 3-64 chars and use lowercase letters, numbers, _ or - (start with letter/number/_).",
            "error",
        )
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    if not role_name:
        add_flash(request, "Role name is required.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    try:
        approval_level = max(MIN_APPROVAL_LEVEL, min(int(approval_level_raw), MAX_APPROVAL_LEVEL))
    except Exception:
        add_flash(
            request,
            f"Approval level must be a number between {MIN_APPROVAL_LEVEL} and {MAX_APPROVAL_LEVEL}.",
            "error",
        )
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)

    can_edit = str(form.get("can_edit", "")).strip().lower() == "on"
    can_report = str(form.get("can_report", "")).strip().lower() == "on"
    can_direct_apply = str(form.get("can_direct_apply", "")).strip().lower() == "on"

    action_choices = list(change_action_choices())
    selected_actions = {
        action for action in action_choices if str(form.get(f"perm_{action}", "")).strip().lower() == "on"
    }

    try:
        repo.save_role_definition(
            role_code=role_code,
            role_name=role_name,
            description=description or None,
            approval_level=approval_level,
            can_edit=can_edit,
            can_report=can_report,
            can_direct_apply=can_direct_apply,
            updated_by=user.user_principal,
        )
        repo.replace_role_permissions(role_code=role_code, action_codes=selected_actions, updated_by=user.user_principal)
    except Exception as exc:
        add_flash(request, f"Could not save role definition: {exc}", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)
    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="save_role_definition",
        payload={
            "role_code": role_code,
            "approval_level": approval_level,
            "can_edit": can_edit,
            "can_report": can_report,
            "can_direct_apply": can_direct_apply,
            "permission_count": len(selected_actions),
        },
    )
    add_flash(request, f"Role `{role_code}` saved.", "success")
    return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_ACCESS), status_code=303)


@router.post("/testing-role")
async def set_testing_role(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if not testing_role_override_enabled(user.config):
        add_flash(request, "Testing role override is disabled in this environment.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    return_to = str(form.get("return_to", "/dashboard"))
    safe_return_to = "/dashboard"
    if return_to.startswith("/"):
        safe_return_to = return_to
    selected = str(form.get("role_override", "")).strip()

    if selected and selected not in set(repo.list_known_roles() or ROLE_CHOICES):
        add_flash(request, "Invalid testing role override selected.", "error")
        return RedirectResponse(url=f"{safe_return_to}", status_code=303)

    if selected:
        request.session[ADMIN_ROLE_OVERRIDE_SESSION_KEY] = selected
        add_flash(request, f"Testing role override set to {selected}.", "success")
    else:
        request.session.pop(ADMIN_ROLE_OVERRIDE_SESSION_KEY, None)
        add_flash(request, "Testing role override cleared.", "success")
    return RedirectResponse(url=f"{safe_return_to}", status_code=303)


@router.post("/lookup/save")
async def save_lookup_option(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    lookup_type = _normalize_lookup_type(form.get("lookup_type"))
    lookup_status = _normalize_lookup_status(form.get("lookup_status"))
    as_of = _normalize_as_of_date(form.get("as_of"))
    redirect_url = _admin_redirect_url(
        section=ADMIN_SECTION_DEFAULTS,
        lookup_type=lookup_type,
        lookup_status=lookup_status,
        as_of=as_of,
    )
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=redirect_url, status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    option_code = str(form.get("option_code", "")).strip().lower()
    option_id = str(form.get("option_id", "")).strip() or None
    option_label = str(form.get("option_label", "")).strip()
    sort_order_raw = str(form.get("sort_order", "100")).strip()
    valid_from = str(form.get("valid_from_ts", "")).strip() or as_of
    valid_to = str(form.get("valid_to_ts", "")).strip() or "9999-12-31"

    if lookup_type not in LOOKUP_TYPE_LABELS:
        add_flash(request, "Lookup type is invalid.", "error")
        return RedirectResponse(url=redirect_url, status_code=303)
    if not option_code:
        option_code = _slug_lookup_code(option_label)
        if not option_code:
            add_flash(request, "Label is required for new options.", "error")
            return RedirectResponse(url=redirect_url, status_code=303)

    if not LOOKUP_CODE_PATTERN.match(option_code):
        add_flash(
            request,
            "Lookup code must be 2-64 chars and use lowercase letters, numbers, _ or -.",
            "error",
        )
        return RedirectResponse(url=redirect_url, status_code=303)
    try:
        sort_order = max(0, int(sort_order_raw or "0"))
    except Exception:
        add_flash(request, "Sort order must be a valid number.", "error")
        return RedirectResponse(url=redirect_url, status_code=303)

    try:
        repo.save_lookup_option(
            option_id=option_id,
            lookup_type=lookup_type,
            option_code=option_code,
            option_label=option_label or None,
            sort_order=sort_order,
            valid_from_ts=valid_from,
            valid_to_ts=valid_to,
            updated_by=user.user_principal,
        )
    except Exception as exc:
        add_flash(request, f"Could not save lookup option: {exc}", "error")
        return RedirectResponse(url=redirect_url, status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="save_lookup_option",
        payload={
            "lookup_type": lookup_type,
            "option_code": option_code,
            "valid_from_ts": valid_from,
            "valid_to_ts": valid_to,
        },
    )
    add_flash(request, f"Lookup option saved: {lookup_type}/{option_code}", "success")
    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/lookup/delete")
async def delete_lookup_option(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()
    lookup_type = _normalize_lookup_type(form.get("lookup_type"))
    lookup_status = _normalize_lookup_status(form.get("lookup_status"))
    as_of = _normalize_as_of_date(form.get("as_of"))
    redirect_url = _admin_redirect_url(
        section=ADMIN_SECTION_DEFAULTS,
        lookup_type=lookup_type,
        lookup_status=lookup_status,
        as_of=as_of,
    )
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=redirect_url, status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    option_id = str(form.get("option_id", "")).strip()
    if lookup_type not in LOOKUP_TYPE_LABELS:
        add_flash(request, "Lookup type is invalid.", "error")
        return RedirectResponse(url=redirect_url, status_code=303)
    if not option_id:
        add_flash(request, "Lookup option id is required.", "error")
        return RedirectResponse(url=redirect_url, status_code=303)

    try:
        repo.delete_lookup_option(
            lookup_type=lookup_type,
            option_id=option_id,
            updated_by=user.user_principal,
        )
    except Exception as exc:
        add_flash(request, f"Could not delete lookup option: {exc}", "error")
        return RedirectResponse(url=redirect_url, status_code=303)

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="delete_lookup_option",
        payload={"lookup_type": lookup_type, "option_id": option_id},
    )
    add_flash(request, "Lookup option removed.", "success")
    return RedirectResponse(url=redirect_url, status_code=303)
