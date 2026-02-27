SELECT
  v.vendor_id,
  COALESCE(v.display_name, v.legal_name) AS vendor_name,
  v.lifecycle_state,
  v.owner_org_id,
  v.risk_tier,
  COUNT(DISTINCT o.offering_id) AS offering_count,
  GROUP_CONCAT(DISTINCT CASE WHEN LOWER(COALESCE(o.lifecycle_state, '')) = 'active' THEN o.business_unit END) AS active_lobs,
  GROUP_CONCAT(DISTINCT CASE WHEN LOWER(COALESCE(o.lifecycle_state, '')) = 'active' THEN o.service_type END) AS active_service_types,
  COUNT(DISTINCT CASE WHEN c.contract_status = 'active' THEN c.contract_id END) AS active_contract_count,
  COUNT(DISTINCT CASE WHEN d.selection_outcome = 'selected' THEN d.demo_id END) AS demos_selected,
  COUNT(DISTINCT CASE WHEN d.selection_outcome IN ('not_selected', 'deferred') THEN d.demo_id END) AS demos_not_selected
FROM core_vendor v
LEFT JOIN core_vendor_offering o ON o.vendor_id = v.vendor_id
LEFT JOIN core_contract c ON c.vendor_id = v.vendor_id
LEFT JOIN core_vendor_demo d ON d.vendor_id = v.vendor_id
GROUP BY v.vendor_id, COALESCE(v.display_name, v.legal_name), v.lifecycle_state, v.owner_org_id, v.risk_tier
ORDER BY vendor_name;

