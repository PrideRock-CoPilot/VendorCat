SELECT
  g.group_principal,
  g.group_principal AS label
FROM {sec_group_role_map} g
WHERE %s = '' OR lower(g.group_principal) LIKE %s
GROUP BY g.group_principal
ORDER BY g.group_principal
LIMIT {limit}
