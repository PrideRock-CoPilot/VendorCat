from __future__ import annotations

from urllib.parse import quote

import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.core.defaults import DEFAULT_SOURCE_SYSTEM
from vendor_catalog_app.repository import GLOBAL_CHANGE_VENDOR_ID
from vendor_catalog_app.web.core.activity import ensure_session_started, log_page_view
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.vendors.common import (
    _render_vendor_new_form,
    _safe_return_to,
    _write_blocked,
)
from vendor_catalog_app.web.routers.vendors.constants import (
    DEFAULT_VENDOR_FIELDS,
    DEFAULT_VENDOR_PAGE_SIZE,
    DEFAULT_VENDOR_SORT_BY,
    DEFAULT_VENDOR_SORT_DIR,
    LIFECYCLE_STATES,
    RISK_TIERS,
    VENDOR_DEFAULT_RETURN_TO,
    VENDOR_FIELD_SORT_MAP,
    VENDOR_FILTER_ALL,
    VENDOR_GROUP_NONE,
    VENDOR_PAGE_SIZES,
    VENDOR_SETTINGS_KEY,
)
from vendor_catalog_app.web.routers.vendors.pages import (
    _load_visible_fields,
    _merge_vendor360_settings,
    _normalize_lifecycle,
    _normalize_vendor_page,
    _normalize_vendor_sort,
    _vendor_list_url,
)
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/vendors")

