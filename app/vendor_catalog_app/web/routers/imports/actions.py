from __future__ import annotations

import io
from typing import Any
import zipfile

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
    import_dynamic_field_catalog,
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


def _can_manage_mapping_profiles(user) -> bool:
    checker = getattr(user, "can_apply_change", None)
    if callable(checker):
        try:
            return bool(checker("manage_import_mapping_profile"))
        except Exception:
            return False
    return bool(getattr(user, "can_edit", False))


def _resolve_parser_inputs(
    *,
    format_hint: str,
    delimiter: str,
    json_record_path: str,
    xml_record_path: str,
    xml_record_tag: str,
    selected_profile: dict[str, Any] | None,
) -> tuple[str, str, str, str, str]:
    resolved_format = safe_format_hint(format_hint)
    resolved_delimiter = safe_delimiter(delimiter)
    resolved_json_path = str(json_record_path or "").strip()
    resolved_xml_path = str(xml_record_path or "").strip()
    resolved_xml_tag = str(xml_record_tag or "").strip()
    profile_parser_options = dict((selected_profile or {}).get("parser_options") or {})

    if profile_parser_options:
        profile_format = safe_format_hint(str(profile_parser_options.get("format_hint") or ""))
        if resolved_format == "auto" and profile_format and profile_format != "auto":
            resolved_format = profile_format

        profile_delimiter = safe_delimiter(str(profile_parser_options.get("delimiter") or ","))
        if resolved_delimiter == "," and profile_delimiter != ",":
            resolved_delimiter = profile_delimiter

        if not resolved_json_path:
            resolved_json_path = str(profile_parser_options.get("json_record_path") or "").strip()
        if not resolved_xml_path:
            resolved_xml_path = str(profile_parser_options.get("xml_record_path") or "").strip()
        if not resolved_xml_tag:
            resolved_xml_tag = str(profile_parser_options.get("xml_record_tag") or "").strip()

    return (
        resolved_format,
        resolved_delimiter,
        resolved_json_path,
        resolved_xml_path,
        resolved_xml_tag,
    )


def _guess_bundle_layout(*, file_name: str, fallback_layout: str) -> str:
    name = str(file_name or "").strip().lower()
    if "invoice" in name:
        return "invoices"
    if "payment" in name:
        return "payments"
    if "supplier" in name or "vendor" in name:
        return "vendors"
    if "offering" in name or "product" in name or "service" in name:
        return "offerings"
    if "project" in name:
        return "projects"
    return safe_layout(fallback_layout)


async def _read_upload_bytes(upload: Any) -> bytes:
    if upload is None or not hasattr(upload, "read"):
        return b""
    return await upload.read()


def _extract_zip_members(raw_bytes: bytes) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not raw_bytes:
        return out
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                member_name = str(info.filename or "").strip()
                if not member_name:
                    continue
                member_bytes = archive.read(info)
                if not member_bytes:
                    continue
                out.append(
                    {
                        "file_name": member_name.split("/")[-1],
                        "raw_bytes": member_bytes,
                        "content_type": "",
                    }
                )
    except Exception:
        return []
    return out


async def _collect_import_uploads(form: Any) -> list[dict[str, Any]]:
    uploads: list[dict[str, Any]] = []
    candidates: list[Any] = []
    primary = form.get("file")
    if primary is not None:
        candidates.append(primary)
    for item in form.getlist("files"):
        candidates.append(item)
    bundle_file = form.get("bundle_file")
    if bundle_file is not None:
        candidates.append(bundle_file)

    seen: set[str] = set()
    for upload in candidates:
        if upload is None or not hasattr(upload, "filename"):
            continue
        file_name = str(getattr(upload, "filename", "") or "").strip()
        if not file_name:
            continue
        raw_bytes = await _read_upload_bytes(upload)
        if not raw_bytes:
            continue
        lower_name = file_name.lower()
        if lower_name.endswith(".zip"):
            for member in _extract_zip_members(raw_bytes):
                member_name = str(member.get("file_name") or "").strip()
                if not member_name:
                    continue
                dedupe = member_name.lower()
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                uploads.append(member)
            continue
        dedupe = lower_name
        if dedupe in seen:
            continue
        seen.add(dedupe)
        uploads.append(
            {
                "file_name": file_name,
                "raw_bytes": raw_bytes,
                "content_type": str(getattr(upload, "content_type", "") or "").strip(),
            }
        )
    return uploads


