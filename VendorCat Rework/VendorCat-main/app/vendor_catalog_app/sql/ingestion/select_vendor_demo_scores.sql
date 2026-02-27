SELECT s.demo_score_id, s.demo_id, s.score_category, s.score_value, s.weight, s.comments
FROM {core_vendor_demo_score} s
INNER JOIN {core_vendor_demo} d
  ON s.demo_id = d.demo_id
WHERE d.vendor_id = %s
ORDER BY d.demo_date DESC, s.score_category
