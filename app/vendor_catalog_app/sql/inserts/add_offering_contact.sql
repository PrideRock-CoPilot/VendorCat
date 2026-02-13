INSERT INTO {core_offering_contact}
  (offering_contact_id, offering_id, contact_type, full_name, email, phone, active_flag, updated_at, updated_by)
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s, %s)
