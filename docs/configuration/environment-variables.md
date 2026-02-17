# Environment Variables

This document describes every supported environment variable, its default, what it controls, and the code path that reads it.
If a variable is misconfigured, the expected behavior and failure mode are listed in its description.

## Canonical Prefixes
- `TVENDOR_`: application/runtime behavior.
- `DATABRICKS_`: Databricks connectivity and auth.

Runtime lookups are centralized in:
- `app/vendor_catalog_app/core/env.py`
- `app/vendor_catalog_app/core/config.py`

## How Configuration Is Resolved
- Types are parsed in `app/vendor_catalog_app/core/env.py` via `get_env_bool`, `get_env_int`, and `get_env_float`.
- Defaults for most settings live in `app/vendor_catalog_app/core/defaults.py` and `app/vendor_catalog_app/core/config.py`.
- Databricks HTTP path resolution falls back to warehouse ID or app resource binding keys.

## Compatibility Aliases
These aliases are still accepted for backward compatibility (resolved in `core/config.py`):
- Hostname: `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HOST`, `DBSQL_SERVER_HOSTNAME`
- HTTP path: `DATABRICKS_HTTP_PATH`, `DATABRICKS_SQL_HTTP_PATH`, `DBSQL_HTTP_PATH`, `SQL_HTTP_PATH`
- Warehouse ID: `DATABRICKS_WAREHOUSE_ID`, `DATABRICKS_SQL_WAREHOUSE_ID`, `SQL_WAREHOUSE_ID`, `DBSQL_WAREHOUSE_ID`
- Databricks Apps resource bindings: `sql-warehouse`, `sql_warehouse`, `SQL_WAREHOUSE`, `SQL-WAREHOUSE`

## Core App Configuration
- `TVENDOR_ENV` (string, default `dev`)
  - Controls dev vs prod behaviors (ex: security defaults, local DB allowance).
  - Used in `core/config.py` and `core/defaults.py`.
- `TVENDOR_FQ_SCHEMA` (string, default empty)
  - Fully qualified schema override in `<catalog>.<schema>` format.
  - If set, overrides `TVENDOR_CATALOG` + `TVENDOR_SCHEMA`.
  - Misformat raises a runtime error in `core/config.py`.
- `TVENDOR_CATALOG` (string, default `vendor_dev` in dev)
  - Required outside dev/local unless `TVENDOR_FQ_SCHEMA` is set.
- `TVENDOR_SCHEMA` (string, default `twvendor` in dev)
  - Required outside dev/local unless `TVENDOR_FQ_SCHEMA` is set.
- `TVENDOR_USE_LOCAL_DB` (bool, default true in dev/local)
  - Enables SQLite local DB. Disallowed outside dev/local and will raise at startup.
  - Used in `core/config.py` and `infrastructure/local_db_bootstrap.py`.
- `TVENDOR_LOCAL_DB_PATH` (string, default `setup/local_db/twvendor_local.db`)
  - Absolute or repo-relative local DB path.
- `TVENDOR_LOCKED_MODE` (bool, default false)
  - Read-only mode enforcement. Used in `core/config.py` and downstream access checks.
- `TVENDOR_ENFORCE_PROD_SQL_POLICY` (bool, default true)
  - Enforces production SQL safety rules (e.g., write restrictions).
- `TVENDOR_ALLOWED_WRITE_VERBS` (CSV string, default `INSERT,UPDATE`)
  - Allowed write verbs in SQL policy enforcement.
- `TVENDOR_SCHEMA_BOOTSTRAP_SQL` (string, default `setup/v1_schema/databricks/00_create_v1_schema.sql`)
  - Schema bootstrap SQL path used by bootstrap logic.
- `TVENDOR_SQL_PRELOAD_ON_STARTUP` (bool, default false)
  - Preloads SQL metadata on app startup to warm caches.

## Databricks Connectivity and Auth
- `DATABRICKS_SERVER_HOSTNAME` (string, no default)
  - Required for Databricks SQL connectivity.
- `DATABRICKS_HTTP_PATH` (string, no default)
  - Preferred HTTP path for Databricks SQL.
- `DATABRICKS_WAREHOUSE_ID` (string, no default)
  - If set, `core/config.py` builds the HTTP path as `/sql/1.0/warehouses/<id>`.
- `DATABRICKS_TOKEN` (string, no default)
  - Personal access token for Databricks SQL connector.
- `DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET` (string, no default)
  - OAuth service-principal auth path used by `infrastructure/db.py`.
- Databricks Apps resource bindings (`sql-warehouse`, etc.)
  - Used by `core/config.py` to resolve `http_path` if no explicit path/warehouse ID is provided.

Misconfiguration effects:
- Missing host/path/auth results in `Missing Databricks settings` errors from `infrastructure/db.py`.
- Warehouse resource binding missing for Apps leads to SQL connection failures.

