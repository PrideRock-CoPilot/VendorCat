PRAGMA foreign_keys = ON;

DROP VIEW IF EXISTS vw_reporting_core_vendor;
CREATE VIEW vw_reporting_core_vendor AS
SELECT
  v.vendor_id,
  v.legal_name,
  v.display_name,
  coalesce(ls.lifecycle_state_code, v.lifecycle_state_id) AS lifecycle_state,
  coalesce(bu.business_unit_name, oo.owner_organization_name, v.primary_business_unit_id, v.primary_owner_organization_id) AS owner_org_id,
  coalesce(rt.risk_tier_code, v.risk_tier_id) AS risk_tier,
  v.source_system,
  CAST(NULL AS TEXT) AS source_record_id,
  CAST(NULL AS TEXT) AS source_batch_id,
  CAST(NULL AS TEXT) AS source_extract_ts,
  CAST(NULL AS TEXT) AS merged_into_vendor_id,
  CAST(NULL AS TEXT) AS merged_at,
  CAST(NULL AS TEXT) AS merged_by,
  CAST(NULL AS TEXT) AS merge_reason,
  vc.vendor_category_code AS vendor_category,
  cc.compliance_category_code AS compliance_category,
  gc.gl_category_code AS gl_category,
  coalesce(v.delegated_vendor_flag, 0) AS delegated_vendor_flag,
  coalesce(v.health_care_vendor_flag, 0) AS health_care_vendor_flag,
  v.created_at,
  v.updated_at,
  v.updated_by
FROM vendor v
LEFT JOIN lkp_lifecycle_state ls
  ON ls.lifecycle_state_id = v.lifecycle_state_id
LEFT JOIN lkp_risk_tier rt
  ON rt.risk_tier_id = v.risk_tier_id
LEFT JOIN lkp_business_unit bu
  ON bu.business_unit_id = v.primary_business_unit_id
LEFT JOIN lkp_owner_organization oo
  ON oo.owner_organization_id = v.primary_owner_organization_id
LEFT JOIN lkp_vendor_category vc
  ON vc.vendor_category_id = v.vendor_category_id
LEFT JOIN lkp_compliance_category cc
  ON cc.compliance_category_id = v.compliance_category_id
LEFT JOIN lkp_gl_category gc
  ON gc.gl_category_id = v.gl_category_id
UNION ALL
SELECT
  cv.vendor_id,
  cv.legal_name,
  cv.display_name,
  cv.lifecycle_state,
  cv.owner_org_id,
  cv.risk_tier,
  cv.source_system,
  cv.source_record_id,
  cv.source_batch_id,
  cv.source_extract_ts,
  cv.merged_into_vendor_id,
  cv.merged_at,
  cv.merged_by,
  cv.merge_reason,
  CAST(NULL AS TEXT) AS vendor_category,
  CAST(NULL AS TEXT) AS compliance_category,
  CAST(NULL AS TEXT) AS gl_category,
  CAST(NULL AS INTEGER) AS delegated_vendor_flag,
  CAST(NULL AS INTEGER) AS health_care_vendor_flag,
  CAST(NULL AS TEXT) AS created_at,
  cv.updated_at,
  cv.updated_by
FROM core_vendor cv
WHERE NOT EXISTS (
  SELECT 1
  FROM vendor v
  WHERE v.vendor_id = cv.vendor_id
);

DROP VIEW IF EXISTS vw_reporting_core_vendor_offering;
CREATE VIEW vw_reporting_core_vendor_offering AS
SELECT
  o.offering_id,
  o.vendor_id,
  o.offering_name,
  CAST(NULL AS TEXT) AS offering_type,
  coalesce(bu.business_unit_name, o.primary_business_unit_id) AS business_unit,
  coalesce(st.service_type_name, o.primary_service_type_id) AS service_type,
  coalesce(ls.lifecycle_state_code, o.lifecycle_state_id) AS lifecycle_state,
  o.criticality_tier,
  o.created_at,
  o.updated_at,
  o.updated_by
FROM offering o
LEFT JOIN lkp_business_unit bu
  ON bu.business_unit_id = o.primary_business_unit_id
LEFT JOIN lkp_service_type st
  ON st.service_type_id = o.primary_service_type_id
LEFT JOIN lkp_lifecycle_state ls
  ON ls.lifecycle_state_id = o.lifecycle_state_id
UNION ALL
SELECT
  co.offering_id,
  co.vendor_id,
  co.offering_name,
  co.offering_type,
  co.business_unit,
  co.service_type,
  co.lifecycle_state,
  co.criticality_tier,
  CAST(NULL AS TEXT) AS created_at,
  co.updated_at,
  co.updated_by
