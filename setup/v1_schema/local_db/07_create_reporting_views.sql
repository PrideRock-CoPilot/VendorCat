PRAGMA foreign_keys = ON;

CREATE VIEW IF NOT EXISTS vw_employee_directory AS
SELECT
  login_identifier,
  email,
  network_id,
  employee_id,
  manager_id,
  first_name,
  last_name,
  display_name,
  active_flag
FROM app_employee_directory;

CREATE VIEW IF NOT EXISTS rpt_spend_fact AS
SELECT
  i.invoice_id,
  i.vendor_id,
  COALESCE(v.display_name, v.legal_name) AS vendor_name,
  v.owner_org_id AS org_id,
  COALESCE(o.offering_type, 'unknown') AS category,
  i.invoice_date AS month,
  i.amount
FROM app_offering_invoice i
LEFT JOIN core_vendor v
  ON i.vendor_id = v.vendor_id
LEFT JOIN core_vendor_offering o
  ON i.offering_id = o.offering_id;

CREATE VIEW IF NOT EXISTS rpt_contract_renewals AS
SELECT
  c.contract_id,
  c.vendor_id,
  COALESCE(v.display_name, v.legal_name) AS vendor_name,
  v.owner_org_id AS org_id,
  COALESCE(o.offering_type, 'unknown') AS category,
  c.end_date AS renewal_date,
  c.annual_value,
  v.risk_tier,
  CASE
    WHEN c.cancelled_flag = 1 THEN 'cancelled'
    ELSE c.contract_status
  END AS renewal_status
FROM core_contract c
LEFT JOIN core_vendor v
  ON c.vendor_id = v.vendor_id
LEFT JOIN core_vendor_offering o
  ON c.offering_id = o.offering_id;

CREATE VIEW IF NOT EXISTS rpt_contract_cancellations AS
SELECT
  c.contract_id,
  c.vendor_id,
  c.offering_id,
  e.event_ts AS cancelled_at,
  e.reason_code,
  e.notes
FROM core_contract c
INNER JOIN core_contract_event e
  ON c.contract_id = e.contract_id
WHERE lower(COALESCE(e.event_type, '')) IN ('cancelled', 'cancellation', 'contract_cancelled');