## Diagnostics
- `TVENDOR_BOOTSTRAP_DIAGNOSTICS_ENABLED` (bool, default true in dev; false in prod)
  - Enables `/bootstrap-diagnostics` without token.
  - Used in `web/system/bootstrap_diagnostics.py`.
- `TVENDOR_BOOTSTRAP_DIAGNOSTICS_TOKEN` (string, no default)
  - If set, allows access with `x-tvendor-diagnostics-token` or `Authorization: Bearer`.

## Session, Security, and Identity
- `TVENDOR_SESSION_SECRET` (string, default `vendor-catalog-dev-secret`)
  - Cookie/session signing secret.
  - In prod, if default and `TVENDOR_ALLOW_DEFAULT_SESSION_SECRET` is false, a random secret is generated.
- `TVENDOR_ALLOW_DEFAULT_SESSION_SECRET` (bool, default false)
  - Allows use of the default session secret outside dev.
- `TVENDOR_SESSION_HTTPS_ONLY` (bool, default true in prod)
  - Enforces HTTPS-only cookies.
- `TVENDOR_CSRF_ENABLED` (bool, default true in prod)
  - Enables CSRF checks.
- `TVENDOR_SECURITY_HEADERS_ENABLED` (bool, default true)
  - Toggles security headers middleware.
- `TVENDOR_CSP_ENABLED` (bool, default true)
  - Enables CSP header.
- `TVENDOR_CSP_POLICY` (string, default from `core/defaults.py`)
  - CSP policy string. Optionally augmented when embedding Databricks reports.
- `TVENDOR_TRUST_FORWARDED_IDENTITY_HEADERS` (bool, default true in dev)
  - Trusts forwarded identity headers for user resolution.
- `TVENDOR_FORWARDED_GROUP_HEADERS` (CSV string, default from `core/security.py`)
  - Header names for group mapping in SSO flows.
- `TVENDOR_ALLOW_TEST_ROLE_OVERRIDE` (bool, default true in dev)
  - Enables test role override for admin users.
- `TVENDOR_TEST_USER` (string, default empty)
  - Dev-only user principal override for local DB flows.
- `TVENDOR_IDENTITY_SYNC_TTL_SEC` (int, default 300)
  - TTL for syncing user identity into app tables.
- `TVENDOR_POLICY_SNAPSHOT_TTL_SEC` (int, default 300)
  - TTL for cached policy snapshots in session.

Primary usage is in:
- `web/system/settings.py` (session/CSP/CSRF/security headers)
- `web/core/runtime.py` (forwarded identity trust, role overrides)
- `web/core/user_context_service.py` (identity sync TTL, policy snapshot TTL)

## Performance and Error Handling
- `TVENDOR_PERF_LOG_ENABLED` (bool, default false)
  - Enables performance log capture.
- `TVENDOR_PERF_RESPONSE_HEADER` (bool, default true)
  - Adds perf headers in responses.
- `TVENDOR_SLOW_QUERY_MS` (float, default 750.0)
  - Threshold for slow query markers and warnings.
- `TVENDOR_SQL_TRACE_ENABLED` (bool, default false)
  - Enables SQL statement tracing in DB client.
- `TVENDOR_SQL_TRACE_MAX_LEN` (int, default 180)
  - Max SQL statement length logged/traced.
- `TVENDOR_ERROR_INCLUDE_DETAILS` (bool, default false)
  - Includes exception details in API error payloads.
- `TVENDOR_REQUEST_ID_HEADER_ENABLED` (bool, default true)
  - Adds `X-Request-ID` to responses.

Primary usage is in:
- `infrastructure/db.py` (SQL tracing and slow query thresholds)
- `web/system/settings.py` (perf flags)
- `web/http/errors.py` (error detail inclusion)

## Logging
- `TVENDOR_LOG_LEVEL` (string, default `INFO`)
  - Application log level.
- `TVENDOR_LOG_JSON` (bool, default false)
  - JSON log formatting.
- `TVENDOR_LOG_CAPTURE_ROOT` (bool, default false)
  - Captures root logger output.

Primary usage is in `infrastructure/logging.py`.

## DB Caching and Pooling
- `TVENDOR_QUERY_CACHE_ENABLED` (bool, default true)
  - Enables query result caching in `DatabricksSQLClient`.
- `TVENDOR_QUERY_CACHE_TTL_SEC` (int, default 120)
  - Query cache TTL seconds.
- `TVENDOR_QUERY_CACHE_MAX_ENTRIES` (int, default 256)
  - Query cache max entries.
- `TVENDOR_DB_POOL_ENABLED` (bool, default true)
  - Enables SQL connection pooling (disabled for local DB).
- `TVENDOR_DB_POOL_MAX_SIZE` (int, default 8)
  - Max pooled connections.
- `TVENDOR_DB_POOL_ACQUIRE_TIMEOUT_SEC` (float, default 15.0)
  - Pool acquire timeout seconds.