FROM core_vendor_offering co
WHERE NOT EXISTS (
  SELECT 1
  FROM offering o
  WHERE o.offering_id = co.offering_id
);

DROP VIEW IF EXISTS vw_reporting_core_vendor_business_owner;
CREATE VIEW vw_reporting_core_vendor_business_owner AS
SELECT
  voa.assignment_id AS vendor_owner_id,
  voa.vendor_id,
  voa.user_principal AS owner_user_principal,
  coalesce(orr.owner_role_code, voa.owner_role_id) AS owner_role,
  coalesce(voa.active_flag, 1) AS active_flag,
  voa.created_at,
  coalesce(voa.ended_at, voa.created_at) AS updated_at,
  CAST(NULL AS TEXT) AS updated_by
FROM vendor_owner_assignment voa
LEFT JOIN lkp_owner_role orr
  ON orr.owner_role_id = voa.owner_role_id
UNION ALL
SELECT
  cbo.vendor_owner_id,
  cbo.vendor_id,
  cbo.owner_user_principal,
  cbo.owner_role,
  cbo.active_flag,
  CAST(NULL AS TEXT) AS created_at,
  cbo.updated_at,
  cbo.updated_by
FROM core_vendor_business_owner cbo
WHERE NOT EXISTS (
  SELECT 1
  FROM vendor_owner_assignment voa
  WHERE voa.assignment_id = cbo.vendor_owner_id
);

DROP VIEW IF EXISTS vw_reporting_core_offering_business_owner;
CREATE VIEW vw_reporting_core_offering_business_owner AS
SELECT
  ooa.assignment_id AS offering_owner_id,
  ooa.offering_id,
  ooa.user_principal AS owner_user_principal,
  coalesce(orr.owner_role_code, ooa.owner_role_id) AS owner_role,
  coalesce(ooa.active_flag, 1) AS active_flag,
  ooa.created_at,
  coalesce(ooa.ended_at, ooa.created_at) AS updated_at,
  CAST(NULL AS TEXT) AS updated_by
FROM offering_owner_assignment ooa
LEFT JOIN lkp_owner_role orr
  ON orr.owner_role_id = ooa.owner_role_id
UNION ALL
SELECT
  cbo.offering_owner_id,
  cbo.offering_id,
  cbo.owner_user_principal,
  cbo.owner_role,
  cbo.active_flag,
  CAST(NULL AS TEXT) AS created_at,
  cbo.updated_at,
  cbo.updated_by
FROM core_offering_business_owner cbo
WHERE NOT EXISTS (
  SELECT 1
  FROM offering_owner_assignment ooa
  WHERE ooa.assignment_id = cbo.offering_owner_id
);

DROP VIEW IF EXISTS vw_reporting_core_vendor_contact;
CREATE VIEW vw_reporting_core_vendor_contact AS
SELECT
  vc.vendor_contact_id,
  vc.vendor_id,
  coalesce(ct.contact_type_code, vc.contact_type_id) AS contact_type,
  vc.full_name,
  vc.email,
  vc.phone,
  coalesce(vc.active_flag, 1) AS active_flag,
  vc.created_at,
  coalesce(vc.ended_at, vc.created_at) AS updated_at,
  CAST(NULL AS TEXT) AS updated_by
FROM vendor_contact vc
LEFT JOIN lkp_contact_type ct
  ON ct.contact_type_id = vc.contact_type_id
UNION ALL
SELECT
  cvc.vendor_contact_id,
  cvc.vendor_id,
  cvc.contact_type,
  cvc.full_name,
  cvc.email,
  cvc.phone,
  cvc.active_flag,
  CAST(NULL AS TEXT) AS created_at,
  cvc.updated_at,
  cvc.updated_by
FROM core_vendor_contact cvc
WHERE NOT EXISTS (
  SELECT 1
  FROM vendor_contact vc
  WHERE vc.vendor_contact_id = cvc.vendor_contact_id
);

DROP VIEW IF EXISTS vw_reporting_core_offering_contact;
CREATE VIEW vw_reporting_core_offering_contact AS
SELECT
  oc.offering_contact_id,
  oc.offering_id,
  coalesce(ct.contact_type_code, oc.contact_type_id) AS contact_type,
  oc.full_name,
  oc.email,
  oc.phone,
  coalesce(oc.active_flag, 1) AS active_flag,
  oc.created_at,
  coalesce(oc.ended_at, oc.created_at) AS updated_at,
  CAST(NULL AS TEXT) AS updated_by
