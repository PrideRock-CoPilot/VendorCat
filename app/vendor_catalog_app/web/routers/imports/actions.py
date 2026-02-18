from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from vendor_catalog_app.web.http.flash import add_flash
from vendor_catalog_app.web.routers.imports.apply_ops import (
    ImportApplyContext,
    apply_import_row,
    apply_stage_area_rows_for_row,
)
from vendor_catalog_app.web.routers.imports.config import (
    ALLOWED_IMPORT_ACTIONS,
    IMPORT_LAYOUTS,
    IMPORT_PREVIEW_RENDER_LIMIT,
    IMPORT_RESULTS_RENDER_LIMIT,
)
from vendor_catalog_app.web.routers.imports.mappings import (
    compatible_profiles,
    find_profile_by_id,
    load_mapping_profiles,
    save_mapping_profile,
)
from vendor_catalog_app.web.routers.imports.matching import build_preview_rows
from vendor_catalog_app.web.routers.imports.parsing import (
    build_stage_area_rows,
    can_manage_imports,
    layout_field_mapping_from_source_targets,
    parse_layout_rows,
    render_context,
    resolve_field_mapping,
    resolve_source_target_mapping,
    safe_delimiter,
    safe_format_hint,
    safe_flow_mode,
    safe_layout,
    safe_source_system,
    write_blocked,
)
from vendor_catalog_app.web.routers.imports.staging import (
    finalize_import_staging_job,
    stage_import_preview,
)
from vendor_catalog_app.web.routers.imports.store import (
    discard_preview_payload,
    load_preview_payload,
    save_preview_payload,
)
from vendor_catalog_app.web.security.rbac import require_permission

router = APIRouter()


def _imports_module():
    # Resolve through package namespace so tests can monkeypatch imports.get_repo/get_user_context.
    from vendor_catalog_app.web.routers import imports as imports_module

    return imports_module


def _source_target_mapping_from_form(form: Any) -> dict[str, str]:
    sources = [str(item or "").strip() for item in form.getlist("source_field_keys")]
    targets = [str(item or "").strip() for item in form.getlist("source_target_keys")]
    mapping: dict[str, str] = {}
    for index, source_key in enumerate(sources):
        if not source_key:
            continue
        target_key = str(targets[index] if index < len(targets) else "").strip()
        mapping[source_key] = target_key
    return mapping


