-- Migration for existing deployments where core_vendor_offering already exists.
-- Run this once after 001_create_databricks_schema.sql if lob/service_type are missing.

ALTER TABLE {fq_schema}.core_vendor_offering
ADD COLUMN IF NOT EXISTS lob STRING;

ALTER TABLE {fq_schema}.core_vendor_offering
ADD COLUMN IF NOT EXISTS service_type STRING;
