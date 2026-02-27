SELECT month, SUM(amount) AS total_spend
FROM {rpt_spend_fact}
WHERE month >= add_months(date_trunc('month', current_date()), -{months_back})
  {org_clause}
GROUP BY month
ORDER BY month
