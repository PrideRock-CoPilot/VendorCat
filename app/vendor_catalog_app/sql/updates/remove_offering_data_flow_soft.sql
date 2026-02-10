UPDATE {app_offering_data_flow}
SET active_flag = false,
    updated_at = %s,
    updated_by = %s
WHERE data_flow_id = %s
  AND offering_id = %s
  AND vendor_id = %s

