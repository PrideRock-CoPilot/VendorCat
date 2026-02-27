SELECT COUNT(DISTINCT v.vendor_id) AS total_rows
FROM {core_vendor} v
WHERE {where_clause}
