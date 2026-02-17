SELECT
  data_flow_id,
  offering_id,
  vendor_id,
  direction,
  flow_name,
  method,
  data_description,
  endpoint_details,
  identifiers,
  reporting_layer,
  creation_process,
  delivery_process,
  owner_user_principal,
  notes,
  active_flag,
  created_at,
  created_by,
  updated_at,
  updated_by
FROM {app_offering_data_flow}
WHERE data_flow_id = %s
  AND offering_id = %s
  AND vendor_id = %s
LIMIT 1

