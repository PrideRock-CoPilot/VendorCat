SELECT month, SUM(amount) AS total_spend
FROM {rpt_spend_fact}
WHERE vendor_id = %s
  AND month >= add_months(date_trunc('month', current_date()), -{months_back})
GROUP BY month
ORDER BY month