@router.get("")
def vendor_list(
    request: Request,
    q: str = "",
    search: str = "",
    status: str = VENDOR_FILTER_ALL,
    owner: str = VENDOR_FILTER_ALL,
    risk: str = VENDOR_FILTER_ALL,
    group: str = VENDOR_GROUP_NONE,
    page: int = 1,
    page_size: int = DEFAULT_VENDOR_PAGE_SIZE,
    sort_by: str = DEFAULT_VENDOR_SORT_BY,
    sort_dir: str = DEFAULT_VENDOR_SORT_DIR,
    show_settings: int = 0,
):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Vendor 360")

    saved_settings = repo.get_user_setting(user.user_principal, VENDOR_SETTINGS_KEY)
    saved_prefs = saved_settings.get("list_prefs", {}) if isinstance(saved_settings, dict) else {}
    qp = request.query_params

    if "q" in qp:
        resolved_q = q.strip()
    elif "search" in qp:
        resolved_q = search.strip()
    else:
        resolved_q = str(saved_prefs.get("q", "")).strip()

    if "status" not in qp and str(saved_prefs.get("status", "")).strip():
        status = str(saved_prefs.get("status", VENDOR_FILTER_ALL))
    if status not in [VENDOR_FILTER_ALL] + LIFECYCLE_STATES:
        status = VENDOR_FILTER_ALL

    if "owner" not in qp and str(saved_prefs.get("owner", "")).strip():
        owner = str(saved_prefs.get("owner", VENDOR_FILTER_ALL))
    if owner != VENDOR_FILTER_ALL and owner not in repo.available_orgs():
        owner = VENDOR_FILTER_ALL

    if "risk" not in qp and str(saved_prefs.get("risk", "")).strip():
        risk = str(saved_prefs.get("risk", VENDOR_FILTER_ALL))
    if risk != VENDOR_FILTER_ALL and risk not in RISK_TIERS:
        risk = VENDOR_FILTER_ALL

    if "group" not in qp and str(saved_prefs.get("group", "")).strip():
        group = str(saved_prefs.get("group", VENDOR_GROUP_NONE))

    if "sort_by" not in qp and str(saved_prefs.get("sort_by", "")).strip():
        sort_by = str(saved_prefs.get("sort_by", DEFAULT_VENDOR_SORT_BY))
    if "sort_dir" not in qp and str(saved_prefs.get("sort_dir", "")).strip():
        sort_dir = str(saved_prefs.get("sort_dir", DEFAULT_VENDOR_SORT_DIR))
    sort_by, sort_dir = _normalize_vendor_sort(sort_by, sort_dir)

    if "page_size" not in qp and saved_prefs.get("page_size"):
        try:
            page_size = int(saved_prefs.get("page_size"))
        except Exception:
            page_size = DEFAULT_VENDOR_PAGE_SIZE
    page, page_size = _normalize_vendor_page(page, page_size)

    vendors_df, total_rows = repo.list_vendors_page(
        search_text=resolved_q,
        lifecycle_state=status,
        owner_org_id=owner,
        risk_tier=risk,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    vendors_df = vendors_df.reset_index(drop=True)

    available_fields = vendors_df.columns.tolist() if not vendors_df.empty else DEFAULT_VENDOR_FIELDS
    visible_fields = _load_visible_fields(repo, user.user_principal, available_fields)

    grouped = pd.DataFrame()
    if group != VENDOR_GROUP_NONE and group in vendors_df.columns and not vendors_df.empty:
        grouped = (
            vendors_df.groupby(group, dropna=False, as_index=False)
            .agg(vendor_count=("vendor_id", "count"))
            .sort_values("vendor_count", ascending=False)
        )

    owner_options = repo.available_orgs()
    risk_options = [VENDOR_FILTER_ALL] + RISK_TIERS

    group_options = [VENDOR_GROUP_NONE] + [
        c for c in ["lifecycle_state", "owner_org_id", "risk_tier", "source_system"] if c in DEFAULT_VENDOR_FIELDS or c in available_fields
    ]
    return_to = _vendor_list_url(
        q=resolved_q,
        status=status,
        owner=owner,
        risk=risk,
        group=group,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
        show_settings=show_settings,
    )

    offering_map: dict[str, list[dict]] = {}
    vendor_ids = vendors_df["vendor_id"].astype(str).tolist() if "vendor_id" in vendors_df.columns else []
    offering_rows = repo.list_vendor_offerings_for_vendors(vendor_ids).to_dict("records")
    for row in offering_rows:
        vid = str(row.get("vendor_id") or "")
        if vid not in offering_map:
            offering_map[vid] = []
        offering_map[vid].append(
            {
                "offering_id": str(row.get("offering_id") or ""),
                "offering_name": str(row.get("offering_name") or row.get("offering_id") or ""),
                "lifecycle_state": str(row.get("lifecycle_state") or ""),
            }
        )

    vendor_rows = vendors_df.to_dict("records")
    for row in vendor_rows:
        vid = str(row.get("vendor_id"))
        row["_vendor_link"] = f"/vendors/{vid}/summary?return_to={quote(return_to, safe='')}"
        row["_offerings_page_link"] = f"/vendors/{vid}/offerings?return_to={quote(return_to, safe='')}"
        row["_offerings"] = []
        for offering in offering_map.get(vid, []):
            entry = dict(offering)
            entry["_offering_link"] = (
                f"/vendors/{vid}/offerings/{entry.get('offering_id')}?return_to={quote(return_to, safe='')}"
            )
            row["_offerings"].append(entry)

    page_count = max(1, (int(total_rows) + page_size - 1) // page_size)
    if page > page_count:
        page = page_count
    prev_page = page - 1 if page > 1 else 1
    next_page = page + 1 if page < page_count else page_count
    sort_links: dict[str, str] = {}
    for field in visible_fields:
        mapped_sort = VENDOR_FIELD_SORT_MAP.get(field)
        if not mapped_sort:
            continue
        next_dir = "desc" if sort_by == mapped_sort and sort_dir == "asc" else "asc"
        sort_links[field] = _vendor_list_url(
            q=resolved_q,
            status=status,
            owner=owner,
            risk=risk,
            group=group,
            page=1,
            page_size=page_size,
            sort_by=mapped_sort,
            sort_dir=next_dir,
            show_settings=show_settings,
        )

    _merge_vendor360_settings(
        repo,
        user.user_principal,
        {
            "list_prefs": {
                "q": resolved_q,
                "status": status,
                "owner": owner,
                "risk": risk,
                "group": group,
                "page_size": page_size,
                "sort_by": sort_by,
                "sort_dir": sort_dir,
            }
        },
    )

    context = base_template_context(
        request=request,
        context=user,
        title="Vendor 360",
        active_nav="vendors",
        extra={
            "filters": {
                "q": resolved_q,
                "search": resolved_q,
                "status": status,
                "owner": owner,
                "risk": risk,
                "group": group,
                "page": page,
                "page_size": page_size,
                "sort_by": sort_by,
                "sort_dir": sort_dir,
            },
            "status_options": [VENDOR_FILTER_ALL] + LIFECYCLE_STATES,
            "owner_options": owner_options,
            "risk_options": risk_options,
            "group_options": group_options,
            "grouped": grouped.to_dict("records"),
            "show_settings": bool(show_settings),
            "page_sizes": VENDOR_PAGE_SIZES,
            "all_fields": available_fields,
            "visible_fields": visible_fields,
            "sort_links": sort_links,
            "vendors": vendor_rows,
            "total_rows": int(total_rows),
            "page_count": page_count,
            "show_from": ((page - 1) * page_size + 1) if total_rows else 0,
            "show_to": min(page * page_size, int(total_rows)),
            "prev_page_url": _vendor_list_url(
                q=resolved_q,
                status=status,
                owner=owner,
                risk=risk,
                group=group,
                page=prev_page,
                page_size=page_size,
                sort_by=sort_by,
                sort_dir=sort_dir,
                show_settings=show_settings,
            ),
            "next_page_url": _vendor_list_url(
                q=resolved_q,
                status=status,
                owner=owner,
                risk=risk,
                group=group,
                page=next_page,
                page_size=page_size,
                sort_by=sort_by,
                sort_dir=sort_dir,
                show_settings=show_settings,
            ),
            "settings_toggle_url": _vendor_list_url(
                q=resolved_q,
                status=status,
                owner=owner,
                risk=risk,
                group=group,
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_dir=sort_dir,
                show_settings=0 if show_settings else 1,
            ),
            "return_to": return_to,
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendors_list.html", context)


@router.post("/settings")
@require_permission("vendor_search_settings_edit")
async def vendor_settings(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()

    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))
    field_names = [str(x) for x in form.getlist("field_name")]
    selected: list[tuple[int, str]] = []
    for field in field_names:
        if form.get(f"include_{field}") != "on":
            continue
        order_raw = str(form.get(f"order_{field}", "999"))
        try:
            order_num = int(order_raw)
        except ValueError:
            order_num = 999
        selected.append((order_num, field))
    selected.sort(key=lambda t: t[0])
    visible_fields = [field for _, field in selected]
    if not visible_fields:
        visible_fields = [field for field in DEFAULT_VENDOR_FIELDS if field in field_names] or field_names

    _merge_vendor360_settings(repo, user.user_principal, {"visible_fields": visible_fields})
    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="vendor_360",
        event_type="update_field_matrix",
        payload={"field_count": len(visible_fields)},
    )
    add_flash(request, "Vendor list fields updated.", "success")
    return RedirectResponse(url=return_to, status_code=303)


@router.get("/new")
def vendor_new_form(request: Request, return_to: str = VENDOR_DEFAULT_RETURN_TO):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Vendor Create")

    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to create vendors.", "error")
        return RedirectResponse(url=_safe_return_to(return_to), status_code=303)

    return _render_vendor_new_form(
        request=request,
        user=user,
        repo=repo,
        return_to=return_to,
    )


@router.post("/new")
@require_permission("vendor_create")
async def vendor_new_submit(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    form = await request.form()

    return_to = _safe_return_to(str(form.get("return_to", VENDOR_DEFAULT_RETURN_TO)))
    if _write_blocked(user):
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=return_to, status_code=303)
    if not user.can_edit:
        add_flash(request, "You do not have permission to create vendors.", "error")
        return RedirectResponse(url=return_to, status_code=303)

    form_values = {
        "legal_name": str(form.get("legal_name", "")).strip(),
        "display_name": str(form.get("display_name", "")).strip(),
        "lifecycle_state": str(form.get("lifecycle_state", "draft")).strip().lower(),
        "owner_org_choice": str(form.get("owner_org_choice", "")).strip(),
        "new_owner_org_id": str(form.get("new_owner_org_id", "")).strip(),
        "risk_tier": str(form.get("risk_tier", "")).strip().lower(),
        "source_system": str(form.get("source_system", DEFAULT_SOURCE_SYSTEM)).strip(),
    }
    legacy_owner_org_id = str(form.get("owner_org_id", "")).strip()
    if legacy_owner_org_id and not form_values["owner_org_choice"] and not form_values["new_owner_org_id"]:
        form_values["owner_org_choice"] = legacy_owner_org_id
    owner_org_id = ""
    if form_values["owner_org_choice"] and form_values["owner_org_choice"] != "__new__":
        owner_org_id = form_values["owner_org_choice"]
    elif form_values["owner_org_choice"] == "__new__":
        owner_org_id = form_values["new_owner_org_id"]

    field_errors: dict[str, str] = {}
    if not form_values["legal_name"]:
        field_errors["legal_name"] = "Legal name is required."
    if not owner_org_id:
        if form_values["owner_org_choice"] == "__new__":
            field_errors["new_owner_org_id"] = "Enter a new Line of Business."
        else:
            field_errors["owner_org_choice"] = "Line of Business is required."

    try:
        form_values["lifecycle_state"] = _normalize_lifecycle(form_values["lifecycle_state"])
        if form_values["risk_tier"] and form_values["risk_tier"] not in RISK_TIERS:
            raise ValueError(f"Risk tier must be one of: {', '.join(RISK_TIERS)}")
    except Exception as exc:
        field_errors["lifecycle_state"] = str(exc)

    if field_errors:
        add_flash(request, "Please fix the highlighted fields.", "error")
        return _render_vendor_new_form(
            request=request,
            user=user,
            repo=repo,
            return_to=return_to,
            form_values=form_values,
            field_errors=field_errors,
            form_error="Validation failed.",
            status_code=400,
        )

    try:
        if user.can_apply_change("create_vendor_profile"):
            vendor_id = repo.create_vendor_profile(
                actor_user_principal=user.user_principal,
                legal_name=form_values["legal_name"],
                display_name=form_values["display_name"] or form_values["legal_name"],
                lifecycle_state=form_values["lifecycle_state"],
                owner_org_id=owner_org_id,
                risk_tier=form_values["risk_tier"] or None,
                source_system=form_values["source_system"] or DEFAULT_SOURCE_SYSTEM,
            )
            repo.log_usage_event(
                user_principal=user.user_principal,
                page_name="vendor_360",
                event_type="vendor_create",
                payload={"vendor_id": vendor_id},
            )
            add_flash(request, f"Vendor created: {vendor_id}", "success")
            return RedirectResponse(
                url=f"/vendors/{vendor_id}/summary?return_to={quote(return_to, safe='')}",
                status_code=303,
            )
        request_id = repo.create_vendor_change_request(
            vendor_id=GLOBAL_CHANGE_VENDOR_ID,
            requestor_user_principal=user.user_principal,
            change_type="create_vendor_profile",
            payload={
                "legal_name": form_values["legal_name"],
                "display_name": form_values["display_name"] or form_values["legal_name"],
                "lifecycle_state": form_values["lifecycle_state"],
                "owner_org_id": owner_org_id,
                "risk_tier": form_values["risk_tier"] or None,
                "source_system": form_values["source_system"] or DEFAULT_SOURCE_SYSTEM,
            },
        )
        add_flash(request, f"Pending change request submitted: {request_id}", "success")
        return RedirectResponse(url="/workflows?status=pending", status_code=303)
    except Exception as exc:
        error_text = str(exc)
        if "owner_org_id" in error_text.lower():
            field_errors["owner_org_choice"] = "Line of Business is required."
            if form_values["owner_org_choice"] == "__new__":
                field_errors["new_owner_org_id"] = "Line of Business is required."
        add_flash(request, "Could not create vendor. Fix the highlighted fields and try again.", "error")
        return _render_vendor_new_form(
            request=request,
            user=user,
            repo=repo,
            return_to=return_to,
            form_values=form_values,
            field_errors=field_errors,
            form_error=error_text,
            status_code=400,
        )





