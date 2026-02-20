from __future__ import annotations

import math
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from vendor_catalog_app.core.security import (
    CHANGE_APPROVAL_LEVELS,
    ROLE_CHOICES,
    change_action_choices,
)
from vendor_catalog_app.web.core.activity import ensure_session_started, log_page_view
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.terms import terms_document
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.admin.common import (
    ADMIN_SECTION_ACCESS,
    ADMIN_SECTION_DEFAULTS,
    ADMIN_SECTION_HELP_INBOX,
    ADMIN_SECTION_OWNERSHIP,
    ADMIN_SECTION_TERMS,
    LOOKUP_TYPE_LABELS,
    _date_value,
    _normalize_admin_section,
    _normalize_as_of_date,
    _normalize_lookup_status,
    _normalize_lookup_type,
)

router = APIRouter(prefix="/admin")

_DEFAULT_PAGE_SIZE = 25
_MAX_PAGE_SIZE = 100


def _normalize_page(raw: str | None) -> int:
    try:
        return max(1, int(str(raw or "1").strip()))
    except Exception:
        return 1


def _normalize_page_size(raw: str | None) -> int:
    try:
        value = int(str(raw or str(_DEFAULT_PAGE_SIZE)).strip())
    except Exception:
        value = _DEFAULT_PAGE_SIZE
    return max(5, min(value, _MAX_PAGE_SIZE))


def _active_flag(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _pager(*, base_path: str, query_params: dict[str, str], page: int, page_size: int, total_count: int, page_key: str = "page") -> dict[str, object]:
    total_pages = max(1, int(math.ceil(float(total_count) / float(page_size)))) if total_count > 0 else 1
    page_value = max(1, min(page, total_pages))
    offset = (page_value - 1) * page_size
    start_row = offset + 1 if total_count > 0 else 0
    end_row = min(total_count, offset + page_size)

    def _url_for(target_page: int) -> str:
        payload = dict(query_params)
        payload[page_key] = str(target_page)
        return f"{base_path}?{urlencode(payload)}"

    return {
        "page": page_value,
        "page_size": page_size,
        "total_count": int(total_count),
        "total_pages": total_pages,
        "offset": offset,
        "start_row": start_row,
        "end_row": end_row,
        "prev_url": _url_for(page_value - 1) if page_value > 1 else "",
        "next_url": _url_for(page_value + 1) if page_value < total_pages else "",
    }


def _admin_state(request: Request, page_name: str):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, page_name)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return repo, user, RedirectResponse(url="/dashboard", status_code=303)
    return repo, user, None


