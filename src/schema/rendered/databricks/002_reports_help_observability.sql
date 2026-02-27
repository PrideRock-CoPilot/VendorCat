-- Phase 6 rendered schema for Databricks

CREATE TABLE IF NOT EXISTS vc_report_run (
  run_id STRING,
  report_code STRING NOT NULL,
  filters_json STRING NOT NULL,
  output_format STRING NOT NULL,
  requested_by STRING NOT NULL,
  status STRING NOT NULL,
  row_count INT NOT NULL,
  download_url STRING,
  warnings_json STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
) USING DELTA
TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported');

CREATE TABLE IF NOT EXISTS vc_report_email_request (
  email_request_id STRING,
  run_id STRING NOT NULL,
  email_to_csv STRING NOT NULL,
  requested_by STRING NOT NULL,
  created_at TIMESTAMP NOT NULL
) USING DELTA
TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported');

CREATE TABLE IF NOT EXISTS vc_help_article (
  article_id STRING,
  slug STRING NOT NULL,
  title STRING NOT NULL,
  markdown_body STRING NOT NULL,
  rendered_html STRING NOT NULL,
  published BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
) USING DELTA
TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported');

CREATE TABLE IF NOT EXISTS vc_help_feedback (
  feedback_id STRING,
  slug STRING NOT NULL,
  rating STRING NOT NULL,
  comment STRING,
  submitted_by STRING NOT NULL,
  created_at TIMESTAMP NOT NULL
) USING DELTA
TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported');

CREATE TABLE IF NOT EXISTS vc_help_issue (
  issue_id STRING,
  slug STRING NOT NULL,
  issue_text STRING NOT NULL,
  screenshot_path STRING,
  submitted_by STRING NOT NULL,
  created_at TIMESTAMP NOT NULL
) USING DELTA
TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported');

CREATE TABLE IF NOT EXISTS vc_perf_baseline (
  baseline_id STRING,
  scenario_key STRING NOT NULL,
  runtime_profile STRING NOT NULL,
  p50_ms DOUBLE NOT NULL,
  p95_ms DOUBLE NOT NULL,
  sample_size INT NOT NULL,
  run_id STRING NOT NULL,
  created_at TIMESTAMP NOT NULL
) USING DELTA
TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported');
