INSERT INTO {app_import_stage_row} (
  import_stage_row_id,
  import_job_id,
  row_index,
  line_number,
  row_payload_json,
  suggested_action,
  suggested_target_id,
  created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