def _role_definitions(repo) -> list[dict[str, object]]:
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

    role_rows: list[dict[str, object]] = []
    for row in role_definitions.to_dict("records"):
        role_code = str(row.get("role_code") or "").strip()
        if not role_code:
            continue
        actions = sorted(set(permission_map.get(role_code, [])))
        role_rows.append(
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
    role_rows.sort(key=lambda item: (str(item.get("role_name") or "").lower(), str(item.get("role_code") or "").lower()))
    return role_rows


def _render(request: Request, user, template_name: str, title: str, extra: dict[str, object]):
    context = base_template_context(
        request=request,
        context=user,
        title=title,
        active_nav="admin",
        extra=extra,
    )
    return request.app.state.templates.TemplateResponse(request, template_name, context)


@router.get("")
def admin(request: Request):
    section = _normalize_admin_section(request.query_params.get("section"))
    if section == ADMIN_SECTION_DEFAULTS:
        return admin_defaults(request)
    if section == ADMIN_SECTION_OWNERSHIP:
        return admin_ownership(request)
    if section == ADMIN_SECTION_HELP_INBOX:
        return admin_help_inbox(request)
    if section == ADMIN_SECTION_TERMS:
        return admin_terms(request)
    return admin_access(request)


@router.get("/access")
def admin_access(request: Request):
    repo, user, redirect = _admin_state(request, "Admin Access")
    if redirect is not None:
        return redirect

    search_query = str(request.query_params.get("q") or "").strip()
    selected_lob_filter = str(request.query_params.get("lob_filter") or "all").strip()
    if not selected_lob_filter:
        selected_lob_filter = "all"
    selected_tab = str(request.query_params.get("tab") or "users").strip().lower()
    if selected_tab not in {"users", "groups", "lob", "roles"}:
        selected_tab = "users"
    page_size = _normalize_page_size(request.query_params.get("page_size"))
    role_page = _normalize_page(request.query_params.get("role_page"))
    scope_page = _normalize_page(request.query_params.get("scope_page"))
    group_page = _normalize_page(request.query_params.get("group_page"))

    role_base_params = {
        "q": search_query,
        "tab": selected_tab,
        "page_size": str(page_size),
        "scope_page": str(scope_page),
        "group_page": str(group_page),
    }
    scope_base_params = {
        "tab": selected_tab,
        "lob_filter": selected_lob_filter,
        "page_size": str(page_size),
        "role_page": str(role_page),
        "group_page": str(group_page),
    }
    group_base_params = {
        "q": search_query,
        "tab": selected_tab,
        "page_size": str(page_size),
        "role_page": str(role_page),
        "scope_page": str(scope_page),
    }

    role_total = repo.count_role_grants(query=search_query)
    role_pager = _pager(
        base_path="/admin/access",
        query_params=role_base_params,
        page=role_page,
        page_size=page_size,
        total_count=role_total,
        page_key="role_page",
    )
    role_rows = repo.list_role_grants(
        query=search_query,
        limit=int(role_pager["page_size"]),
        offset=int(role_pager["offset"]),
    ).to_dict("records")

    scope_org_filter = "" if selected_lob_filter.lower() == "all" else selected_lob_filter
    scope_total = repo.count_scope_grants(org_id=scope_org_filter)
    scope_pager = _pager(
        base_path="/admin/access",
        query_params=scope_base_params,
        page=scope_page,
        page_size=page_size,
        total_count=scope_total,
        page_key="scope_page",
    )
    scope_rows = repo.list_scope_grants(
        org_id=scope_org_filter,
        limit=int(scope_pager["page_size"]),
        offset=int(scope_pager["offset"]),
    ).to_dict("records")

    group_total = repo.count_group_role_grants(query=search_query)
    group_pager = _pager(
        base_path="/admin/access",
        query_params=group_base_params,
        page=group_page,
        page_size=page_size,
        total_count=group_total,
        page_key="group_page",
    )
    group_role_rows = repo.list_group_role_grants(
        query=search_query,
        limit=int(group_pager["page_size"]),
        offset=int(group_pager["offset"]),
    ).to_dict("records")

    role_definitions = _role_definitions(repo)
    known_roles = repo.list_known_roles() or list(ROLE_CHOICES)
    group_options: list[dict[str, object]] = []
    drawer_user_options: list[dict[str, object]] = []
    lob_options = [str(item).strip() for item in list(repo.available_orgs() or []) if str(item).strip() and str(item).strip().lower() != "all"]
    user_scope_map: dict[str, list[str]] = {}
    user_scope_level_map: dict[str, str] = {}
    scope_priority = {"none": 0, "read": 1, "edit": 2, "full": 3}
    for row in role_rows:
        user_principal = str(row.get("user_principal") or "").strip()
        if not user_principal or user_principal in user_scope_map:
            continue
        scope_frame = repo.list_scope_grants(user_principal=user_principal, limit=250, offset=0)
        if scope_frame.empty:
            user_scope_map[user_principal] = []
            user_scope_level_map[user_principal] = "edit"
            continue
        active_rows = [
            item
            for item in scope_frame.to_dict("records")
            if _active_flag(item.get("active_flag")) and str(item.get("org_id") or "").strip()
        ]
        user_scope_map[user_principal] = sorted({str(item.get("org_id") or "").strip() for item in active_rows})
        best_scope = "edit"
        best_score = -1
        for item in active_rows:
            scope_level = str(item.get("scope_level") or "").strip().lower()
            score = scope_priority.get(scope_level, -1)
            if score > best_score:
                best_score = score
                best_scope = scope_level
        user_scope_level_map[user_principal] = best_scope

    return _render(
        request,
        user,
        "admin/access.html",
        "Admin Access",
        {
            "admin_active_page": ADMIN_SECTION_ACCESS,
            "search_query": search_query,
            "selected_access_tab": selected_tab,
            "selected_lob_filter": selected_lob_filter,
            "page_size": page_size,
            "role_rows": role_rows,
            "scope_rows": scope_rows,
            "group_role_rows": group_role_rows,
            "role_pager": role_pager,
            "scope_pager": scope_pager,
            "group_pager": group_pager,
            "grantable_roles": known_roles,
            "role_definitions": role_definitions,
            "group_options": group_options,
            "drawer_user_options": drawer_user_options,
            "lob_options": lob_options,
            "user_scope_map": user_scope_map,
            "user_scope_level_map": user_scope_level_map,
            "role_code_options": known_roles,
            "change_actions": list(change_action_choices()),
        },
    )


@router.get("/help-inbox")
def admin_help_inbox(request: Request):
    repo, user, redirect = _admin_state(request, "Admin Help Inbox")
    if redirect is not None:
        return redirect

    page_size = _normalize_page_size(request.query_params.get("page_size"))
    help_feedback_rows = repo.list_help_feedback(limit=page_size, offset=0).to_dict("records")
    help_issue_rows = repo.list_help_issues(limit=page_size, offset=0).to_dict("records")

    return _render(
        request,
        user,
        "admin/help_inbox.html",
        "Admin Help Inbox",
        {
            "admin_active_page": ADMIN_SECTION_HELP_INBOX,
            "help_feedback_rows": help_feedback_rows,
            "help_issue_rows": help_issue_rows,
            "page_size": page_size,
        },
    )


@router.get("/users/search")
def admin_user_search(request: Request, q: str = "", limit: int = 20):
    repo, user, redirect = _admin_state(request, "Admin User Search")
    if redirect is not None:
        return JSONResponse({"items": []}, status_code=403)
    rows = repo.search_user_directory(q=q, limit=max(1, min(int(limit or 20), 20))).to_dict("records")
    return JSONResponse({"items": rows})


@router.get("/groups/search")
def admin_group_search(request: Request, q: str = "", limit: int = 20):
    repo, user, redirect = _admin_state(request, "Admin Group Search")
    if redirect is not None:
        return JSONResponse({"items": []}, status_code=403)
    rows = repo.search_group_principals(q=q, limit=max(1, min(int(limit or 20), 20))).to_dict("records")
    return JSONResponse({"items": rows})


@router.get("/users")
def admin_user_lookup_redirect(request: Request, principal: str = ""):
    candidate = str(principal or "").strip()
    if not candidate:
        return RedirectResponse(url="/admin/access", status_code=303)
    return RedirectResponse(url=f"/admin/users/{candidate}", status_code=303)


@router.get("/groups")
def admin_group_lookup_redirect(request: Request, principal: str = ""):
    candidate = str(principal or "").strip()
    if not candidate:
        return RedirectResponse(url="/admin/access", status_code=303)
    return RedirectResponse(url=f"/admin/groups/{candidate}", status_code=303)


@router.get("/users/{principal}")
def admin_user_detail(request: Request, principal: str):
    repo, user, redirect = _admin_state(request, "Admin User Detail")
    if redirect is not None:
        return redirect

    page_size = _normalize_page_size(request.query_params.get("page_size"))
    role_page = _normalize_page(request.query_params.get("role_page"))
    scope_page = _normalize_page(request.query_params.get("scope_page"))
    normalized_principal = repo.resolve_user_login_identifier(principal) or str(principal or "").strip()

    profile = repo.get_user_directory_profile(normalized_principal) or {}
    display_name = str(profile.get("display_name") or "").strip()
    if not display_name:
        display_name = normalized_principal

    role_total = repo.count_role_grants(user_principal=normalized_principal)
    role_pager = _pager(
        base_path=f"/admin/users/{normalized_principal}",
        query_params={"page_size": str(page_size), "scope_page": str(scope_page)},
        page=role_page,
        page_size=page_size,
        total_count=role_total,
        page_key="role_page",
    )
    role_rows = repo.list_role_grants(
        user_principal=normalized_principal,
        limit=int(role_pager["page_size"]),
        offset=int(role_pager["offset"]),
    ).to_dict("records")

    scope_total = repo.count_scope_grants(user_principal=normalized_principal)
    scope_pager = _pager(
        base_path=f"/admin/users/{normalized_principal}",
        query_params={"page_size": str(page_size), "role_page": str(role_page)},
        page=scope_page,
        page_size=page_size,
        total_count=scope_total,
        page_key="scope_page",
    )
    scope_rows = repo.list_scope_grants(
        user_principal=normalized_principal,
        limit=int(scope_pager["page_size"]),
        offset=int(scope_pager["offset"]),
    ).to_dict("records")

    active_roles = [str(row.get("role_code") or "") for row in role_rows if _active_flag(row.get("active_flag"))]
    active_scopes = [str(row.get("scope_level") or "") for row in scope_rows if _active_flag(row.get("active_flag"))]

    return _render(
        request,
        user,
        "admin/user_detail.html",
        "Admin User Access",
        {
            "admin_active_page": ADMIN_SECTION_ACCESS,
            "subject_principal": normalized_principal,
            "subject_display_name": display_name,
            "subject_profile": profile,
            "grantable_roles": repo.list_known_roles() or list(ROLE_CHOICES),
            "role_rows": role_rows,
            "scope_rows": scope_rows,
            "role_pager": role_pager,
            "scope_pager": scope_pager,
            "effective_role_summary": ", ".join(sorted(set(active_roles))) if active_roles else "No active direct role grants",
            "effective_scope_summary": ", ".join(sorted(set(active_scopes))) if active_scopes else "No active Line of Business access grants",
        },
    )


@router.get("/groups/{principal}")
def admin_group_detail(request: Request, principal: str):
    repo, user, redirect = _admin_state(request, "Admin Group Detail")
    if redirect is not None:
        return redirect

    page_size = _normalize_page_size(request.query_params.get("page_size"))
    page = _normalize_page(request.query_params.get("page"))
    group_principal = repo.normalize_group_principal(principal)

    total_count = repo.count_group_role_grants(group_principal=group_principal)
    pager = _pager(
        base_path=f"/admin/groups/{group_principal}",
        query_params={"page_size": str(page_size)},
        page=page,
        page_size=page_size,
        total_count=total_count,
        page_key="page",
    )
    role_rows = repo.list_group_role_grants(
        group_principal=group_principal,
        limit=int(pager["page_size"]),
        offset=int(pager["offset"]),
    ).to_dict("records")

    return _render(
        request,
        user,
        "admin/group_detail.html",
        "Admin Group Access",
        {
            "admin_active_page": ADMIN_SECTION_ACCESS,
            "group_principal": group_principal,
            "group_role_rows": role_rows,
            "group_pager": pager,
            "grantable_roles": repo.list_known_roles() or list(ROLE_CHOICES),
        },
    )


@router.get("/roles")
def admin_roles(request: Request):
    repo, user, redirect = _admin_state(request, "Admin Roles")
    if redirect is not None:
        return redirect

    page_size = _normalize_page_size(request.query_params.get("page_size"))
    page = _normalize_page(request.query_params.get("page"))
    q = str(request.query_params.get("q") or "").strip().lower()

    role_rows = _role_definitions(repo)
    if q:
        role_rows = [
            row
            for row in role_rows
            if q in str(row.get("role_code") or "").lower()
            or q in str(row.get("role_name") or "").lower()
            or q in str(row.get("description") or "").lower()
        ]

    total_count = len(role_rows)
    pager = _pager(
        base_path="/admin/roles",
        query_params={"q": q, "page_size": str(page_size)},
        page=page,
        page_size=page_size,
        total_count=total_count,
        page_key="page",
    )
    start = int(pager["offset"])
    end = start + int(pager["page_size"])
    page_rows = role_rows[start:end]

    return _render(
        request,
        user,
        "admin/roles.html",
        "Admin Roles",
        {
            "admin_active_page": ADMIN_SECTION_ACCESS,
            "roles_query": q,
            "roles_pager": pager,
            "role_definitions": page_rows,
            "role_code_options": repo.list_known_roles() or list(ROLE_CHOICES),
            "change_actions": list(change_action_choices()),
            "role_approval_level_options": list(CHANGE_APPROVAL_LEVELS.keys()),
        },
    )


@router.get("/roles/{role_code}")
def admin_role_detail(request: Request, role_code: str):
    repo, user, redirect = _admin_state(request, "Admin Role Detail")
    if redirect is not None:
        return redirect

    normalized_role = str(role_code or "").strip().lower()
    definitions = _role_definitions(repo)
    role_row = next((row for row in definitions if str(row.get("role_code") or "").strip().lower() == normalized_role), None)
    if role_row is None:
        add_flash(request, f"Role '{normalized_role}' was not found.", "error")
        return RedirectResponse(url="/admin/roles", status_code=303)

    page_size = _normalize_page_size(request.query_params.get("page_size"))
    user_page = _normalize_page(request.query_params.get("user_page"))
    group_page = _normalize_page(request.query_params.get("group_page"))

    user_total = repo.count_role_grants(role_code=normalized_role)
    user_pager = _pager(
        base_path=f"/admin/roles/{normalized_role}",
        query_params={"page_size": str(page_size), "group_page": str(group_page)},
        page=user_page,
        page_size=page_size,
        total_count=user_total,
        page_key="user_page",
    )
    role_user_rows = repo.list_role_grants(
        role_code=normalized_role,
        limit=int(user_pager["page_size"]),
        offset=int(user_pager["offset"]),
    ).to_dict("records")

    group_total = repo.count_group_role_grants(role_code=normalized_role)
    group_pager = _pager(
        base_path=f"/admin/roles/{normalized_role}",
        query_params={"page_size": str(page_size), "user_page": str(user_page)},
        page=group_page,
        page_size=page_size,
        total_count=group_total,
        page_key="group_page",
    )
    role_group_rows = repo.list_group_role_grants(
        role_code=normalized_role,
        limit=int(group_pager["page_size"]),
        offset=int(group_pager["offset"]),
    ).to_dict("records")

    return _render(
        request,
        user,
        "admin/role_detail.html",
        "Admin Role Detail",
        {
            "admin_active_page": ADMIN_SECTION_ACCESS,
            "role_row": role_row,
            "role_user_rows": role_user_rows,
            "role_group_rows": role_group_rows,
            "user_pager": user_pager,
            "group_pager": group_pager,
            "grantable_roles": repo.list_known_roles() or list(ROLE_CHOICES),
        },
    )


@router.get("/ownership")
def admin_ownership(request: Request):
    repo, user, redirect = _admin_state(request, "Admin Ownership")
    if redirect is not None:
        return redirect

    selected_owner_source = str(request.query_params.get("source_owner") or "").strip()
    page_size = _normalize_page_size(request.query_params.get("page_size"))
    page = _normalize_page(request.query_params.get("page"))

    ownership_rows: list[dict[str, object]] = []
    if selected_owner_source:
        try:
            ownership_rows = repo.list_owner_reassignment_assignments(selected_owner_source)
        except Exception as exc:
            add_flash(request, f"Could not load ownership assignments: {exc}", "error")
            ownership_rows = []

    pager = _pager(
        base_path="/admin/ownership",
        query_params={"source_owner": selected_owner_source, "page_size": str(page_size)},
        page=page,
        page_size=page_size,
        total_count=len(ownership_rows),
        page_key="page",
    )
    start = int(pager["offset"])
    end = start + int(pager["page_size"])
    page_rows = ownership_rows[start:end]

    return _render(
        request,
        user,
        "admin/ownership.html",
        "Admin Ownership Reassignment",
        {
            "admin_active_page": ADMIN_SECTION_OWNERSHIP,
            "selected_owner_source": selected_owner_source,
            "ownership_rows": page_rows,
            "ownership_pager": pager,
        },
    )


@router.get("/defaults")
def admin_defaults(request: Request):
    repo, user, redirect = _admin_state(request, "Admin Defaults")
    if redirect is not None:
        return redirect

    selected_lookup_type = _normalize_lookup_type(request.query_params.get("lookup_type"))
    selected_lookup_status = _normalize_lookup_status(request.query_params.get("status"))
    selected_as_of = _normalize_as_of_date(request.query_params.get("as_of"))
    page_size = _normalize_page_size(request.query_params.get("page_size"))
    page = _normalize_page(request.query_params.get("page"))

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

    pager = _pager(
        base_path="/admin/defaults",
        query_params={
            "lookup_type": selected_lookup_type,
            "status": selected_lookup_status,
            "as_of": selected_as_of,
            "page_size": str(page_size),
        },
        page=page,
        page_size=page_size,
        total_count=len(selected_lookup_rows),
        page_key="page",
    )
    start = int(pager["offset"])
    end = start + int(pager["page_size"])
    page_rows = selected_lookup_rows[start:end]

    active_rows_for_date = repo.list_lookup_option_versions(
        selected_lookup_type,
        as_of_ts=selected_as_of,
        status_filter="active",
    )
    next_sort_order = max(1, len(active_rows_for_date) + 1)

    return _render(
        request,
        user,
        "admin/defaults.html",
        "Admin Defaults Catalog",
        {
            "admin_active_page": ADMIN_SECTION_DEFAULTS,
            "lookup_type_options": list(LOOKUP_TYPE_LABELS.keys()),
            "lookup_type_labels": LOOKUP_TYPE_LABELS,
            "selected_lookup_type": selected_lookup_type,
            "selected_lookup_status": selected_lookup_status,
            "selected_as_of": selected_as_of,
            "selected_lookup_rows": page_rows,
            "next_lookup_sort_order": next_sort_order,
            "defaults_pager": pager,
        },
    )


@router.get("/terms")
def admin_terms(request: Request):
    repo, user, redirect = _admin_state(request, "Admin User Agreement")
    if redirect is not None:
        return redirect

    terms_payload = terms_document(repo=repo)
    return _render(
        request,
        user,
        "admin/terms.html",
        "Admin User Agreement",
        {
            "admin_active_page": ADMIN_SECTION_TERMS,
            "terms_title": str(terms_payload.get("title") or ""),
            "terms_effective_date": str(terms_payload.get("effective_date") or ""),
            "terms_document_text": str(terms_payload.get("document_text") or ""),
            "terms_version": str(terms_payload.get("version") or ""),
        },
    )
