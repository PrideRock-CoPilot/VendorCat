DELETE FROM {app_offering_data_flow}
WHERE data_flow_id = %s
  AND offering_id = %s
  AND vendor_id = %s

