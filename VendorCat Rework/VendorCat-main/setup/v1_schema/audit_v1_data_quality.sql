-- V1 data quality audit query pack
-- Use with setup/v1_schema/audit_v1_data_quality.py for repeatable reporting.

-- 1) Duplicate natural keys (case-normalized)
SELECT lower(trim(legal_name)) AS natural_key, COUNT(*) AS duplicate_count
FROM core_vendor
WHERE trim(coalesce(legal_name, '')) <> ''
GROUP BY lower(trim(legal_name))
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, natural_key;

SELECT vendor_id, lower(trim(offering_name)) AS natural_key, COUNT(*) AS duplicate_count
FROM core_vendor_offering
WHERE trim(coalesce(vendor_id, '')) <> ''
  AND trim(coalesce(offering_name, '')) <> ''
GROUP BY vendor_id, lower(trim(offering_name))
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, vendor_id, natural_key;

-- 2) Orphan references
SELECT o.offering_id, o.vendor_id
FROM core_vendor_offering o
LEFT JOIN core_vendor v ON v.vendor_id = o.vendor_id
WHERE trim(coalesce(o.vendor_id, '')) <> ''
  AND v.vendor_id IS NULL;

SELECT c.contract_id, c.offering_id
FROM core_contract c
LEFT JOIN core_vendor_offering o ON o.offering_id = c.offering_id
WHERE trim(coalesce(c.offering_id, '')) <> ''
  AND o.offering_id IS NULL;

-- 3) One-to-many compression risk
SELECT
  v.vendor_id,
  v.owner_org_id,
  COUNT(DISTINCT a.org_id) AS active_business_unit_count
FROM core_vendor v
JOIN core_vendor_org_assignment a ON a.vendor_id = v.vendor_id
WHERE coalesce(a.active_flag, 1) IN (1, '1', 'true', 'TRUE')
  AND trim(coalesce(a.org_id, '')) <> ''
GROUP BY v.vendor_id, v.owner_org_id
HAVING COUNT(DISTINCT a.org_id) > 1
ORDER BY active_business_unit_count DESC, v.vendor_id;

-- 4) Lookup drift (examples)
SELECT owner_org_id AS field_value, COUNT(*) AS row_count
FROM core_vendor
WHERE trim(coalesce(owner_org_id, '')) <> ''
GROUP BY owner_org_id
ORDER BY row_count DESC;

SELECT business_unit AS field_value, COUNT(*) AS row_count
FROM core_vendor_offering
WHERE trim(coalesce(business_unit, '')) <> ''
GROUP BY business_unit
ORDER BY row_count DESC;

-- 5) Reconciliation metrics
SELECT COUNT(*) AS core_vendor_count FROM core_vendor;
SELECT COUNT(*) AS canonical_vendor_count FROM vendor;
SELECT COUNT(*) AS core_offering_count FROM core_vendor_offering;
SELECT COUNT(*) AS canonical_offering_count FROM offering;

SELECT COUNT(*) AS core_active_vendor_org_assignment_count
FROM core_vendor_org_assignment
WHERE coalesce(active_flag, 1) IN (1, '1', 'true', 'TRUE');

SELECT COUNT(*) AS canonical_active_vendor_business_unit_assignment_count
FROM vendor_business_unit_assignment
WHERE coalesce(active_flag, 1) IN (1, '1', 'true', 'TRUE');
