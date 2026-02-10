SELECT change_request_id, vendor_id, requestor_user_principal, change_type, requested_payload_json, status, submitted_at, updated_at
FROM {app_vendor_change_request}
{where_clause}
ORDER BY submitted_at DESC
