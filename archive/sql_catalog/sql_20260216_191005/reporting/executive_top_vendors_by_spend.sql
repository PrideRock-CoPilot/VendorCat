SELECT
  sf.vendor_id,
  coalesce(v.display_name, v.legal_name) AS vendor_name,
  v.risk_tier,
  SUM(sf.amount) AS total_spend
FROM {rpt_spend_fact} sf
LEFT JOIN {core_vendor} v
  ON sf.vendor_id = v.vendor_id
WHERE sf.month >= add_months(date_trunc('month', current_date()), -{months_back})
  {org_clause}
GROUP BY sf.vendor_id, coalesce(v.display_name, v.legal_name), v.risk_tier
ORDER BY total_spend DESC
LIMIT {limit_rows}
