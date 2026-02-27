from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.admin.common import (
    ADMIN_SECTION_OWNERSHIP,
    _admin_redirect_url,
)
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/admin")


@router.post("/ownership/reassign")
@require_permission("admin_role_manage")
async def ownership_reassign_submit(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    if user.config.locked_mode:
        add_flash(request, "Application is in locked mode. Write actions are disabled.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_OWNERSHIP), status_code=303)
    if not user.has_admin_rights:
        add_flash(request, "Admin access required.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await request.form()
    source_owner = str(form.get("source_owner", "")).strip()
    action_mode = str(form.get("action_mode", "selected_default")).strip().lower()
    default_target_owner = str(form.get("default_target_owner", "")).strip()

    if not source_owner:
        add_flash(request, "Source owner is required.", "error")
        return RedirectResponse(url=_admin_redirect_url(section=ADMIN_SECTION_OWNERSHIP), status_code=303)

    try:
        rows = repo.list_owner_reassignment_assignments(source_owner)
    except Exception as exc:
        add_flash(request, f"Could not load source ownerships: {exc}", "error")
        return RedirectResponse(
            url=f"{_admin_redirect_url(section=ADMIN_SECTION_OWNERSHIP)}&source_owner={quote(source_owner, safe='')}",
            status_code=303,
        )

    row_lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        assignment_key = str(row.get("assignment_key") or "").strip()
        if assignment_key:
            row_lookup[assignment_key] = {
                "assignment_type": str(row.get("assignment_type") or "").strip(),
                "assignment_id": str(row.get("assignment_id") or "").strip(),
            }

    selected_keys = [str(x).strip() for x in form.getlist("selected_assignment_key") if str(x).strip()]
    if action_mode == "all_default":
        target_keys = list(row_lookup.keys())
    else:
        target_keys = [key for key in selected_keys if key in row_lookup]

    if not target_keys:
        add_flash(request, "Select at least one ownership row to reassign.", "error")
        return RedirectResponse(
            url=f"{_admin_redirect_url(section=ADMIN_SECTION_OWNERSHIP)}&source_owner={quote(source_owner, safe='')}",
            status_code=303,
        )

    if action_mode in {"all_default", "selected_default"} and not default_target_owner:
        add_flash(request, "Replacement owner is required for default reassignment.", "error")
        return RedirectResponse(
            url=f"{_admin_redirect_url(section=ADMIN_SECTION_OWNERSHIP)}&source_owner={quote(source_owner, safe='')}",
            status_code=303,
        )

    assignments: list[dict[str, str]] = []
    missing_targets: list[str] = []
    for key in target_keys:
        row = row_lookup.get(key)
        if not row:
            continue
        per_row_target = str(form.get(f"target_for__{key}", "")).strip()
        if action_mode == "selected_per_row":
            target_owner = per_row_target or default_target_owner
        else:
            target_owner = default_target_owner
        if not target_owner:
            missing_targets.append(key)
            continue
        assignments.append(
            {
                "assignment_type": row["assignment_type"],
                "assignment_id": row["assignment_id"],
                "target_owner": target_owner,
            }
        )

    if missing_targets:
        add_flash(request, "One or more selected rows are missing replacement owner values.", "error")
        return RedirectResponse(
            url=f"{_admin_redirect_url(section=ADMIN_SECTION_OWNERSHIP)}&source_owner={quote(source_owner, safe='')}",
            status_code=303,
        )

    try:
        result = repo.bulk_reassign_owner_assignments(
            source_user_principal=source_owner,
            assignments=assignments,
            actor_user_principal=user.user_principal,
        )
    except Exception as exc:
        add_flash(request, f"Could not reassign ownerships: {exc}", "error")
        return RedirectResponse(
            url=f"{_admin_redirect_url(section=ADMIN_SECTION_OWNERSHIP)}&source_owner={quote(source_owner, safe='')}",
            status_code=303,
        )

    repo.log_usage_event(
        user_principal=user.user_principal,
        page_name="admin",
        event_type="owner_bulk_reassign",
        payload={
            "source_owner": source_owner,
            "updated_count": int(result.get("updated_count", 0)),
            "skipped_count": int(result.get("skipped_count", 0)),
            "mode": action_mode,
        },
    )

    updated_count = int(result.get("updated_count", 0))
    skipped_count = int(result.get("skipped_count", 0))
    add_flash(
        request,
        f"Ownership reassignment complete. Updated: {updated_count}; Skipped: {skipped_count}.",
        "success",
    )
    return RedirectResponse(
        url=f"{_admin_redirect_url(section=ADMIN_SECTION_OWNERSHIP)}&source_owner={quote(source_owner, safe='')}",
        status_code=303,
    )
