UPDATE {app_vendor_change_request}
SET status = %s,
    updated_at = %s
WHERE change_request_id = %s
