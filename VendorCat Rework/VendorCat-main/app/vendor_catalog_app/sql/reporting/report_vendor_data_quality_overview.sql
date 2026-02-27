SELECT
  v.vendor_id,
  coalesce(v.display_name, v.legal_name, v.vendor_id) AS vendor_display_name,
  v.lifecycle_state,
  v.owner_org_id,
  v.risk_tier,
  coalesce(w.warning_count, 0) AS warning_count,
  coalesce(w.open_warning_count, 0) AS open_warning_count,
  w.latest_warning_at,
  coalesce(o.offering_count, 0) AS offering_count,
  o.latest_offering_updated_at,
  coalesce(c.contract_count, 0) AS contract_count,
  c.latest_contract_updated_at,
  coalesce(d.demo_count, 0) AS demo_count,
  d.latest_demo_updated_at,
  coalesce(i.invoice_count, 0) AS invoice_count,
  i.latest_invoice_date,
  coalesce(t.ticket_count, 0) AS ticket_count,
  t.latest_ticket_updated_at,
  coalesce(f.data_flow_count, 0) AS data_flow_count,
  f.latest_data_flow_updated_at
FROM {core_vendor} v
LEFT JOIN (
  SELECT
    vendor_id,
    count(*) AS warning_count,
    sum(CASE WHEN lower(coalesce(warning_status, 'open')) IN ('open', 'monitoring') THEN 1 ELSE 0 END) AS open_warning_count,
    max(coalesce(detected_at, created_at, updated_at)) AS latest_warning_at
  FROM {app_vendor_warning}
  GROUP BY vendor_id
) w
  ON w.vendor_id = v.vendor_id
LEFT JOIN (
  SELECT
    vendor_id,
    count(*) AS offering_count,
    max(updated_at) AS latest_offering_updated_at
  FROM {core_vendor_offering}
  GROUP BY vendor_id
) o
  ON o.vendor_id = v.vendor_id
LEFT JOIN (
  SELECT
    vendor_id,
    count(*) AS contract_count,
    max(updated_at) AS latest_contract_updated_at
  FROM {core_contract}
  GROUP BY vendor_id
) c
  ON c.vendor_id = v.vendor_id
LEFT JOIN (
  SELECT
    vendor_id,
    count(*) AS demo_count,
    max(updated_at) AS latest_demo_updated_at
  FROM {core_vendor_demo}
  GROUP BY vendor_id
) d
  ON d.vendor_id = v.vendor_id
LEFT JOIN (
  SELECT
    vendor_id,
    count(*) AS invoice_count,
    max(invoice_date) AS latest_invoice_date
  FROM {app_offering_invoice}
  GROUP BY vendor_id
) i
  ON i.vendor_id = v.vendor_id
LEFT JOIN (
  SELECT
    vendor_id,
    count(*) AS ticket_count,
    max(updated_at) AS latest_ticket_updated_at
  FROM {app_offering_ticket}
  GROUP BY vendor_id
) t
  ON t.vendor_id = v.vendor_id
LEFT JOIN (
  SELECT
    vendor_id,
    count(*) AS data_flow_count,
    max(updated_at) AS latest_data_flow_updated_at
  FROM {app_offering_data_flow}
  GROUP BY vendor_id
) f
  ON f.vendor_id = v.vendor_id
WHERE {where_clause}
ORDER BY lower(coalesce(v.display_name, v.legal_name, v.vendor_id)), v.vendor_id
LIMIT {limit}