def _bundle_file_summaries(bundle_files: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    totals = {"ready": 0, "review": 0, "blocked": 0, "error": 0, "total": 0}
    for index, item in enumerate(bundle_files):
        preview_rows = list(item.get("rows") or [])
        status_counts = {"ready": 0, "review": 0, "blocked": 0, "error": 0}
        for row in preview_rows:
            status = str(row.get("row_status") or "ready").strip().lower()
            if status not in status_counts:
                status = "review"
            status_counts[status] += 1
        totals["ready"] += int(status_counts.get("ready", 0))
        totals["review"] += int(status_counts.get("review", 0))
        totals["blocked"] += int(status_counts.get("blocked", 0))
        totals["error"] += int(status_counts.get("error", 0))
        totals["total"] += len(preview_rows)
        rows.append(
            {
                "index": index,
                "file_name": str(item.get("file_name") or ""),
                "layout_key": str(item.get("layout_key") or "vendors"),
                "import_job_id": str(item.get("import_job_id") or ""),
                "row_count": len(preview_rows),
                "status_counts": status_counts,
            }
        )
    return rows, totals

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
    format_hint_raw = str(form.get("format_hint", "auto"))
    delimiter_raw = str(form.get("delimiter", ","))
    json_record_path_raw = str(form.get("json_record_path", "") or "").strip()
    xml_record_path_raw = str(form.get("xml_record_path", "") or "").strip()
    xml_record_tag = str(form.get("xml_record_tag", "") or "").strip()
    selected_mapping_profile_id = str(form.get("mapping_profile_id", "") or "").strip()
    selected_mapping_profile_name = ""
    dynamic_field_catalog = import_dynamic_field_catalog(repo)
    available_profiles = load_mapping_profiles(repo, user_principal=user.user_principal, layout_key=selected_layout)
    selected_profile = find_profile_by_id(available_profiles, selected_mapping_profile_id)
    format_hint, delimiter, json_record_path, xml_record_path, xml_record_tag = _resolve_parser_inputs(
        format_hint=format_hint_raw,
        delimiter=delimiter_raw,
        json_record_path=json_record_path_raw,
        xml_record_path=xml_record_path_raw,
        xml_record_tag=xml_record_tag,
        selected_profile=selected_profile,
    )
    requested_source_target_mapping: dict[str, str] = {}
    if selected_profile is not None:
        requested_source_target_mapping.update(_profile_source_target_mapping(selected_profile))
        selected_mapping_profile_name = str(selected_profile.get("profile_name") or "").strip()
    requested_source_target_mapping.update(_source_target_mapping_from_form(form))

    uploads = await _collect_import_uploads(form)
    if not uploads:
        add_flash(request, "Select one or more files to upload.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    if len(uploads) == 1:
        source_file_name = str(uploads[0].get("file_name") or "").strip()
        raw_bytes = bytes(uploads[0].get("raw_bytes") or b"")
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
                xml_record_path=xml_record_path,
                xml_record_tag=xml_record_tag,
                strict_layout=(flow_mode == "quick"),
                source_target_mapping=requested_source_target_mapping,
                dynamic_field_catalog=dynamic_field_catalog,
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
            resolved_record_selector = str(parse_result.get("resolved_record_selector") or "").strip()
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
            preview_rows_full = build_preview_rows(
                repo,
                selected_layout,
                parsed_rows,
                source_rows=source_rows,
                source_target_mapping=resolved_source_target_mapping,
                mapping_profile_id=selected_mapping_profile_id,
                resolved_record_selector=resolved_record_selector,
            )
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
            "resolved_record_selector": resolved_record_selector,
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
                dynamic_field_catalog=dynamic_field_catalog,
                mapping_profiles=_decorate_mapping_profiles(
                    profiles=available_profiles,
                    compatible=compatible,
                ),
                selected_mapping_profile_id=selected_mapping_profile_id,
                import_reason="",
            ),
        )
        return request.app.state.templates.TemplateResponse(request, "imports.html", context)

    bundle_files: list[dict[str, Any]] = []
    bundle_warnings: list[str] = []
    for upload in uploads:
        file_name = str(upload.get("file_name") or "").strip()
        raw_bytes = bytes(upload.get("raw_bytes") or b"")
        if not file_name or not raw_bytes:
            continue
        bundle_layout = _guess_bundle_layout(file_name=file_name, fallback_layout=selected_layout)
        try:
            parse_result = parse_layout_rows(
                bundle_layout,
                raw_bytes,
                file_name=file_name,
                format_hint=format_hint,
                delimiter=delimiter,
                json_record_path=json_record_path,
                xml_record_path=xml_record_path,
                xml_record_tag=xml_record_tag,
                strict_layout=False,
                source_target_mapping={},
                dynamic_field_catalog=dynamic_field_catalog,
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
            resolved_record_selector = str(parse_result.get("resolved_record_selector") or "").strip()
            parser_warnings = list(parse_result.get("warnings") or [])
            preview_rows_full = build_preview_rows(
                repo,
                bundle_layout,
                parsed_rows,
                source_rows=source_rows,
                source_target_mapping=resolved_source_target_mapping,
                mapping_profile_id="",
                resolved_record_selector=resolved_record_selector,
            )
        except Exception as exc:
            bundle_warnings.append(f"{file_name}: parse failed ({exc})")
            continue

        import_job_id, staged_row_count, staging_warning = stage_import_preview(
            repo,
            layout_key=bundle_layout,
            source_system=source_system,
            source_object=source_object or "bundle_upload",
            file_name=file_name,
            file_type=str(file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""),
            detected_format=effective_format,
            parser_options=parser_options,
            preview_rows=preview_rows_full,
            stage_area_rows=stage_area_rows,
            actor_user_principal=user.user_principal,
        )
        if staging_warning:
            parser_warnings.append(staging_warning)

        bundle_files.append(
            {
                "layout_key": bundle_layout,
                "file_name": file_name,
                "detected_format": detected_format,
                "effective_format": effective_format,
                "parser_options": parser_options,
                "parser_warnings": parser_warnings,
                "import_job_id": import_job_id,
                "staged_row_count": int(staged_row_count or 0),
                "source_rows": source_rows,
                "source_fields": source_fields,
                "source_target_mapping": resolved_source_target_mapping,
                "field_mapping": resolved_field_mapping,
                "stage_area_rows": stage_area_rows,
                "resolved_record_selector": resolved_record_selector,
                "selected_mapping_profile_id": "",
                "selected_mapping_profile_name": "",
                "rows": preview_rows_full,
            }
        )

    if not bundle_files:
        add_flash(request, "No valid files were parsed from the upload bundle.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    selected_bundle_index = 0
    selected_bundle_file = bundle_files[selected_bundle_index]
    bundle_summaries, bundle_totals = _bundle_file_summaries(bundle_files)
    bundle_layout = safe_layout(str(selected_bundle_file.get("layout_key") or "vendors"))
    source_fields = list(selected_bundle_file.get("source_fields") or [])
    available_profiles = load_mapping_profiles(repo, user_principal=user.user_principal, layout_key=bundle_layout)
    compatible = compatible_profiles(
        profiles=available_profiles,
        file_format=str(selected_bundle_file.get("effective_format") or ""),
        source_fields=source_fields,
    )

    preview_payload = {
        "is_bundle": True,
        "bundle_files": bundle_files,
        "bundle_selected_index": selected_bundle_index,
        "bundle_warnings": bundle_warnings,
        "layout_key": bundle_layout,
        "source_system": source_system,
        "source_object": source_object,
        "source_file_name": str(selected_bundle_file.get("file_name") or ""),
        "flow_mode": "wizard",
        "detected_format": str(selected_bundle_file.get("detected_format") or ""),
        "effective_format": str(selected_bundle_file.get("effective_format") or ""),
        "parser_options": dict(selected_bundle_file.get("parser_options") or {}),
        "parser_warnings": list(selected_bundle_file.get("parser_warnings") or []),
        "import_job_id": str(selected_bundle_file.get("import_job_id") or ""),
        "source_rows": list(selected_bundle_file.get("source_rows") or []),
        "source_fields": source_fields,
        "source_target_mapping": dict(selected_bundle_file.get("source_target_mapping") or {}),
        "field_mapping": dict(selected_bundle_file.get("field_mapping") or {}),
        "stage_area_rows": dict(selected_bundle_file.get("stage_area_rows") or {}),
        "rows": list(selected_bundle_file.get("rows") or []),
        "selected_mapping_profile_id": str(selected_bundle_file.get("selected_mapping_profile_id") or ""),
        "selected_mapping_profile_name": str(selected_bundle_file.get("selected_mapping_profile_name") or ""),
    }
    preview_token = save_preview_payload(preview_payload)
    selected_preview_rows_full = list(selected_bundle_file.get("rows") or [])
    preview_rows = selected_preview_rows_full[:IMPORT_PREVIEW_RENDER_LIMIT]
    preview_total_rows = len(selected_preview_rows_full)
    preview_hidden_count = max(0, preview_total_rows - len(preview_rows))

    parser_warnings = list(selected_bundle_file.get("parser_warnings") or [])
    parser_warnings.extend(bundle_warnings)
    context_payload = render_context(
        selected_layout=bundle_layout,
        selected_flow_mode="wizard",
        selected_source_system=source_system,
        source_object=source_object,
        source_file_name=str(selected_bundle_file.get("file_name") or ""),
        detected_file_type=str(selected_bundle_file.get("detected_format") or ""),
        effective_file_type=str(selected_bundle_file.get("effective_format") or ""),
        parser_options=dict(selected_bundle_file.get("parser_options") or {}),
        parser_warnings=parser_warnings,
        staging_job_id=str(selected_bundle_file.get("import_job_id") or ""),
        staged_row_count=int(selected_bundle_file.get("staged_row_count") or 0),
        preview_token=preview_token,
        preview_rows=preview_rows,
        preview_total_rows=preview_total_rows,
        preview_hidden_count=preview_hidden_count,
        source_field_map=source_fields,
        selected_source_target_mapping=dict(selected_bundle_file.get("source_target_mapping") or {}),
        dynamic_field_catalog=dynamic_field_catalog,
        mapping_profiles=_decorate_mapping_profiles(
            profiles=available_profiles,
            compatible=compatible,
        ),
        selected_mapping_profile_id=str(selected_bundle_file.get("selected_mapping_profile_id") or ""),
        import_reason="",
    )
    context_payload.update(
        {
            "bundle_mode": True,
            "bundle_files": bundle_summaries,
            "bundle_totals": bundle_totals,
            "bundle_selected_index": selected_bundle_index,
        }
    )
    context = imports_module.base_template_context(
        request,
        user,
        title="Data Imports",
        active_nav="imports",
        extra=context_payload,
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
    dynamic_field_catalog = import_dynamic_field_catalog(repo)
    if bool(payload.get("is_bundle")):
        bundle_files_payload = [dict(item) for item in list(payload.get("bundle_files") or [])]
        if not bundle_files_payload:
            add_flash(request, "Bundle preview expired. Upload files again.", "error")
            return RedirectResponse(url="/imports", status_code=303)

        selected_bundle_index = int(form.get("bundle_file_index", payload.get("bundle_selected_index", 0)) or 0)
        if selected_bundle_index < 0 or selected_bundle_index >= len(bundle_files_payload):
            selected_bundle_index = 0
        selected_bundle_file = dict(bundle_files_payload[selected_bundle_index])

        layout_key = safe_layout(str(selected_bundle_file.get("layout_key") or "vendors"))
        flow_mode = "wizard"
        source_system = safe_source_system(str(payload.get("source_system") or "spreadsheet_manual"))
        source_object = str(payload.get("source_object") or "").strip()
        source_file_name = str(selected_bundle_file.get("file_name") or "").strip()
        detected_file_type = str(selected_bundle_file.get("detected_format") or "").strip()
        effective_file_type = str(selected_bundle_file.get("effective_format") or "").strip()
        parser_options = dict(selected_bundle_file.get("parser_options") or {})
        parser_warnings = list(selected_bundle_file.get("parser_warnings") or [])
        source_rows = list(selected_bundle_file.get("source_rows") or [])
        source_fields = list(selected_bundle_file.get("source_fields") or [])
        if not source_rows or not source_fields:
            add_flash(request, "Source preview metadata is unavailable for selected bundle file. Upload the file again.", "error")
            return RedirectResponse(url="/imports", status_code=303)

        available_profiles = load_mapping_profiles(repo, user_principal=user.user_principal, layout_key=layout_key)
        selected_mapping_profile_id = str(
            form.get("mapping_profile_id", selected_bundle_file.get("selected_mapping_profile_id", ""))
            or ""
        ).strip()
        selected_profile = find_profile_by_id(available_profiles, selected_mapping_profile_id)
        requested_source_target_mapping = dict(selected_bundle_file.get("source_target_mapping") or {})
        if selected_profile is not None:
            requested_source_target_mapping.update(_profile_source_target_mapping(selected_profile))
        requested_source_target_mapping.update(_source_target_mapping_from_form(form))

        resolved_source_target_mapping = resolve_source_target_mapping(
            source_fields=source_fields,
            requested_mapping=requested_source_target_mapping,
            dynamic_field_catalog=dynamic_field_catalog,
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
        mapped_rows_for_preview: list[dict[str, str]] = []
        for row in source_rows:
            out_row: dict[str, str] = {}
            for field, source_key in resolved_field_mapping.items():
                out_row[str(field)] = str(row.get(str(source_key), "") or "").strip() if source_key else ""
            out_row["_line"] = str(row.get("_line") or "")
            mapped_rows_for_preview.append(out_row)
        preview_rows_full = build_preview_rows(
            repo,
            layout_key,
            mapped_rows_for_preview,
            source_rows=source_rows,
            source_target_mapping=resolved_source_target_mapping,
            mapping_profile_id=selected_mapping_profile_id,
            resolved_record_selector=str(selected_bundle_file.get("resolved_record_selector") or ""),
        )
        compatible = compatible_profiles(
            profiles=available_profiles,
            file_format=effective_file_type,
            source_fields=source_fields,
        )

        profile_name_to_save = str(form.get("mapping_profile_name", "") or "").strip()
        mapping_profile_saved = ""
        if profile_name_to_save:
            if not _can_manage_mapping_profiles(user):
                add_flash(request, "Only admins can create or edit shared mapping profiles.", "error")
            else:
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
            source_object=source_object or "bundle_upload",
            file_name=source_file_name,
            file_type=str(source_file_name.rsplit(".", 1)[-1].lower() if "." in source_file_name else ""),
            detected_format=effective_file_type,
            parser_options=parser_options,
            preview_rows=preview_rows_full,
            stage_area_rows=stage_area_rows,
            actor_user_principal=user.user_principal,
        )
        if staging_warning:
            parser_warnings.append(staging_warning)

        selected_bundle_file["import_job_id"] = import_job_id
        selected_bundle_file["staged_row_count"] = staged_row_count
        selected_bundle_file["field_mapping"] = resolved_field_mapping
        selected_bundle_file["source_target_mapping"] = resolved_source_target_mapping
        selected_bundle_file["stage_area_rows"] = stage_area_rows
        selected_bundle_file["selected_mapping_profile_id"] = selected_mapping_profile_id
        selected_bundle_file["selected_mapping_profile_name"] = str(
            profile_name_to_save
            or (find_profile_by_id(available_profiles, selected_mapping_profile_id) or {}).get("profile_name")
            or ""
        )
        selected_bundle_file["rows"] = preview_rows_full
        selected_bundle_file["parser_warnings"] = parser_warnings
        bundle_files_payload[selected_bundle_index] = selected_bundle_file

        bundle_summaries, bundle_totals = _bundle_file_summaries(bundle_files_payload)
        next_payload = dict(payload)
        next_payload["bundle_files"] = bundle_files_payload
        next_payload["bundle_selected_index"] = selected_bundle_index
        next_payload["layout_key"] = layout_key
        next_payload["source_file_name"] = source_file_name
        next_payload["detected_format"] = detected_file_type
        next_payload["effective_format"] = effective_file_type
        next_payload["parser_options"] = parser_options
        next_payload["parser_warnings"] = parser_warnings
        next_payload["import_job_id"] = import_job_id
        next_payload["source_rows"] = source_rows
        next_payload["source_fields"] = source_fields
        next_payload["source_target_mapping"] = resolved_source_target_mapping
        next_payload["field_mapping"] = resolved_field_mapping
        next_payload["stage_area_rows"] = stage_area_rows
        next_payload["selected_mapping_profile_id"] = selected_mapping_profile_id
        next_payload["selected_mapping_profile_name"] = str(selected_bundle_file.get("selected_mapping_profile_name") or "")
        next_payload["rows"] = preview_rows_full
        next_token = save_preview_payload(next_payload)
        discard_preview_payload(preview_token)

        preview_rows = preview_rows_full[:IMPORT_PREVIEW_RENDER_LIMIT]
        preview_total_rows = len(preview_rows_full)
        preview_hidden_count = max(0, preview_total_rows - len(preview_rows))
        context_payload = render_context(
            selected_layout=layout_key,
            selected_flow_mode=flow_mode,
            selected_source_system=source_system,
            source_object=source_object,
            source_file_name=source_file_name,
            detected_file_type=detected_file_type,
            effective_file_type=effective_file_type,
            parser_options=parser_options,
            parser_warnings=parser_warnings + list(payload.get("bundle_warnings") or []),
            staging_job_id=import_job_id,
            staged_row_count=int(staged_row_count or 0),
            staging_warning=staging_warning,
            preview_token=next_token,
            preview_rows=preview_rows,
            preview_total_rows=preview_total_rows,
            preview_hidden_count=preview_hidden_count,
            source_field_map=source_fields,
            selected_source_target_mapping=resolved_source_target_mapping,
            dynamic_field_catalog=dynamic_field_catalog,
            mapping_profiles=_decorate_mapping_profiles(
                profiles=available_profiles,
                compatible=compatible,
            ),
            selected_mapping_profile_id=selected_mapping_profile_id,
            mapping_profile_saved=mapping_profile_saved,
            import_reason="",
        )
        context_payload.update(
            {
                "bundle_mode": True,
                "bundle_files": bundle_summaries,
                "bundle_totals": bundle_totals,
                "bundle_selected_index": selected_bundle_index,
            }
        )
        context = imports_module.base_template_context(
            request,
            user,
            title="Data Imports",
            active_nav="imports",
            extra=context_payload,
        )
        return request.app.state.templates.TemplateResponse(request, "imports.html", context)

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
    selected_mapping_profile_id = str(form.get("mapping_profile_id", payload.get("selected_mapping_profile_id", "")) or "").strip()
    selected_profile = find_profile_by_id(available_profiles, selected_mapping_profile_id)
    requested_source_target_mapping = dict(payload.get("source_target_mapping") or {})
    if selected_profile is not None:
        requested_source_target_mapping.update(_profile_source_target_mapping(selected_profile))
    requested_source_target_mapping.update(_source_target_mapping_from_form(form))

    resolved_source_target_mapping = resolve_source_target_mapping(
        source_fields=source_fields,
        requested_mapping=requested_source_target_mapping,
        dynamic_field_catalog=dynamic_field_catalog,
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
    preview_rows_full = build_preview_rows(
        repo,
        layout_key,
        mapped_rows_for_preview,
        source_rows=source_rows,
        source_target_mapping=resolved_source_target_mapping,
        mapping_profile_id=selected_mapping_profile_id,
        resolved_record_selector=str(payload.get("resolved_record_selector") or ""),
    )
    compatible = compatible_profiles(
        profiles=available_profiles,
        file_format=effective_file_type,
        source_fields=source_fields,
    )

    profile_name_to_save = str(form.get("mapping_profile_name", "") or "").strip()
    mapping_profile_saved = ""
    if profile_name_to_save:
        if not _can_manage_mapping_profiles(user):
            add_flash(request, "Only admins can create or edit shared mapping profiles.", "error")
        else:
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
    next_payload["selected_mapping_profile_name"] = str(
        (find_profile_by_id(available_profiles, selected_mapping_profile_id) or {}).get("profile_name")
        or payload.get("selected_mapping_profile_name")
        or ""
    )
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
            dynamic_field_catalog=dynamic_field_catalog,
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
    dynamic_field_catalog = import_dynamic_field_catalog(repo)

    if not can_manage_imports(user):
        add_flash(request, "You do not have permission to run imports.", "error")
        return RedirectResponse(url="/dashboard", status_code=303)
    if write_blocked(user):
        add_flash(request, "Application is in locked mode. Import actions are disabled.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    form = await request.form()
    preview_token = str(form.get("preview_token", "")).strip()
    reason = str(form.get("reason", "")).strip()
    apply_mode = str(form.get("apply_mode", "apply_eligible") or "apply_eligible").strip().lower()
    if apply_mode not in {"stage_only", "apply_eligible", "reprocess"}:
        apply_mode = "apply_eligible"
    payload = load_preview_payload(preview_token)
    if payload is None:
        add_flash(request, "Import preview expired. Upload the file again.", "error")
        return RedirectResponse(url="/imports", status_code=303)

    if bool(payload.get("is_bundle")):
        bundle_files_payload = [dict(item) for item in list(payload.get("bundle_files") or [])]
        if not bundle_files_payload:
            add_flash(request, "Bundle preview expired. Upload files again.", "error")
            return RedirectResponse(url="/imports", status_code=303)

        if apply_mode == "stage_only":
            add_flash(request, "Bundle rows are staged. No core-table writes were executed.", "success")
        else:
            apply_context = ImportApplyContext(repo)
            order_rank = {"vendors": 0, "offerings": 1, "projects": 2, "invoices": 3, "payments": 4}
            ordered_files = sorted(
                list(enumerate(bundle_files_payload)),
                key=lambda item: int(order_rank.get(str(item[1].get("layout_key") or "").strip().lower(), 99)),
            )
            global_created = 0
            global_merged = 0
            global_skipped = 0
            global_failed = 0
            global_blocked = 0
            child_apply_counts: dict[str, int] = {}
            bundle_results: list[dict[str, Any]] = []

            for file_index, file_payload in ordered_files:
                file_layout = safe_layout(str(file_payload.get("layout_key") or "vendors"))
                file_rows = list(file_payload.get("rows") or [])
                file_stage_rows = {
                    str(area): list(rows or [])
                    for area, rows in dict(file_payload.get("stage_area_rows") or {}).items()
                }
                file_created = 0
                file_merged = 0
                file_skipped = 0
                file_failed = 0
                file_blocked = 0

                for preview_row in file_rows:
                    row_index = int(preview_row.get("row_index") or 0)
                    row_data = dict(preview_row.get("row_data") or {})
                    row_status = str(preview_row.get("row_status") or "").strip().lower()
                    if row_status == "error":
                        file_skipped += 1
                        if len(bundle_results) < IMPORT_RESULTS_RENDER_LIMIT:
                            bundle_results.append(
                                {
                                    "row_index": row_index,
                                    "status": "skipped",
                                    "message": f"{file_payload.get('file_name')}: skipped due to preview errors.",
                                }
                            )
                        continue

                    selected_action = str(preview_row.get("suggested_action") or "new").strip().lower()
                    if selected_action not in ALLOWED_IMPORT_ACTIONS:
                        selected_action = "new"
                    target_id = str(preview_row.get("suggested_target_id") or "").strip()
                    fallback_target_vendor_id = str(preview_row.get("suggested_target_vendor_id") or "").strip()
                    try:
                        status, message, apply_result = apply_import_row(
                            repo,
                            layout_key=file_layout,
                            row_data=row_data,
                            action=selected_action,
                            target_id=target_id,
                            fallback_target_vendor_id=fallback_target_vendor_id,
                            actor_user_principal=user.user_principal,
                            reason=reason or "bundle import",
                            apply_context=apply_context,
                        )
                        child_counts = apply_stage_area_rows_for_row(
                            repo,
                            stage_area_rows=file_stage_rows,
                            row_index=row_index,
                            selected_action=selected_action,
                            row_data=row_data,
                            fallback_target_vendor_id=fallback_target_vendor_id,
                            primary_result=apply_result,
                            actor_user_principal=user.user_principal,
                            reason=reason or "bundle import",
                            apply_context=apply_context,
                        )
                        if child_counts:
                            parts = [f"{key}={value}" for key, value in sorted(child_counts.items())]
                            message = f"{message} | child writes: {', '.join(parts)}"
                            for key, value in child_counts.items():
                                child_apply_counts[key] = int(child_apply_counts.get(key, 0)) + int(value or 0)
                        if status == "created":
                            file_created += 1
                        elif status == "merged":
                            file_merged += 1
                        else:
                            file_skipped += 1
                        if len(bundle_results) < IMPORT_RESULTS_RENDER_LIMIT:
                            bundle_results.append(
                                {
                                    "row_index": row_index,
                                    "status": status,
                                    "message": f"{file_payload.get('file_name')}: {message}",
                                }
                            )
                    except Exception as exc:
                        raw_error = str(exc)
                        lowered = raw_error.lower()
                        if "dependency" in lowered:
                            file_blocked += 1
                            file_skipped += 1
                            status_key = "blocked"
                        else:
                            file_failed += 1
                            status_key = "failed"
                        if len(bundle_results) < IMPORT_RESULTS_RENDER_LIMIT:
                            bundle_results.append(
                                {
                                    "row_index": row_index,
                                    "status": status_key,
                                    "message": f"{file_payload.get('file_name')}: {raw_error}",
                                }
                            )

                global_created += file_created
                global_merged += file_merged
                global_skipped += file_skipped
                global_failed += file_failed
                global_blocked += file_blocked
                finalize_import_staging_job(
                    repo,
                    import_job_id=str(file_payload.get("import_job_id") or "").strip(),
                    created_count=file_created,
                    merged_count=file_merged,
                    skipped_count=file_skipped,
                    failed_count=file_failed,
                    actor_user_principal=user.user_principal,
                    error_message=(
                        "Blocked rows remain staged for dependency reprocess."
                        if file_blocked and file_failed == 0
                        else ("" if file_failed == 0 else "One or more bundle row apply operations failed.")
                    ),
                )

            if global_failed == 0:
                add_flash(
                    request,
                    (
                        "Bundle apply complete. "
                        f"created={global_created}, merged={global_merged}, skipped={global_skipped}, blocked={global_blocked}, failed={global_failed}"
                    ),
                    "success",
                )
            else:
                add_flash(
                    request,
                    (
                        "Bundle apply completed with errors. "
                        f"created={global_created}, merged={global_merged}, skipped={global_skipped}, blocked={global_blocked}, failed={global_failed}"
                    ),
                    "error",
                )
            if child_apply_counts:
                child_summary = ", ".join([f"{key}={value}" for key, value in sorted(child_apply_counts.items())])
                add_flash(request, f"Applied child entity writes: {child_summary}", "info")
            if global_blocked > 0:
                add_flash(
                    request,
                    "Blocked rows remain staged. Use 'Reprocess Blocked' after upstream dependencies are loaded.",
                    "info",
                )
            if len(bundle_results) > IMPORT_RESULTS_RENDER_LIMIT:
                hidden_results = len(bundle_results) - IMPORT_RESULTS_RENDER_LIMIT
                add_flash(
                    request,
                    f"Showing first {IMPORT_RESULTS_RENDER_LIMIT} bundle result rows. {hidden_results} additional rows were processed.",
                    "info",
                )
            payload["bundle_last_results"] = bundle_results
            preview_token = save_preview_payload(payload)

        selected_bundle_index = int(payload.get("bundle_selected_index") or 0)
        if selected_bundle_index < 0 or selected_bundle_index >= len(bundle_files_payload):
            selected_bundle_index = 0
        selected_bundle_file = dict(bundle_files_payload[selected_bundle_index])
        bundle_layout = safe_layout(str(selected_bundle_file.get("layout_key") or "vendors"))
        source_fields = list(selected_bundle_file.get("source_fields") or [])
        selected_source_target_mapping = dict(selected_bundle_file.get("source_target_mapping") or {})
        available_profiles = load_mapping_profiles(repo, user_principal=user.user_principal, layout_key=bundle_layout)
        compatible = compatible_profiles(
            profiles=available_profiles,
            file_format=str(selected_bundle_file.get("effective_format") or ""),
            source_fields=source_fields,
        )
        selected_preview_rows_full = list(selected_bundle_file.get("rows") or [])
        preview_rows = selected_preview_rows_full[:IMPORT_PREVIEW_RENDER_LIMIT]
        preview_total_rows = len(selected_preview_rows_full)
        preview_hidden_count = max(0, preview_total_rows - len(preview_rows))
        bundle_summaries, bundle_totals = _bundle_file_summaries(bundle_files_payload)
        bundle_results = list(payload.get("bundle_last_results") or [])

        context_payload = render_context(
            selected_layout=bundle_layout,
            selected_flow_mode="wizard",
            selected_source_system=safe_source_system(str(payload.get("source_system") or "spreadsheet_manual")),
            source_object=str(payload.get("source_object") or "").strip(),
            source_file_name=str(selected_bundle_file.get("file_name") or ""),
            detected_file_type=str(selected_bundle_file.get("detected_format") or ""),
            effective_file_type=str(selected_bundle_file.get("effective_format") or ""),
            parser_options=dict(selected_bundle_file.get("parser_options") or {}),
            parser_warnings=list(selected_bundle_file.get("parser_warnings") or []) + list(payload.get("bundle_warnings") or []),
            staging_job_id=str(selected_bundle_file.get("import_job_id") or ""),
            staged_row_count=int(selected_bundle_file.get("staged_row_count") or 0),
            preview_token=preview_token,
            preview_rows=preview_rows,
            preview_total_rows=preview_total_rows,
            preview_hidden_count=preview_hidden_count,
            source_field_map=source_fields,
            selected_source_target_mapping=selected_source_target_mapping,
            dynamic_field_catalog=dynamic_field_catalog,
            mapping_profiles=_decorate_mapping_profiles(
                profiles=available_profiles,
                compatible=compatible,
            ),
            selected_mapping_profile_id=str(selected_bundle_file.get("selected_mapping_profile_id") or ""),
            import_results=bundle_results[:IMPORT_RESULTS_RENDER_LIMIT],
            import_reason=reason,
        )
        context_payload.update(
            {
                "bundle_mode": True,
                "bundle_files": bundle_summaries,
                "bundle_totals": bundle_totals,
                "bundle_selected_index": selected_bundle_index,
            }
        )
        context = imports_module.base_template_context(
            request,
            user,
            title="Data Imports",
            active_nav="imports",
            extra=context_payload,
        )
        return request.app.state.templates.TemplateResponse(request, "imports.html", context)

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
            dynamic_field_catalog=import_dynamic_field_catalog(repo),
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

