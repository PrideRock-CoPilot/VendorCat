INSERT INTO {app_vendor_change_request}
  (change_request_id, vendor_id, requestor_user_principal, change_type, requested_payload_json, status, submitted_at, updated_at)
VALUES
  (%s, %s, %s, %s, %s, %s, %s, %s)
