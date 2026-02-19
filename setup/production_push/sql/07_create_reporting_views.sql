USE CATALOG `${CATALOG}`;
USE SCHEMA `${SCHEMA}`;

CREATE OR REPLACE VIEW vw_employee_directory AS
WITH directory AS (
  SELECT
    emp.EMPLID AS employee_id,
    LOWER(COALESCE(emp.OPRID, emp.EMAIL_ADDR)) AS network_id,
    LOWER(emp.EMAIL_ADDR) AS email,
    emp.FIRST_NAME AS first_name,
    emp.LAST_NAME AS last_name,
    TRIM(emp.FIRST_NAME || ' ' || emp.LAST_NAME) AS display_name,
    emp.EMPL_STATUS AS active_flag,
    CASE emp.EMPL_STATUS
      WHEN 'A' THEN 'Active'
      WHEN 'T' THEN 'Terminated'
      WHEN 'L' THEN 'Leave'
      WHEN 'U' THEN 'Unknown'
      WHEN 'D' THEN 'Deceased'
      WHEN 'S' THEN 'Suspended'
      ELSE emp.EMPL_STATUS
    END AS employment_status,
    emp.ACTION_DT AS last_action_date,
    emp.HIRE_DT AS hire_date,
    emp.TERMINATION_DT AS termination_date,
    emp.JOBTITLE AS job_title,
    emp.DEPTNAME AS department_name,
    emp.MANAGER_LEVEL AS manager_level,
    CASE
      WHEN emp.MANAGER_LEVEL = '0' THEN 'CEO'
      WHEN emp.MANAGER_LEVEL = '10' THEN 'President (Corporate)'
      WHEN emp.MANAGER_LEVEL = '18' THEN 'President (Market/Division)'
      WHEN emp.MANAGER_LEVEL = '17' THEN 'EVP / President (Business Unit)'
      WHEN emp.MANAGER_LEVEL = '13' THEN 'SVP'
      WHEN emp.MANAGER_LEVEL = '15' THEN 'Senior Leadership / Enterprise Architect'
      WHEN emp.MANAGER_LEVEL = '3' THEN 'VP'
      WHEN emp.MANAGER_LEVEL = '14' THEN 'Senior Manager / Team Lead'
      WHEN emp.MANAGER_LEVEL = '1' THEN 'Director'
      WHEN emp.MANAGER_LEVEL = '2' THEN 'Senior Partner / Specialist'
      WHEN emp.MANAGER_LEVEL = '5' THEN 'Manager'
      WHEN emp.MANAGER_LEVEL = '7' THEN 'Supervisor'
      WHEN emp.MANAGER_LEVEL = '9' THEN 'Individual Contributor'
      ELSE 'Unknown'
    END AS hierarchy_tier,
    CASE
      WHEN emp.MANAGER_LEVEL IN ('0', '10', '18', '17', '13') THEN 10
      WHEN emp.MANAGER_LEVEL IN ('15', '3') THEN 8
      WHEN emp.MANAGER_LEVEL IN ('1', '14') THEN 6
      WHEN emp.MANAGER_LEVEL IN ('2', '5', '7') THEN 4
      WHEN emp.MANAGER_LEVEL = '9' THEN 2
      ELSE 1
    END AS default_security_level,
    emp.REPORT_EMPLID AS manager_id
  FROM pr_std.hcm.emp_courion emp
)
SELECT DISTINCT
  employee_id,
  LOWER(COALESCE(NULLIF(email, ''), NULLIF(network_id, ''), NULLIF(employee_id, ''))) AS login_identifier,
  network_id,
  email,
  first_name,
  last_name,
  display_name,
  active_flag,
  employment_status,
  last_action_date,
  hire_date,
  termination_date,
  job_title,
  department_name,
  manager_level,
  hierarchy_tier,
  default_security_level,
  manager_id
FROM directory;

CREATE OR REPLACE VIEW rpt_spend_fact AS
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

CREATE OR REPLACE VIEW rpt_contract_renewals AS
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
    WHEN CAST(COALESCE(c.cancelled_flag, 0) AS INT) = 1 THEN 'cancelled'
    ELSE c.contract_status
  END AS renewal_status
FROM core_contract c
LEFT JOIN core_vendor v
  ON c.vendor_id = v.vendor_id
LEFT JOIN core_vendor_offering o
  ON c.offering_id = o.offering_id;

CREATE OR REPLACE VIEW rpt_contract_cancellations AS
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
