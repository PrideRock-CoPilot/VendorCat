from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.imports.apply_ops import (
    ImportApplyContext,
    apply_import_row,
)
from vendor_catalog_app.web.routers.imports.config import (
    ALLOWED_IMPORT_ACTIONS,
    IMPORT_PREVIEW_RENDER_LIMIT,
    IMPORT_RESULTS_RENDER_LIMIT,
)
from vendor_catalog_app.web.routers.imports.matching import build_preview_rows
from vendor_catalog_app.web.routers.imports.parsing import (
    can_manage_imports,
    parse_layout_rows,
    render_context,
    safe_layout,
    write_blocked,
)
from vendor_catalog_app.web.routers.imports.store import (
    discard_preview_payload,
    load_preview_payload,
    save_preview_payload,
)
from vendor_catalog_app.web.routers.vendors.constants import IMPORT_MERGE_REASON_OPTIONS
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter()


def _imports_module():
    # Resolve through package namespace so tests can monkeypatch imports.get_repo/get_user_context.
    from vendor_catalog_app.web.routers import imports as imports_module

    return imports_module


@router.post("/imports/preview")
@require_permission("import_preview")
async def imports_preview(request: Request):
    imports_module = _imports_module()
    repo = imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    imports_module.log_page_view(request, user, "Imports")

    if not can_manage_imports(user):
        add_flash(request, "You do not have permission to run imports.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)
    if write_blocked(user):
        add_flash(request, "Application is in locked mode. Import actions are disabled.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    form = await request.form()
    selected_layout = safe_layout(str(form.get("layout", "vendors")))
    upload = form.get("file")
    if upload is None or not hasattr(upload, "filename"):
        add_flash(request, "Select a CSV file to upload.", "error")
        return RedirectResponse(url="/imports", status_code=303)
    raw_bytes = await upload.read()
    if not raw_bytes:
        add_flash(request, "Uploaded file is empty.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    try:
        parsed_rows = parse_layout_rows(selected_layout, raw_bytes)
        preview_rows_full = build_preview_rows(repo, selected_layout, parsed_rows)
    except Exception as exc:
        add_flash(request, f"Failed to parse import file: {exc}", "error")
        return RedirectResponse(url="/imports", status_code=303)

    preview_payload = {
        "layout_key": selected_layout,
        "rows": preview_rows_full,
    }
    preview_token = save_preview_payload(preview_payload)
    preview_rows = preview_rows_full[:IMPORT_PREVIEW_RENDER_LIMIT]
    preview_total_rows = len(preview_rows_full)
    preview_hidden_count = max(0, preview_total_rows - len(preview_rows))

    context = imports_module.base_template_context(
        request,
        user,
        title="Data Imports",
        active_nav="imports",
        extra=render_context(
            selected_layout=selected_layout,
            preview_token=preview_token,
            preview_rows=preview_rows,
            preview_total_rows=preview_total_rows,
            preview_hidden_count=preview_hidden_count,
            import_reason="",
        ),
    )
    return request.app.state.templates.TemplateResponse(request, "imports.html", context)


@router.post("/imports/apply")
@require_permission("import_apply")
async def imports_apply(request: Request):
    imports_module = _imports_module()
    repo = imports_module.get_repo()
    user = imports_module.get_user_context(request)
    imports_module.ensure_session_started(request, user)
    imports_module.log_page_view(request, user, "Imports")

    if not can_manage_imports(user):
        add_flash(request, "You do not have permission to run imports.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)
    if write_blocked(user):
        add_flash(request, "Application is in locked mode. Import actions are disabled.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    form = await request.form()
    preview_token = str(form.get("preview_token", "")).strip()
    reason = str(form.get("reason", "")).strip()
    payload = load_preview_payload(preview_token)
    if payload is None:
        add_flash(request, "Import preview expired. Upload the file again.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    layout_key = safe_layout(str(payload.get("layout_key") or "vendors"))
    preview_rows = list(payload.get("rows") or [])
    results: list[dict[str, Any]] = []
    created_count = 0
    merged_count = 0
    skipped_count = 0
    failed_count = 0

    bulk_default_action = str(form.get("bulk_default_action", "")).strip().lower()
    if bulk_default_action not in ALLOWED_IMPORT_ACTIONS:
        bulk_default_action = ""
    apply_context = ImportApplyContext(repo)

    for preview_row in preview_rows:
        row_index = int(preview_row.get("row_index") or 0)
        row_data = dict(preview_row.get("row_data") or {})
        default_action = str(preview_row.get("suggested_action") or "new").strip().lower()
        action_key = f"action_{row_index}"
        if action_key in form:
            selected_action = str(form.get(action_key, default_action)).strip().lower()
        elif bulk_default_action:
            selected_action = bulk_default_action
        else:
            selected_action = default_action
        if selected_action not in ALLOWED_IMPORT_ACTIONS:
            selected_action = "skip"

        target_id = str(
            form.get(
                f"target_{row_index}",
                str(preview_row.get("suggested_target_id") or ""),
            )
            or ""
        ).strip()
        fallback_target_vendor_id = str(preview_row.get("suggested_target_vendor_id") or "").strip()

        try:
            if selected_action == "merge" and not reason:
                raise ValueError("Reason is required for merge actions.")
            status, message = apply_import_row(
                repo,
                layout_key=layout_key,
                row_data=row_data,
                action=selected_action,
                target_id=target_id,
                fallback_target_vendor_id=fallback_target_vendor_id,
                actor_user_principal=user.user_principal,
                reason=reason or "bulk import",
                apply_context=apply_context,
            )
            if status == "created":
                created_count += 1
            elif status == "merged":
                merged_count += 1
            elif status == "skipped":
                skipped_count += 1
            if len(results) < IMPORT_RESULTS_RENDER_LIMIT:
                results.append(
                    {
                        "row_index": row_index,
                        "status": status,
                        "message": message,
                    }
                )
        except Exception as exc:
            failed_count += 1
            if len(results) < IMPORT_RESULTS_RENDER_LIMIT:
                results.append(
                    {
                        "row_index": row_index,
                        "status": "failed",
                        "message": str(exc),
                    }
                )

    discard_preview_payload(preview_token)
    if failed_count == 0:
        add_flash(
            request,
            (
                "Import complete. "
                f"created={created_count}, merged={merged_count}, skipped={skipped_count}, failed={failed_count}"
            ),
            "success",
        )
    else:
        add_flash(
            request,
            (
                "Import completed with errors. "
                f"created={created_count}, merged={merged_count}, skipped={skipped_count}, failed={failed_count}"
            ),
            "error",
        )
    if len(preview_rows) > IMPORT_RESULTS_RENDER_LIMIT:
        hidden_results = len(preview_rows) - IMPORT_RESULTS_RENDER_LIMIT
        add_flash(
            request,
            f"Showing first {IMPORT_RESULTS_RENDER_LIMIT} result rows. {hidden_results} additional rows were applied.",
            "info",
        )

    context = imports_module.base_template_context(
        request,
        user,
        title="Data Imports",
        active_nav="imports",
        extra=render_context(
            selected_layout=layout_key,
            preview_token="",
            preview_rows=[],
            preview_total_rows=0,
            preview_hidden_count=0,
            import_results=results,
            import_reason=reason,
        ),
    )
    return request.app.state.templates.TemplateResponse(request, "imports.html", context)

