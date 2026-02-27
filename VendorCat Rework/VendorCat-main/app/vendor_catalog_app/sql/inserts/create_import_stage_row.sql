INSERT INTO {app_import_stage_row} (
  import_stage_row_id,
  import_job_id,
  row_index,
  line_number,
  area_key,
  source_group_key,
  row_payload_json,
  suggested_action,
  suggested_target_id,
  decision_action,
  decision_target_id,
  decision_payload_json,
  decision_updated_at,
  decision_updated_by,
  created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
