-- Unity Catalog bootstrap for Vendor Catalog
-- Single schema design: twvendor

CREATE CATALOG IF NOT EXISTS vendor_prod;
CREATE SCHEMA IF NOT EXISTS vendor_prod.twvendor;

-- Example group grants (replace with enterprise groups)
GRANT USAGE ON CATALOG vendor_prod TO `vendor_admin`;
GRANT USAGE ON CATALOG vendor_prod TO `vendor_steward`;
GRANT USAGE ON CATALOG vendor_prod TO `vendor_editor`;
GRANT USAGE ON CATALOG vendor_prod TO `vendor_viewer`;
GRANT USAGE ON CATALOG vendor_prod TO `vendor_auditor`;

GRANT USE SCHEMA ON SCHEMA vendor_prod.twvendor TO `vendor_admin`;
GRANT USE SCHEMA ON SCHEMA vendor_prod.twvendor TO `vendor_steward`;
GRANT USE SCHEMA ON SCHEMA vendor_prod.twvendor TO `vendor_editor`;
GRANT USE SCHEMA ON SCHEMA vendor_prod.twvendor TO `vendor_viewer`;
GRANT USE SCHEMA ON SCHEMA vendor_prod.twvendor TO `vendor_auditor`;

-- Direct table privileges should be limited.
-- App/read users should query secure rpt_ views instead of raw tables.
GRANT ALL PRIVILEGES ON SCHEMA vendor_prod.twvendor TO `vendor_admin`;