- `TVENDOR_DB_POOL_IDLE_TTL_SEC` (float, default 600.0)
  - Max idle TTL before pooled connection cleanup.
- `TVENDOR_REPO_CACHE_ENABLED` (bool, default true)
  - Enables repository-level cache.
- `TVENDOR_REPO_CACHE_TTL_SEC` (int, default 120)
  - Repo cache TTL seconds.
- `TVENDOR_REPO_CACHE_MAX_ENTRIES` (int, default 512)
  - Repo cache max entries.

Primary usage is in:
- `infrastructure/db.py` (query cache, pool config)
- `backend/repository/vendor_repository.py` (repo cache)

## Usage Logging
- `TVENDOR_USAGE_LOG_ENABLED` (bool, default true in dev; false in prod)
  - Enables usage event logging to `app_usage_log`.
  - Note: this flag is read directly from `os.getenv` in repository mixins.
- `TVENDOR_USAGE_LOG_MIN_INTERVAL_SEC` (int, default 120)
  - Throttle per `(user, page, event_type)` to limit log spam.

Primary usage is in:
- `backend/repository_mixins/domains/repository_identity.py`
- `backend/repository_mixins/common/core/cache_runtime.py`

## Observability and Metrics
- `TVENDOR_METRICS_ENABLED` (bool, default true)
  - Master switch for metrics.
- `TVENDOR_METRICS_PROMETHEUS_ENABLED` (bool, default true)
  - Enables Prometheus endpoint.
- `TVENDOR_METRICS_PROMETHEUS_PATH` (string, default `/api/metrics`)
  - Path for Prometheus scrape.
- `TVENDOR_METRICS_ALLOW_UNAUTHENTICATED` (bool, default true in dev)
  - Allows unauthenticated metrics access.
- `TVENDOR_METRICS_AUTH_TOKEN` (string, no default)
  - Token for authenticated metrics access.
- `TVENDOR_STATSD_ENABLED` (bool, default false)
  - Enables StatsD emission.
- `TVENDOR_STATSD_HOST` (string, default `127.0.0.1`)
- `TVENDOR_STATSD_PORT` (int, default `8125`)
- `TVENDOR_STATSD_PREFIX` (string, default `tvendor`)
- `TVENDOR_ALERTS_ENABLED` (bool, default true)
  - Enables alert threshold checks.
- `TVENDOR_ALERT_WINDOW_SEC` (int, default 300)
- `TVENDOR_ALERT_MIN_REQUESTS` (int, default 20)
- `TVENDOR_ALERT_COOLDOWN_SEC` (int, default 300)
- `TVENDOR_ALERT_REQUEST_P95_MS` (float, default 0.0)
- `TVENDOR_ALERT_ERROR_RATE_PCT` (float, default 0.0)
- `TVENDOR_ALERT_DB_AVG_MS` (float, default 0.0)

Primary usage is in `infrastructure/observability.py` and `web/system/settings.py`.

## UI Timing and Loading States
- `TVENDOR_STARTUP_SPLASH_MIN_DELAY_MS` (int, default 2000)
- `TVENDOR_STARTUP_SPLASH_MAX_DELAY_MS` (int, default 5000)
  - Startup splash random delay window.
- `TVENDOR_LOADING_OVERLAY_MIN_DELAY_MS` (int, default 2000)
- `TVENDOR_LOADING_OVERLAY_MAX_DELAY_MS` (int, default 5000)
- `TVENDOR_LOADING_OVERLAY_SHOW_DELAY_MS` (int, default 220)
- `TVENDOR_LOADING_OVERLAY_SLOW_STATUS_MS` (int, default 5000)
- `TVENDOR_LOADING_OVERLAY_SAFETY_MS` (int, default 12000)

Primary usage is in:
- `web/routers/dashboard/common.py` (startup splash)
- `web/core/template_context.py` (loading overlay)

## Databricks Reports Embedding
- `TVENDOR_DATABRICKS_REPORTS_JSON` (string JSON, default empty)
  - JSON list of report links and metadata.
- `TVENDOR_DATABRICKS_REPORTS_ALLOW_EMBED` (bool, default false)
  - Allows embedding within the app.
- `TVENDOR_DATABRICKS_REPORTS_ALLOWED_HOSTS` (CSV string, default empty)
  - Allowlist for report hostnames.

Primary usage is in `web/routers/reports/common.py` and `web/system/settings.py`.

## Local DB Bootstrap
- `TVENDOR_LOCAL_DB_AUTO_INIT` (bool, default true)
  - Enables automatic local DB initialization.
- `TVENDOR_LOCAL_DB_RESET_ON_START` (bool, default false)
  - Forces local DB reset on startup.
- `TVENDOR_LOCAL_DB_SEED` (bool, default false)
  - Enables seed data load.
- `TVENDOR_LOCAL_DB_SEED_PROFILE` (string, default `baseline`)
  - Seed profile (`baseline` or `full`).

Primary usage is in `infrastructure/local_db_bootstrap.py`.