FROM offering_contact oc
LEFT JOIN lkp_contact_type ct
  ON ct.contact_type_id = oc.contact_type_id
UNION ALL
SELECT
  coc.offering_contact_id,
  coc.offering_id,
  coc.contact_type,
  coc.full_name,
  coc.email,
  coc.phone,
  coc.active_flag,
  CAST(NULL AS TEXT) AS created_at,
  coc.updated_at,
  coc.updated_by
FROM core_offering_contact coc
WHERE NOT EXISTS (
  SELECT 1
  FROM offering_contact oc
  WHERE oc.offering_contact_id = coc.offering_contact_id
);

DROP VIEW IF EXISTS vw_reporting_core_vendor_identifier;
CREATE VIEW vw_reporting_core_vendor_identifier AS
SELECT
  vi.vendor_identifier_id,
  vi.vendor_id,
  vi.identifier_type,
  vi.source_vendor_key AS identifier_value,
  coalesce(vi.is_primary_source, 0) AS is_primary,
  CAST(NULL AS TEXT) AS country_code,
  vi.updated_at,
  CAST(NULL AS TEXT) AS updated_by
FROM vendor_identifier vi
UNION ALL
SELECT
  cvi.vendor_identifier_id,
  cvi.vendor_id,
  cvi.identifier_type,
  cvi.identifier_value,
  cvi.is_primary,
  cvi.country_code,
  cvi.updated_at,
  cvi.updated_by
FROM core_vendor_identifier cvi
WHERE NOT EXISTS (
  SELECT 1
  FROM vendor_identifier vi
  WHERE vi.vendor_identifier_id = cvi.vendor_identifier_id
);

DROP VIEW IF EXISTS vw_reporting_core_vendor_org_assignment;
CREATE VIEW vw_reporting_core_vendor_org_assignment AS
SELECT
  vba.assignment_id AS vendor_org_assignment_id,
  vba.vendor_id,
  coalesce(bu.business_unit_name, vba.business_unit_id) AS org_id,
  CASE
    WHEN coalesce(vba.is_primary, 0) = 1 THEN 'primary'
    ELSE 'consumer'
  END AS assignment_type,
  coalesce(vba.active_flag, 1) AS active_flag,
  vba.created_at,
  coalesce(vba.updated_at, vba.created_at) AS updated_at,
  vba.updated_by
FROM vendor_business_unit_assignment vba
LEFT JOIN lkp_business_unit bu
  ON bu.business_unit_id = vba.business_unit_id
UNION ALL
SELECT
  cvoa.vendor_org_assignment_id,
  cvoa.vendor_id,
  cvoa.org_id,
  cvoa.assignment_type,
  cvoa.active_flag,
  CAST(NULL AS TEXT) AS created_at,
  cvoa.updated_at,
  cvoa.updated_by
FROM core_vendor_org_assignment cvoa
WHERE NOT EXISTS (
  SELECT 1
  FROM vendor_business_unit_assignment vba
  WHERE vba.assignment_id = cvoa.vendor_org_assignment_id
);

DROP VIEW IF EXISTS vw_reporting_core_contract;
CREATE VIEW vw_reporting_core_contract AS
SELECT
  c.contract_id,
  c.vendor_id,
  c.offering_id,
  c.contract_number,
  c.contract_status,
  c.start_date,
  c.end_date,
  coalesce(c.cancelled_flag, 0) AS cancelled_flag,
  c.annual_value,
  c.updated_at,
  c.updated_by
FROM contract c
UNION ALL
SELECT
  cc.contract_id,
  cc.vendor_id,
  cc.offering_id,
  cc.contract_number,
  cc.contract_status,
  cc.start_date,
  cc.end_date,
  cc.cancelled_flag,
  cc.annual_value,
  cc.updated_at,
  cc.updated_by
FROM core_contract cc
WHERE NOT EXISTS (
  SELECT 1
  FROM contract c
  WHERE c.contract_id = cc.contract_id
);

DROP VIEW IF EXISTS vw_reporting_core_contract_event;
CREATE VIEW vw_reporting_core_contract_event AS
SELECT
  ce.contract_event_id,
  ce.contract_id,
  ce.event_type,
  ce.event_ts,
  ce.reason_code,
  ce.notes,
  ce.actor_user_principal
FROM contract_event ce
UNION ALL
SELECT
  cce.contract_event_id,
  cce.contract_id,
  cce.event_type,
  cce.event_ts,
  cce.reason_code,
  cce.notes,
  cce.actor_user_principal
