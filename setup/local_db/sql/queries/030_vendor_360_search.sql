-- Replace ? with a search term. This query supports broad search across vendor, offering, contract, and owners.
SELECT DISTINCT
  v.vendor_id,
  COALESCE(v.display_name, v.legal_name) AS vendor_name,
  v.lifecycle_state,
  v.owner_org_id,
  v.risk_tier,
  v.updated_at
FROM core_vendor v
LEFT JOIN core_vendor_offering o ON o.vendor_id = v.vendor_id
LEFT JOIN core_contract c ON c.vendor_id = v.vendor_id
LEFT JOIN core_vendor_business_owner vbo ON vbo.vendor_id = v.vendor_id
LEFT JOIN core_offering_business_owner obo ON obo.offering_id = o.offering_id
LEFT JOIN app_project p ON p.vendor_id = v.vendor_id AND COALESCE(p.active_flag, 1) = 1
WHERE
  LOWER(COALESCE(v.vendor_id, '')) LIKE '%' || LOWER(?) || '%'
  OR LOWER(COALESCE(v.legal_name, '')) LIKE '%' || LOWER(?) || '%'
  OR LOWER(COALESCE(v.display_name, '')) LIKE '%' || LOWER(?) || '%'
  OR LOWER(COALESCE(o.offering_id, '')) LIKE '%' || LOWER(?) || '%'
  OR LOWER(COALESCE(o.offering_name, '')) LIKE '%' || LOWER(?) || '%'
  OR LOWER(COALESCE(c.contract_id, '')) LIKE '%' || LOWER(?) || '%'
  OR LOWER(COALESCE(c.contract_number, '')) LIKE '%' || LOWER(?) || '%'
  OR LOWER(COALESCE(vbo.owner_user_principal, '')) LIKE '%' || LOWER(?) || '%'
  OR LOWER(COALESCE(obo.owner_user_principal, '')) LIKE '%' || LOWER(?) || '%'
  OR LOWER(COALESCE(p.project_name, '')) LIKE '%' || LOWER(?) || '%'
ORDER BY vendor_name;
