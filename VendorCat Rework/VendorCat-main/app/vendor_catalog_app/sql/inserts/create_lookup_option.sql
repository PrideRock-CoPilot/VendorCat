INSERT INTO {app_lookup_option}
  (
    option_id,
    lookup_type,
    option_code,
    option_label,
    sort_order,
    active_flag,
    valid_from_ts,
    valid_to_ts,
    is_current,
    deleted_flag,
    updated_at,
    updated_by
  )
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