FROM core_contract_event cce
WHERE NOT EXISTS (
  SELECT 1
  FROM contract_event ce
  WHERE ce.contract_event_id = cce.contract_event_id
);

DROP VIEW IF EXISTS vw_reporting_core_vendor_demo;
CREATE VIEW vw_reporting_core_vendor_demo AS
SELECT
  d.demo_id,
  d.vendor_id,
  d.offering_id,
  d.demo_date,
  d.overall_score,
  d.selection_outcome,
  d.non_selection_reason_code,
  d.notes,
  d.updated_at,
  d.updated_by
FROM vendor_demo d
UNION ALL
SELECT
  cd.demo_id,
  cd.vendor_id,
  cd.offering_id,
  cd.demo_date,
  cd.overall_score,
  cd.selection_outcome,
  cd.non_selection_reason_code,
  cd.notes,
  cd.updated_at,
  cd.updated_by
FROM core_vendor_demo cd
WHERE NOT EXISTS (
  SELECT 1
  FROM vendor_demo d
  WHERE d.demo_id = cd.demo_id
);

DROP VIEW IF EXISTS vw_reporting_core_vendor_demo_score;
CREATE VIEW vw_reporting_core_vendor_demo_score AS
SELECT
  ds.demo_score_id,
  ds.demo_id,
  ds.score_category,
  ds.score_value,
  ds.weight,
  ds.comments
FROM vendor_demo_score ds
UNION ALL
SELECT
  cds.demo_score_id,
  cds.demo_id,
  cds.score_category,
  cds.score_value,
  cds.weight,
  cds.comments
FROM core_vendor_demo_score cds
WHERE NOT EXISTS (
  SELECT 1
  FROM vendor_demo_score ds
  WHERE ds.demo_score_id = cds.demo_score_id
);

DROP VIEW IF EXISTS vw_reporting_core_vendor_demo_note;
CREATE VIEW vw_reporting_core_vendor_demo_note AS
SELECT
  dn.demo_note_id,
  dn.demo_id,
  dn.note_type,
  dn.note_text,
  dn.created_at,
  dn.created_by
FROM vendor_demo_note dn
UNION ALL
SELECT
  cdn.demo_note_id,
  cdn.demo_id,
  cdn.note_type,
  cdn.note_text,
  cdn.created_at,
  cdn.created_by
FROM core_vendor_demo_note cdn
WHERE NOT EXISTS (
  SELECT 1
  FROM vendor_demo_note dn
  WHERE dn.demo_note_id = cdn.demo_note_id
);

DROP VIEW IF EXISTS rpt_spend_fact;
CREATE VIEW rpt_spend_fact AS
SELECT
  i.invoice_id,
  i.vendor_id,
  coalesce(v.display_name, v.legal_name) AS vendor_name,
  v.owner_org_id AS org_id,
  coalesce(o.offering_type, 'unknown') AS category,
  i.invoice_date AS month,
  i.amount
FROM app_offering_invoice i
LEFT JOIN vw_reporting_core_vendor v
  ON i.vendor_id = v.vendor_id
LEFT JOIN vw_reporting_core_vendor_offering o
  ON i.offering_id = o.offering_id;

DROP VIEW IF EXISTS rpt_contract_renewals;
CREATE VIEW rpt_contract_renewals AS
SELECT
  c.contract_id,
  c.vendor_id,
  coalesce(v.display_name, v.legal_name) AS vendor_name,
  v.owner_org_id AS org_id,
  coalesce(o.offering_type, 'unknown') AS category,
  c.end_date AS renewal_date,
  c.annual_value,
  v.risk_tier,
  CASE
    WHEN c.cancelled_flag = 1 THEN 'cancelled'
    ELSE c.contract_status
  END AS renewal_status
FROM vw_reporting_core_contract c
LEFT JOIN vw_reporting_core_vendor v
  ON c.vendor_id = v.vendor_id
LEFT JOIN vw_reporting_core_vendor_offering o
  ON c.offering_id = o.offering_id;

DROP VIEW IF EXISTS rpt_contract_cancellations;
CREATE VIEW rpt_contract_cancellations AS
SELECT
  c.contract_id,
  c.vendor_id,
  c.offering_id,
  e.event_ts AS cancelled_at,
  e.reason_code,
  e.notes
FROM vw_reporting_core_contract c
INNER JOIN vw_reporting_core_contract_event e
  ON c.contract_id = e.contract_id
WHERE lower(coalesce(e.event_type, '')) IN ('cancelled', 'cancellation', 'contract_cancelled');
