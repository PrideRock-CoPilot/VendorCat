UPDATE {app_offering_data_flow}
SET {set_clause},
    updated_at = %s,
    updated_by = %s
WHERE data_flow_id = %s
  AND offering_id = %s
  AND vendor_id = %s
