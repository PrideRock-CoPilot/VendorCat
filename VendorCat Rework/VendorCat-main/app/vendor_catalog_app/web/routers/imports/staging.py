from __future__ import annotations

from typing import Any

from vendor_catalog_app.core.repository_constants import (
    LOOKUP_TYPE_COMPLIANCE_CATEGORY,
    LOOKUP_TYPE_CONTACT_TYPE,
    LOOKUP_TYPE_GL_CATEGORY,
    LOOKUP_TYPE_LIFECYCLE_STATE,
    LOOKUP_TYPE_OFFERING_BUSINESS_UNIT,
    LOOKUP_TYPE_OFFERING_SERVICE_TYPE,
    LOOKUP_TYPE_OFFERING_TYPE,
    LOOKUP_TYPE_OWNER_ORGANIZATION,
    LOOKUP_TYPE_OWNER_ROLE,
    LOOKUP_TYPE_RISK_TIER,
    LOOKUP_TYPE_VENDOR_CATEGORY,
)
from vendor_catalog_app.web.routers.imports.parsing import normalize_column_name

LAYOUT_PRIMARY_GOVERNED_AREA = {
    "vendors": "vendor",
    "offerings": "offering",
}

GOVERNED_LOOKUP_FIELDS: dict[str, dict[str, str]] = {
    "vendor": {
        "owner_org_id": LOOKUP_TYPE_OWNER_ORGANIZATION,
        "lifecycle_state": LOOKUP_TYPE_LIFECYCLE_STATE,
        "risk_tier": LOOKUP_TYPE_RISK_TIER,
        "vendor_category": LOOKUP_TYPE_VENDOR_CATEGORY,
        "compliance_category": LOOKUP_TYPE_COMPLIANCE_CATEGORY,
        "gl_category": LOOKUP_TYPE_GL_CATEGORY,
    },
    "offering": {
        "offering_type": LOOKUP_TYPE_OFFERING_TYPE,
        "business_unit": LOOKUP_TYPE_OFFERING_BUSINESS_UNIT,
        "service_type": LOOKUP_TYPE_OFFERING_SERVICE_TYPE,
        "lifecycle_state": LOOKUP_TYPE_LIFECYCLE_STATE,
    },
    "vendor_contact": {
        "contact_type": LOOKUP_TYPE_CONTACT_TYPE,
    },
    "offering_contact": {
        "contact_type": LOOKUP_TYPE_CONTACT_TYPE,
    },
    "vendor_owner": {
        "owner_role": LOOKUP_TYPE_OWNER_ROLE,
    },
    "offering_owner": {
        "owner_role": LOOKUP_TYPE_OWNER_ROLE,
    },
}


def _normalize_lookup_token(raw: Any) -> str:
    return normalize_column_name(str(raw or "").strip())


def _active_lookup_value_set(repo, *, lookup_type: str, cache: dict[str, set[str]]) -> set[str]:
    key = str(lookup_type or "").strip().lower()
    if key in cache:
        return cache[key]
    values: set[str] = set()
    if not key or not hasattr(repo, "list_lookup_options"):
        cache[key] = values
        return values
    try:
        rows = repo.list_lookup_options(key, active_only=True)
    except Exception:
        rows = None
    if rows is not None and not getattr(rows, "empty", True):
        for row in rows.to_dict("records"):
            option_code = _normalize_lookup_token(row.get("option_code"))
            option_label = _normalize_lookup_token(row.get("option_label"))
            if option_code:
                values.add(option_code)
            if option_label:
                values.add(option_label)
    cache[key] = values
    return values


