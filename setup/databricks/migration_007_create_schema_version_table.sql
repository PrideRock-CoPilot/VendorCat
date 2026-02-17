-- Migration 007: Create app_schema_version table
-- Author: Tech Lead
-- Date: 2026-02-15
-- Jira: VENDOR-MIGRATION-FRAMEWORK

-- Description:
-- Creates the app_schema_version table to track applied database migrations.
-- This is the first migration in the versioned migration system.

-- Backward Compatibility:
-- Yes - new table, does not affect existing functionality.

-- Rollback Instructions:
-- DROP TABLE IF EXISTS twvendor.app_schema_version;

-- ======================
-- FORWARD MIGRATION
-- ======================

CREATE TABLE IF NOT EXISTS twvendor.app_schema_version (
    version_number INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    applied_by TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rollback_notes TEXT
);

-- Insert this migration as version 7
INSERT INTO twvendor.app_schema_version (
    version_number,
    description,
    applied_by,
    applied_at,
    rollback_notes
) VALUES (
    7,
    'Create app_schema_version table for migration tracking',
    'system',
    CURRENT_TIMESTAMP,
    'DROP TABLE twvendor.app_schema_version'
);

-- Verification query (run after migration to verify)
-- SELECT * FROM twvendor.app_schema_version;
-- Expected: 1 row with version_number = 7
