from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.core.activity import ensure_session_started, log_page_view
from vendor_catalog_app.web.core.runtime import get_repo
from vendor_catalog_app.web.core.template_context import base_template_context
from vendor_catalog_app.web.core.user_context_service import get_user_context
from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter(prefix="/vendors")


def _render_merge_center(
    *,
    request: Request,
    user,
    survivor_vendor_id: str,
    source_vendor_id: str,
    merge_preview: dict | None = None,
    merge_execute_result: dict | None = None,
):
    context = base_template_context(
        request=request,
        context=user,
        title="Vendor Merge Center",
        active_nav="vendors",
        extra={
            "survivor_vendor_id": str(survivor_vendor_id or "").strip(),
            "source_vendor_id": str(source_vendor_id or "").strip(),
            "merge_preview": dict(merge_preview or {}),
            "merge_execute_result": dict(merge_execute_result or {}),
        },
    )
    return request.app.state.templates.TemplateResponse(request, "vendor_merge_center.html", context)


@router.get("/merge-center")
@require_permission("merge_vendor_records")
async def vendor_merge_center_page(
    request: Request,
    survivor_vendor_id: str = "",
    source_vendor_id: str = "",
):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Vendor Merge Center")

    preview: dict | None = None
    survivor_id = str(survivor_vendor_id or "").strip()
    source_id = str(source_vendor_id or "").strip()
    if survivor_id and source_id:
        try:
            preview = repo.preview_vendor_merge(
                survivor_vendor_id=survivor_id,
                source_vendor_id=source_id,
            )
        except Exception as exc:
            add_flash(request, f"Could not preview merge: {exc}", "error")
    return _render_merge_center(
        request=request,
        user=user,
        survivor_vendor_id=survivor_id,
        source_vendor_id=source_id,
        merge_preview=preview,
    )


@router.post("/merge-center/preview")
@require_permission("merge_vendor_records")
async def vendor_merge_center_preview(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Vendor Merge Center")

    form = await request.form()
    survivor_id = str(form.get("survivor_vendor_id") or "").strip()
    source_id = str(form.get("source_vendor_id") or "").strip()
    if not survivor_id or not source_id:
        add_flash(request, "Both survivor and source vendor IDs are required.", "error")
        return _render_merge_center(
            request=request,
            user=user,
            survivor_vendor_id=survivor_id,
            source_vendor_id=source_id,
        )
    try:
        preview = repo.preview_vendor_merge(
            survivor_vendor_id=survivor_id,
            source_vendor_id=source_id,
        )
    except Exception as exc:
        add_flash(request, f"Could not preview merge: {exc}", "error")
        return _render_merge_center(
            request=request,
            user=user,
            survivor_vendor_id=survivor_id,
            source_vendor_id=source_id,
        )
    return _render_merge_center(
        request=request,
        user=user,
        survivor_vendor_id=survivor_id,
        source_vendor_id=source_id,
        merge_preview=preview,
    )


@router.post("/merge-center/execute")
@require_permission("merge_vendor_records")
async def vendor_merge_center_execute(request: Request):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    log_page_view(request, user, "Vendor Merge Center")

    form = await request.form()
    survivor_id = str(form.get("survivor_vendor_id") or "").strip()
    source_id = str(form.get("source_vendor_id") or "").strip()
    merge_reason = str(form.get("merge_reason") or "").strip() or "vendor_merge_center"
    if not survivor_id or not source_id:
        add_flash(request, "Both survivor and source vendor IDs are required.", "error")
        return RedirectResponse(url="/vendors/merge-center", status_code=303)

    try:
        preview = repo.preview_vendor_merge(
            survivor_vendor_id=survivor_id,
            source_vendor_id=source_id,
        )
    except Exception as exc:
        add_flash(request, f"Could not preview merge: {exc}", "error")
        return RedirectResponse(url="/vendors/merge-center", status_code=303)

    field_decisions: dict[str, str] = {}
    for conflict in list(preview.get("conflicts") or []):
        field_name = str(conflict.get("field_name") or "").strip()
        if not field_name:
            continue
        field_decisions[field_name] = str(form.get(f"conflict_decision_{field_name}") or "").strip().lower() or "survivor"

    offering_decisions: dict[str, dict[str, str]] = {}
    for collision in list(preview.get("offering_collisions") or []):
        source_offering_id = str(collision.get("source_offering_id") or "").strip()
        if not source_offering_id:
            continue
        offering_decisions[source_offering_id] = {
            "decision": str(form.get(f"offering_decision_{source_offering_id}") or "").strip().lower() or "keep_both",
            "target_offering_id": str(form.get(f"offering_target_{source_offering_id}") or "").strip(),
            "renamed_offering_name": str(form.get(f"offering_rename_{source_offering_id}") or "").strip(),
        }

    try:
        result = repo.execute_vendor_merge(
            survivor_vendor_id=survivor_id,
            source_vendor_id=source_id,
            field_decisions=field_decisions,
            offering_decisions=offering_decisions,
            actor_user_principal=user.user_principal,
            merge_reason=merge_reason,
        )
    except Exception as exc:
        add_flash(request, f"Merge execute failed: {exc}", "error")
        return _render_merge_center(
            request=request,
            user=user,
            survivor_vendor_id=survivor_id,
            source_vendor_id=source_id,
            merge_preview=preview,
        )

    add_flash(
        request,
        f"Vendor merge executed. source={source_id} -> survivor={str(result.get('survivor_vendor_id') or survivor_id)}",
        "success",
    )
    canonical_survivor = str(result.get("survivor_vendor_id") or survivor_id).strip()
    return RedirectResponse(url=f"/vendors/{canonical_survivor}/summary?return_to=%2Fvendors%2Fmerge-center", status_code=303)
