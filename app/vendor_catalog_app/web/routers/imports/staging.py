from __future__ import annotations

from typing import Any


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
        return import_job_id, staged_count, ""
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
