UPDATE {app_import_job}
SET status = ?,
    created_count = ?,
    merged_count = ?,
    skipped_count = ?,
    failed_count = ?,
    error_message = ?,
    applied_at = ?,
    applied_by = ?
WHERE import_job_id = ?
