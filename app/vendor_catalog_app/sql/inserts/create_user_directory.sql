INSERT INTO {app_user_directory}
  (
    user_id,
    login_identifier,
    email,
    network_id,
    first_name,
    last_name,
    display_name,
    active_flag,
    created_at,
    updated_at,
    last_seen_at
  )
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
