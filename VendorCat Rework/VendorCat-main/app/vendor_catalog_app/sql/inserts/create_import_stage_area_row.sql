INSERT INTO {area_stage_table} (
  import_stage_area_row_id,
  import_job_id,
  row_index,
  line_number,
  area_payload_json,
  created_at
) VALUES (?, ?, ?, ?, ?, ?);
