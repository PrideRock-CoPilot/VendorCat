SELECT COUNT(*)
FROM sqlite_master
WHERE type = ?
  AND name NOT LIKE 'sqlite_%';