def _collect_governed_lookup_values(
    *,
    layout_key: str,
    preview_rows: list[dict[str, Any]],
    stage_area_rows: dict[str, list[dict[str, Any]]] | None,
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    primary_area = str(LAYOUT_PRIMARY_GOVERNED_AREA.get(str(layout_key or "").strip().lower()) or "").strip()
    if primary_area:
        field_lookup_map = dict(GOVERNED_LOOKUP_FIELDS.get(primary_area) or {})
        if field_lookup_map:
            for row in list(preview_rows or []):
                row_index = int(row.get("row_index") or 0)
                row_data = dict(row.get("row_data") or {})
                for field_key, lookup_type in field_lookup_map.items():
                    raw_value = str(row_data.get(field_key) or "").strip()
                    if not raw_value:
                        continue
                    collected.append(
                        {
                            "area_key": primary_area,
                            "row_index": row_index,
                            "lookup_type": lookup_type,
                            "field_key": field_key,
                            "raw_value": raw_value,
                        }
                    )

    for area_key, rows in dict(stage_area_rows or {}).items():
        cleaned_area = str(area_key or "").strip().lower()
        field_lookup_map = dict(GOVERNED_LOOKUP_FIELDS.get(cleaned_area) or {})
        if not field_lookup_map:
            continue
        for row in list(rows or []):
            row_index = int(row.get("row_index") or 0)
            payload = dict(row.get("payload") or {})
            for field_key, lookup_type in field_lookup_map.items():
                raw_value = str(payload.get(field_key) or "").strip()
                if not raw_value:
                    continue
                collected.append(
                    {
                        "area_key": cleaned_area,
                        "row_index": row_index,
                        "lookup_type": lookup_type,
                        "field_key": field_key,
                        "raw_value": raw_value,
                    }
                )
    return collected


def _sync_import_lookup_candidates(
    repo,
    *,
    import_job_id: str,
    layout_key: str,
    preview_rows: list[dict[str, Any]],
    stage_area_rows: dict[str, list[dict[str, Any]]] | None,
    actor_user_principal: str,
) -> int:
    if (
        not hasattr(repo, "clear_import_lookup_candidates")
        or not hasattr(repo, "upsert_import_lookup_candidate")
        or not hasattr(repo, "list_lookup_options")
    ):
        return 0
    job_id = str(import_job_id or "").strip()
    if not job_id:
        return 0

    repo.clear_import_lookup_candidates(import_job_id=job_id)
    lookup_rows = _collect_governed_lookup_values(
        layout_key=layout_key,
        preview_rows=preview_rows,
        stage_area_rows=stage_area_rows,
    )
    if not lookup_rows:
        return 0

    lookup_cache: dict[str, set[str]] = {}
    created: set[tuple[int, str, str]] = set()
    pending_count = 0

    for row in lookup_rows:
        lookup_type = str(row.get("lookup_type") or "").strip().lower()
        raw_value = str(row.get("raw_value") or "").strip()
        option_code = _normalize_lookup_token(raw_value)
        if not lookup_type or not option_code:
            continue
        allowed_values = _active_lookup_value_set(repo, lookup_type=lookup_type, cache=lookup_cache)
        if option_code in allowed_values:
            continue
        row_index = int(row.get("row_index") or 0)
        dedupe_key = (row_index, lookup_type, option_code)
        if dedupe_key in created:
            continue
        repo.upsert_import_lookup_candidate(
            import_job_id=job_id,
            area_key=str(row.get("area_key") or "").strip().lower(),
            row_index=row_index,
            lookup_type=lookup_type,
            option_code=option_code,
            option_label=raw_value,
            actor_user_principal=actor_user_principal,
            status="pending",
        )
        created.add(dedupe_key)
        pending_count += 1

    return pending_count


def stage_import_preview(
    repo,
    *,
    layout_key: str,
    source_system: str,
    source_object: str,
    file_name: str,
    file_type: str,
    detected_format: str,
    parser_options: dict[str, Any],
    preview_rows: list[dict[str, Any]],
    stage_area_rows: dict[str, list[dict[str, Any]]] | None,
    actor_user_principal: str,
) -> tuple[str, int, str]:
    if not hasattr(repo, "create_import_stage_job") or not hasattr(repo, "create_import_stage_rows"):
        return "", 0, "Staging tables are not configured in this runtime."
    try:
        import_job_id = repo.create_import_stage_job(
            layout_key=layout_key,
            source_system=source_system,
            source_object=source_object or None,
            file_name=file_name or None,
            file_type=file_type or None,
            detected_format=detected_format or None,
            parser_config=parser_options,
            row_count=len(preview_rows),
            actor_user_principal=actor_user_principal,
        )
        staged_count = int(
            repo.create_import_stage_rows(
                import_job_id=import_job_id,
                preview_rows=preview_rows,
            )
            or 0
        )
        if hasattr(repo, "create_import_stage_area_rows"):
            try:
                repo.create_import_stage_area_rows(
                    import_job_id=import_job_id,
                    stage_area_rows=dict(stage_area_rows or {}),
                )
            except Exception:
                # Main stage rows are authoritative for preview/apply.
                pass
        staging_warning = ""
        try:
            pending_lookup_count = _sync_import_lookup_candidates(
                repo,
                import_job_id=import_job_id,
                layout_key=layout_key,
                preview_rows=preview_rows,
                stage_area_rows=stage_area_rows,
                actor_user_principal=actor_user_principal,
            )
            if pending_lookup_count > 0:
                staging_warning = (
                    f"{pending_lookup_count} governed lookup value(s) were staged for steward approval. "
                    "Approve or reject candidates before apply."
                )
        except Exception:
            staging_warning = ""
        return import_job_id, staged_count, staging_warning
    except Exception as exc:
        return "", 0, f"Could not persist staging rows: {exc}"


def finalize_import_staging_job(
    repo,
    *,
    import_job_id: str,
    created_count: int,
    merged_count: int,
    skipped_count: int,
    failed_count: int,
    actor_user_principal: str,
    error_message: str = "",
) -> None:
    if not import_job_id:
        return
    if not hasattr(repo, "finalize_import_stage_job"):
        return
    try:
        repo.finalize_import_stage_job(
            import_job_id=import_job_id,
            created_count=created_count,
            merged_count=merged_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            actor_user_principal=actor_user_principal,
            error_message=error_message or None,
        )
    except Exception:
        # Import apply is primary; staging finalization should not block user action.
        return
