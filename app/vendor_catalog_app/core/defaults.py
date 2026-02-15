from __future__ import annotations

# Environment and config defaults
DEFAULT_ENV_NAME = "dev"
DEFAULT_DEV_ENV_NAMES = ("dev", "development", "local")
DEFAULT_DEV_CATALOG = "vendor_dev"
DEFAULT_DEV_SCHEMA = "twvendor"
DEFAULT_ALLOWED_WRITE_VERBS_CSV = "INSERT,UPDATE"
DEFAULT_ALLOWED_WRITE_VERBS = ("INSERT", "UPDATE")
DEFAULT_LOCAL_DB_PATH = "setup/local_db/twvendor_local.db"
DEFAULT_SCHEMA_BOOTSTRAP_SQL_PATH = "setup/databricks/001_create_databricks_schema.sql"
DEFAULT_SESSION_SECRET = "vendor-catalog-dev-secret"

# Security/header defaults
DEFAULT_CSP_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "object-src 'none'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; "
    "connect-src 'self'; "
    "form-action 'self'"
)

# Web/router defaults
DEFAULT_RETURN_TO_PATH = "/vendors"
DEFAULT_ALLOWED_RETURN_TO_PREFIXES = ("/vendor-360", "/vendors", "/projects")
DEFAULT_VENDOR_SETTINGS_KEY = "vendor360_list"
DEFAULT_FILTER_OPTION_ALL = "all"
DEFAULT_GROUP_OPTION_NONE = "none"
DEFAULT_PROJECT_TYPE = "other"
DEFAULT_CONTRACT_STATUS = "active"
DEFAULT_PROJECT_STATUS_ACTIVE = "active"
DEFAULT_SOURCE_SYSTEM = "manual"
DEFAULT_VENDOR_SUMMARY_MONTHS = 12
DEFAULT_DOC_TITLE_MAX_LENGTH = 120
DEFAULT_OFFERING_INVOICE_WINDOW_MONTHS = 3
DEFAULT_OFFERING_ALERT_THRESHOLD_PCT = 10.0

# Startup/loading experience defaults (milliseconds)
DEFAULT_STARTUP_SPLASH_MIN_DELAY_MS = 2000
DEFAULT_STARTUP_SPLASH_MAX_DELAY_MS = 5000
DEFAULT_LOADING_OVERLAY_MIN_DELAY_MS = 2000
DEFAULT_LOADING_OVERLAY_MAX_DELAY_MS = 5000
DEFAULT_LOADING_OVERLAY_SHOW_DELAY_MS = 220
DEFAULT_LOADING_OVERLAY_SLOW_STATUS_MS = 5000
DEFAULT_LOADING_OVERLAY_SAFETY_MS = 12000
