SELECT
  contract_id,
  vendor_id,
  vendor_name,
  org_id,
  category,
  renewal_date,
  annual_value,
  risk_tier,
  renewal_status,
  datediff(renewal_date, current_date()) AS days_to_renewal
FROM {rpt_contract_renewals}
WHERE renewal_date BETWEEN current_date() AND date_add(current_date(), {horizon_days})
  {org_clause}
ORDER BY renewal_date
