-- Secure views for application read paths in single schema twvendor

CREATE OR REPLACE VIEW vendor_prod.twvendor.rpt_vendor_360 AS
SELECT
  v.vendor_id,
  v.legal_name,
  v.display_name,
  v.lifecycle_state,
  v.owner_org_id,
  v.risk_tier,
  v.updated_at
FROM vendor_prod.twvendor.core_vendor v
INNER JOIN vendor_prod.twvendor.sec_user_org_scope s
  ON v.owner_org_id = s.org_id
WHERE s.active_flag = true
  AND s.user_principal = current_user();

CREATE OR REPLACE VIEW vendor_prod.twvendor.rpt_vendor_demo_outcomes AS
SELECT
  d.demo_id,
  d.vendor_id,
  d.offering_id,
  d.demo_date,
  d.overall_score,
  d.selection_outcome,
  d.non_selection_reason_code,
  d.notes
FROM vendor_prod.twvendor.core_vendor_demo d
INNER JOIN vendor_prod.twvendor.core_vendor v
  ON d.vendor_id = v.vendor_id
INNER JOIN vendor_prod.twvendor.sec_user_org_scope s
  ON v.owner_org_id = s.org_id
WHERE s.active_flag = true
  AND s.user_principal = current_user();

CREATE OR REPLACE VIEW vendor_prod.twvendor.rpt_contract_cancellations AS
SELECT
  c.contract_id,
  c.vendor_id,
  c.offering_id,
  e.event_ts AS cancelled_at,
  e.reason_code,
  e.notes
FROM vendor_prod.twvendor.core_contract c
INNER JOIN vendor_prod.twvendor.core_contract_event e
  ON c.contract_id = e.contract_id
INNER JOIN vendor_prod.twvendor.core_vendor v
  ON c.vendor_id = v.vendor_id
INNER JOIN vendor_prod.twvendor.sec_user_org_scope s
  ON v.owner_org_id = s.org_id
WHERE e.event_type = 'contract_cancelled'
  AND s.active_flag = true
  AND s.user_principal = current_user();