def _decorate_mapping_profiles(
    *,
    profiles: list[dict[str, Any]],
    compatible: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    compatible_ids = {str(row.get("profile_id") or "").strip() for row in compatible}
    items: list[dict[str, Any]] = []
    for row in profiles:
        item = dict(row)
        item["compatible"] = str(item.get("profile_id") or "").strip() in compatible_ids
        items.append(item)
    return items


def _profile_source_target_mapping(profile: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(profile, dict):
        return {}
    direct = {str(k): str(v) for k, v in dict(profile.get("source_target_mapping") or {}).items() if str(k).strip()}
    if direct:
        return direct
    # Backward compatibility: old profile format stored target->source.
    legacy_target_to_source = dict(profile.get("field_mapping") or {})
    converted: dict[str, str] = {}
    for target_key, source_key in legacy_target_to_source.items():
        source = str(source_key or "").strip()
        target = str(target_key or "").strip()
        if not source:
            continue
        if source not in converted:
            converted[source] = target
    return converted


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
    flow_mode = safe_flow_mode(str(form.get("flow_mode", "quick")))
    source_system = safe_source_system(str(form.get("source_system", "spreadsheet_manual")))
    source_object = str(form.get("source_object", "") or "").strip()
    format_hint = safe_format_hint(str(form.get("format_hint", "auto")))
    delimiter = safe_delimiter(str(form.get("delimiter", ",")))
    json_record_path = str(form.get("json_record_path", "") or "").strip()
    xml_record_tag = str(form.get("xml_record_tag", "") or "").strip()
    selected_mapping_profile_id = str(form.get("mapping_profile_id", "") or "").strip()
    selected_mapping_profile_name = ""
    available_profiles = load_mapping_profiles(repo, user_principal=user.user_principal, layout_key=selected_layout)
    selected_profile = find_profile_by_id(available_profiles, selected_mapping_profile_id)
    requested_source_target_mapping: dict[str, str] = {}
    if selected_profile is not None:
        requested_source_target_mapping.update(_profile_source_target_mapping(selected_profile))
        selected_mapping_profile_name = str(selected_profile.get("profile_name") or "").strip()
    requested_source_target_mapping.update(_source_target_mapping_from_form(form))

    upload = form.get("file")
    if upload is None or not hasattr(upload, "filename"):
        add_flash(request, "Select a file to upload.", "error")
        return RedirectResponse(url="/imports", status_code=303)
    source_file_name = str(getattr(upload, "filename", "") or "").strip()
    raw_bytes = await upload.read()
    if not raw_bytes:
        add_flash(request, "Uploaded file is empty.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    try:
        parse_result = parse_layout_rows(
            selected_layout,
            raw_bytes,
            file_name=source_file_name,
            format_hint=format_hint,
            delimiter=delimiter,
            json_record_path=json_record_path,
            xml_record_tag=xml_record_tag,
            strict_layout=(flow_mode == "quick"),
            source_target_mapping=requested_source_target_mapping,
        )
        parsed_rows = list(parse_result.get("rows") or [])
        source_rows = list(parse_result.get("source_rows") or [])
        source_fields = list(parse_result.get("source_fields") or [])
        resolved_field_mapping = dict(parse_result.get("field_mapping") or {})
        resolved_source_target_mapping = dict(parse_result.get("source_target_mapping") or {})
        stage_area_rows = {
            str(area): list(rows or [])
            for area, rows in dict(parse_result.get("stage_area_rows") or {}).items()
        }
        detected_format = str(parse_result.get("detected_format") or "")
        effective_format = str(parse_result.get("effective_format") or "")
        parser_options = dict(parse_result.get("parser_options") or {})
        parser_warnings = list(parse_result.get("warnings") or [])
        compatible = compatible_profiles(
            profiles=available_profiles,
            file_format=effective_format,
            source_fields=source_fields,
        )
        if selected_mapping_profile_id and find_profile_by_id(compatible, selected_mapping_profile_id) is None:
            parser_warnings.append(
                "Selected mapping profile signature does not match detected source tags/columns. "
                "Review mapping before apply."
            )
        preview_rows_full = build_preview_rows(repo, selected_layout, parsed_rows)
    except Exception as exc:
        add_flash(request, f"Failed to parse import file: {exc}", "error")
        return RedirectResponse(url="/imports", status_code=303)

    import_job_id, staged_row_count, staging_warning = stage_import_preview(
        repo,
        layout_key=selected_layout,
        source_system=source_system,
        source_object=source_object,
        file_name=source_file_name,
        file_type=str(source_file_name.rsplit(".", 1)[-1].lower() if "." in source_file_name else ""),
        detected_format=effective_format,
        parser_options=parser_options,
        preview_rows=preview_rows_full,
        stage_area_rows=stage_area_rows,
        actor_user_principal=user.user_principal,
    )

    preview_payload = {
        "layout_key": selected_layout,
        "source_system": source_system,
        "source_object": source_object,
        "source_file_name": source_file_name,
        "flow_mode": flow_mode,
        "detected_format": detected_format,
        "effective_format": effective_format,
        "parser_options": parser_options,
        "parser_warnings": parser_warnings,
        "import_job_id": import_job_id,
        "source_rows": source_rows,
        "source_fields": source_fields,
        "source_target_mapping": resolved_source_target_mapping,
        "field_mapping": resolved_field_mapping,
        "stage_area_rows": stage_area_rows,
        "selected_mapping_profile_id": selected_mapping_profile_id,
        "selected_mapping_profile_name": selected_mapping_profile_name,
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
            selected_flow_mode=flow_mode,
            selected_source_system=source_system,
            source_object=source_object,
            source_file_name=source_file_name,
            detected_file_type=detected_format,
            effective_file_type=effective_format,
            parser_options=parser_options,
            parser_warnings=parser_warnings,
            staging_job_id=import_job_id,
            staged_row_count=staged_row_count,
            staging_warning=staging_warning,
            preview_token=preview_token,
            preview_rows=preview_rows,
            preview_total_rows=preview_total_rows,
            preview_hidden_count=preview_hidden_count,
            source_field_map=source_fields,
            selected_source_target_mapping=resolved_source_target_mapping,
            mapping_profiles=_decorate_mapping_profiles(
                profiles=available_profiles,
                compatible=compatible,
            ),
            selected_mapping_profile_id=selected_mapping_profile_id,
            import_reason="",
        ),
    )
    return request.app.state.templates.TemplateResponse(request, "imports.html", context)


@router.post("/imports/remap")
@require_permission("import_preview")
async def imports_remap(request: Request):
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
    payload = load_preview_payload(preview_token)
    if payload is None:
        add_flash(request, "Import preview expired. Upload the file again.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    layout_key = safe_layout(str(payload.get("layout_key") or "vendors"))
    flow_mode = safe_flow_mode(str(payload.get("flow_mode") or "wizard"))
    source_system = safe_source_system(str(payload.get("source_system") or "spreadsheet_manual"))
    source_object = str(payload.get("source_object") or "").strip()
    source_file_name = str(payload.get("source_file_name") or "").strip()
    detected_file_type = str(payload.get("detected_format") or "").strip()
    effective_file_type = str(payload.get("effective_format") or "").strip()
    parser_options = dict(payload.get("parser_options") or {})
    parser_warnings = list(payload.get("parser_warnings") or [])
    source_rows = list(payload.get("source_rows") or [])
    source_fields = list(payload.get("source_fields") or [])
    if not source_rows or not source_fields:
        add_flash(request, "Source preview metadata is unavailable. Upload the file again.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    available_profiles = load_mapping_profiles(repo, user_principal=user.user_principal, layout_key=layout_key)
    selected_mapping_profile_id = str(form.get("mapping_profile_id", "") or "").strip()
    selected_profile = find_profile_by_id(available_profiles, selected_mapping_profile_id)
    requested_source_target_mapping: dict[str, str] = {}
    if selected_profile is not None:
        requested_source_target_mapping.update(_profile_source_target_mapping(selected_profile))
    requested_source_target_mapping.update(_source_target_mapping_from_form(form))

    resolved_source_target_mapping = resolve_source_target_mapping(
        source_fields=source_fields,
        requested_mapping=requested_source_target_mapping,
    )
    resolved_field_mapping = layout_field_mapping_from_source_targets(
        layout_key=layout_key,
        source_target_mapping=resolved_source_target_mapping,
    )
    allowed_fields = [str(field) for field in IMPORT_LAYOUTS.get(layout_key, {}).get("fields", [])]
    resolved_field_mapping = resolve_field_mapping(
        allowed_fields=allowed_fields,
        source_fields=source_fields,
        requested_mapping=resolved_field_mapping,
    )
    stage_area_rows = build_stage_area_rows(
        source_rows=source_rows,
        source_target_mapping=resolved_source_target_mapping,
    )
    # Reuse cached parsed source rows for remap path; avoid re-upload requirement.
    mapped_rows_for_preview = []
    for row in source_rows:
        out_row: dict[str, str] = {}
        for field, source_key in resolved_field_mapping.items():
            out_row[str(field)] = str(row.get(str(source_key), "") or "").strip() if source_key else ""
        out_row["_line"] = str(row.get("_line") or "")
        mapped_rows_for_preview.append(out_row)
    preview_rows_full = build_preview_rows(repo, layout_key, mapped_rows_for_preview)
    compatible = compatible_profiles(
        profiles=available_profiles,
        file_format=effective_file_type,
        source_fields=source_fields,
    )

    profile_name_to_save = str(form.get("mapping_profile_name", "") or "").strip()
    mapping_profile_saved = ""
    if profile_name_to_save:
        saved_id = save_mapping_profile(
            repo,
            user_principal=user.user_principal,
            layout_key=layout_key,
            profile_name=profile_name_to_save,
            file_format=effective_file_type,
            source_fields=source_fields,
            source_target_mapping=resolved_source_target_mapping,
            field_mapping=resolved_field_mapping,
            parser_options=parser_options,
            profile_id=selected_mapping_profile_id,
        )
        if saved_id:
            selected_mapping_profile_id = saved_id
            mapping_profile_saved = profile_name_to_save
            add_flash(request, f"Saved mapping profile '{profile_name_to_save}'.", "success")
            available_profiles = load_mapping_profiles(repo, user_principal=user.user_principal, layout_key=layout_key)
            compatible = compatible_profiles(
                profiles=available_profiles,
                file_format=effective_file_type,
                source_fields=source_fields,
            )
        else:
            add_flash(request, "Could not save mapping profile.", "error")

    import_job_id, staged_row_count, staging_warning = stage_import_preview(
        repo,
        layout_key=layout_key,
        source_system=source_system,
        source_object=source_object,
        file_name=source_file_name,
        file_type=str(source_file_name.rsplit(".", 1)[-1].lower() if "." in source_file_name else ""),
        detected_format=effective_file_type,
        parser_options=parser_options,
        preview_rows=preview_rows_full,
        stage_area_rows=stage_area_rows,
        actor_user_principal=user.user_principal,
    )

    next_payload = dict(payload)
    next_payload["import_job_id"] = import_job_id
    next_payload["field_mapping"] = resolved_field_mapping
    next_payload["source_target_mapping"] = resolved_source_target_mapping
    next_payload["stage_area_rows"] = stage_area_rows
    next_payload["selected_mapping_profile_id"] = selected_mapping_profile_id
    next_payload["rows"] = preview_rows_full
    next_token = save_preview_payload(next_payload)
    discard_preview_payload(preview_token)

    preview_rows = preview_rows_full[:IMPORT_PREVIEW_RENDER_LIMIT]
    preview_total_rows = len(preview_rows_full)
    preview_hidden_count = max(0, preview_total_rows - len(preview_rows))

    context = imports_module.base_template_context(
        request,
        user,
        title="Data Imports",
        active_nav="imports",
        extra=render_context(
            selected_layout=layout_key,
            selected_flow_mode=flow_mode,
            selected_source_system=source_system,
            source_object=source_object,
            source_file_name=source_file_name,
            detected_file_type=detected_file_type,
            effective_file_type=effective_file_type,
            parser_options=parser_options,
            parser_warnings=parser_warnings,
            staging_job_id=import_job_id,
            staged_row_count=staged_row_count,
            staging_warning=staging_warning,
            preview_token=next_token,
            preview_rows=preview_rows,
            preview_total_rows=preview_total_rows,
            preview_hidden_count=preview_hidden_count,
            source_field_map=source_fields,
            selected_source_target_mapping=resolved_source_target_mapping,
            mapping_profiles=_decorate_mapping_profiles(
                profiles=available_profiles,
                compatible=compatible,
            ),
            selected_mapping_profile_id=selected_mapping_profile_id,
            mapping_profile_saved=mapping_profile_saved,
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
    flow_mode = safe_flow_mode(str(payload.get("flow_mode") or "wizard"))
    source_system = safe_source_system(str(payload.get("source_system") or "spreadsheet_manual"))
    source_object = str(payload.get("source_object") or "").strip()
    source_file_name = str(payload.get("source_file_name") or "").strip()
    detected_file_type = str(payload.get("detected_format") or "").strip()
    effective_file_type = str(payload.get("effective_format") or "").strip()
    parser_options = dict(payload.get("parser_options") or {})
    parser_warnings = list(payload.get("parser_warnings") or [])
    source_fields = list(payload.get("source_fields") or [])
    selected_source_target_mapping = dict(payload.get("source_target_mapping") or {})
    selected_mapping_profile_id = str(payload.get("selected_mapping_profile_id") or "").strip()
    available_profiles = load_mapping_profiles(repo, user_principal=user.user_principal, layout_key=layout_key)
    compatible = compatible_profiles(
        profiles=available_profiles,
        file_format=effective_file_type,
        source_fields=source_fields,
    )
    import_job_id = str(payload.get("import_job_id") or "").strip()
    preview_rows = list(payload.get("rows") or [])
    stage_area_rows = {
        str(area): list(rows or [])
        for area, rows in dict(payload.get("stage_area_rows") or {}).items()
    }
    results: list[dict[str, Any]] = []
    created_count = 0
    merged_count = 0
    skipped_count = 0
    failed_count = 0
    child_apply_counts: dict[str, int] = {}

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
            status, message, apply_result = apply_import_row(
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
            child_counts = apply_stage_area_rows_for_row(
                repo,
                stage_area_rows=stage_area_rows,
                row_index=row_index,
                selected_action=selected_action,
                row_data=row_data,
                fallback_target_vendor_id=fallback_target_vendor_id,
                primary_result=apply_result,
                actor_user_principal=user.user_principal,
                reason=reason or "bulk import",
                apply_context=apply_context,
            )
            if child_counts:
                parts = [f"{key}={value}" for key, value in sorted(child_counts.items())]
                message = f"{message} | child writes: {', '.join(parts)}"
                for key, value in child_counts.items():
                    child_apply_counts[key] = int(child_apply_counts.get(key, 0)) + int(value or 0)
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

    finalize_import_staging_job(
        repo,
        import_job_id=import_job_id,
        created_count=created_count,
        merged_count=merged_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        actor_user_principal=user.user_principal,
        error_message="" if failed_count == 0 else "One or more row apply operations failed.",
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
    if child_apply_counts:
        child_summary = ", ".join([f"{key}={value}" for key, value in sorted(child_apply_counts.items())])
        add_flash(request, f"Applied child entity writes: {child_summary}", "info")
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
            selected_flow_mode=flow_mode,
            selected_source_system=source_system,
            source_object=source_object,
            source_file_name=source_file_name,
            detected_file_type=detected_file_type,
            effective_file_type=effective_file_type,
            parser_options=parser_options,
            parser_warnings=parser_warnings,
            staging_job_id=import_job_id,
            staged_row_count=len(preview_rows),
            preview_token="",
            preview_rows=[],
            preview_total_rows=0,
            preview_hidden_count=0,
            source_field_map=source_fields,
            selected_source_target_mapping=selected_source_target_mapping,
            mapping_profiles=_decorate_mapping_profiles(
                profiles=available_profiles,
                compatible=compatible,
            ),
            selected_mapping_profile_id=selected_mapping_profile_id,
            import_results=results,
            import_reason=reason,
        ),
    )
    return request.app.state.templates.TemplateResponse(request, "imports.html", context)

