SELECT category, SUM(amount) AS total_spend
FROM {rpt_spend_fact}
WHERE vendor_id = %s
  AND month >= add_months(date_trunc('month', current_date()), -{months_back})
GROUP BY category
ORDER BY total_spend DESC
