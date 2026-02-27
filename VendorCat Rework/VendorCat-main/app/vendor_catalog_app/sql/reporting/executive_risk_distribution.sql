SELECT risk_tier, COUNT(*) AS vendor_count
FROM {core_vendor}
WHERE lifecycle_state = 'active'
  {org_clause}
GROUP BY risk_tier
ORDER BY vendor_count DESC
