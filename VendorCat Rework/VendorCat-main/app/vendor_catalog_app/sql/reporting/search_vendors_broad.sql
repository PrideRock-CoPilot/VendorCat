SELECT DISTINCT
  v.vendor_id,
  v.legal_name,
  v.display_name,
  v.lifecycle_state,
  v.owner_org_id,
  v.risk_tier,
  v.updated_at
FROM {core_vendor} v
WHERE (
  lower(v.vendor_id) LIKE lower(%s)
  OR lower(coalesce(v.legal_name, '')) LIKE lower(%s)
  OR lower(coalesce(v.display_name, '')) LIKE lower(%s)
  OR lower(coalesce(v.owner_org_id, '')) LIKE lower(%s)
  OR lower(coalesce(v.risk_tier, '')) LIKE lower(%s)
  OR lower(coalesce(v.source_system, '')) LIKE lower(%s)
  OR lower(coalesce(v.source_record_id, '')) LIKE lower(%s)
  OR lower(coalesce(v.source_batch_id, '')) LIKE lower(%s)
  OR EXISTS (
    SELECT 1
    FROM {core_vendor_offering} o
    WHERE o.vendor_id = v.vendor_id
      AND (
        lower(o.offering_id) LIKE lower(%s)
        OR lower(coalesce(o.offering_name, '')) LIKE lower(%s)
        OR lower(coalesce(o.offering_type, '')) LIKE lower(%s)
        OR lower(coalesce(o.business_unit, '')) LIKE lower(%s)
        OR lower(coalesce(o.service_type, '')) LIKE lower(%s)
      )
  )
  OR EXISTS (
    SELECT 1
    FROM {core_contract} c
    WHERE c.vendor_id = v.vendor_id
      AND (
        lower(c.contract_id) LIKE lower(%s)
        OR lower(coalesce(c.contract_number, '')) LIKE lower(%s)
        OR lower(coalesce(c.contract_status, '')) LIKE lower(%s)
      )
  )
  OR EXISTS (
    SELECT 1
    FROM {core_vendor_business_owner} bo
    WHERE bo.vendor_id = v.vendor_id
      AND (
        lower(coalesce(bo.owner_user_principal, '')) LIKE lower(%s)
        OR lower(coalesce(bo.owner_role, '')) LIKE lower(%s)
      )
  )
  OR EXISTS (
    SELECT 1
    FROM {core_offering_business_owner} obo
    INNER JOIN {core_vendor_offering} o2
      ON obo.offering_id = o2.offering_id
    WHERE o2.vendor_id = v.vendor_id
      AND (
        lower(coalesce(obo.owner_user_principal, '')) LIKE lower(%s)
        OR lower(coalesce(obo.owner_role, '')) LIKE lower(%s)
      )
  )
  OR EXISTS (
    SELECT 1
    FROM {core_vendor_contact} vc
    WHERE vc.vendor_id = v.vendor_id
      AND (
        lower(coalesce(vc.full_name, '')) LIKE lower(%s)
        OR lower(coalesce(vc.email, '')) LIKE lower(%s)
        OR lower(coalesce(vc.contact_type, '')) LIKE lower(%s)
        OR lower(coalesce(vc.phone, '')) LIKE lower(%s)
      )
  )
  OR EXISTS (
    SELECT 1
    FROM {core_offering_contact} oc
    INNER JOIN {core_vendor_offering} o3
      ON oc.offering_id = o3.offering_id
    WHERE o3.vendor_id = v.vendor_id
      AND (
        lower(coalesce(oc.full_name, '')) LIKE lower(%s)
        OR lower(coalesce(oc.email, '')) LIKE lower(%s)
        OR lower(coalesce(oc.contact_type, '')) LIKE lower(%s)
        OR lower(coalesce(oc.phone, '')) LIKE lower(%s)
      )
  )
  OR EXISTS (
    SELECT 1
    FROM {core_vendor_demo} d
    WHERE d.vendor_id = v.vendor_id
      AND (
        lower(d.demo_id) LIKE lower(%s)
        OR lower(coalesce(d.offering_id, '')) LIKE lower(%s)
        OR lower(coalesce(d.selection_outcome, '')) LIKE lower(%s)
        OR lower(coalesce(d.non_selection_reason_code, '')) LIKE lower(%s)
        OR lower(coalesce(d.notes, '')) LIKE lower(%s)
      )
  )
  OR EXISTS (
    SELECT 1
    FROM {app_project} p
    WHERE p.vendor_id = v.vendor_id
      AND coalesce(p.active_flag, true) = true
      AND (
        lower(p.project_id) LIKE lower(%s)
        OR lower(coalesce(p.project_name, '')) LIKE lower(%s)
        OR lower(coalesce(p.project_type, '')) LIKE lower(%s)
        OR lower(coalesce(p.status, '')) LIKE lower(%s)
        OR lower(coalesce(p.owner_principal, '')) LIKE lower(%s)
        OR lower(coalesce(p.description, '')) LIKE lower(%s)
      )
  )
)
{state_clause}
ORDER BY v.display_name
LIMIT 250

