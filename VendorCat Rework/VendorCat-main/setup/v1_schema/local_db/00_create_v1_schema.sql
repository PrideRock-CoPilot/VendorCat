PRAGMA foreign_keys = ON;

-- SQLite does not create schemas in the same way as Databricks.
-- This file exists to normalize execution order across environments.
SELECT 'V1 local schema bootstrap started' AS status;
