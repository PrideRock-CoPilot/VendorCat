SELECT
  (SELECT COUNT(*) FROM {core_vendor} WHERE lifecycle_state = 'active') AS active_vendors,
  (SELECT COUNT(*) FROM {core_vendor_offering} WHERE lifecycle_state = 'active') AS active_offerings,
  (SELECT COUNT(*) FROM {core_vendor_demo}) AS demos_logged,
  (SELECT COUNT(*) FROM {core_contract_event} WHERE event_type = 'contract_cancelled') AS cancelled_contracts
