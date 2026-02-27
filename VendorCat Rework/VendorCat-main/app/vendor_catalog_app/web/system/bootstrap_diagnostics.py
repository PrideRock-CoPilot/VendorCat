from __future__ import annotations

import hmac
import os
from typing import Any

from fastapi import Request

from vendor_catalog_app.core.env import (
    TVENDOR_BOOTSTRAP_DIAGNOSTICS_ENABLED,
    TVENDOR_BOOTSTRAP_DIAGNOSTICS_TOKEN,
    get_env,
    get_env_bool,
)

RUNTIME_REQUIRED_TABLES = (
    "core_vendor",
    "sec_user_role_map",
    "app_user_settings",
    "app_user_directory",
    "app_lookup_option",
)
RUNTIME_REQUIRED_VIEWS = (
    "vw_employee_directory",
)


def bootstrap_diagnostics_enabled(config) -> bool:
    return get_env_bool(
        TVENDOR_BOOTSTRAP_DIAGNOSTICS_ENABLED,
        default=bool(getattr(config, "is_dev_env", False)),
    )


def _request_matches_token(request: Request, *, token: str, header_name: str) -> bool:
    expected = str(token or "").strip()
    if not expected:
        return False
    header_value = str(request.headers.get(header_name, "")).strip()
    if header_value and hmac.compare_digest(header_value, expected):
        return True
    auth_header = str(request.headers.get("authorization", "")).strip()
    if auth_header.lower().startswith("bearer "):
        bearer = auth_header[7:].strip()
        if bearer and hmac.compare_digest(bearer, expected):
            return True
    return False


def bootstrap_diagnostics_authorized(request: Request, config) -> bool:
    if bootstrap_diagnostics_enabled(config):
        return True
    token = get_env(TVENDOR_BOOTSTRAP_DIAGNOSTICS_TOKEN, "")
    if not token:
        return False
    return _request_matches_token(
        request,
        token=token,
        header_name="x-tvendor-diagnostics-token",
    )


def connection_context(config) -> dict[str, bool]:
    warehouse_id_env = str(os.getenv("DATABRICKS_WAREHOUSE_ID", "")).strip()
    warehouse_resource_keys = ("sql-warehouse", "sql_warehouse", "SQL_WAREHOUSE", "SQL-WAREHOUSE")
    has_warehouse_resource = any(key in os.environ for key in warehouse_resource_keys)
    
    return {
        "has_server_hostname": bool(config.databricks_server_hostname),
        "has_http_path": bool(config.databricks_http_path),
        "has_warehouse_id_env": bool(warehouse_id_env),
        "has_warehouse_resource_binding": has_warehouse_resource,
        "warehouse_id_value": warehouse_id_env[:20] + "..." if len(warehouse_id_env) > 20 else warehouse_id_env,
        "has_pat_token": bool(str(config.databricks_token or "").strip()),
        "has_client_credentials": bool(
            str(config.databricks_client_id or "").strip()
            and str(config.databricks_client_secret or "").strip()
        ),
    }


def raw_env_key_presence() -> dict[str, bool]:
    keys = (
        "DATABRICKS_SERVER_HOSTNAME",
        "DATABRICKS_HOST",
        "DBSQL_SERVER_HOSTNAME",
        "DATABRICKS_HTTP_PATH",
        "DATABRICKS_SQL_HTTP_PATH",
        "DBSQL_HTTP_PATH",
        "SQL_HTTP_PATH",
        "DATABRICKS_WAREHOUSE_ID",
        "DATABRICKS_SQL_WAREHOUSE_ID",
        "SQL_WAREHOUSE_ID",
        "DBSQL_WAREHOUSE_ID",
        "sql-warehouse",
        "sql_warehouse",
        "SQL_WAREHOUSE",
        "SQL-WAREHOUSE",
    )
    return {key: key in os.environ for key in keys}


def path_preview(value: str, keep: int = 28) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if len(raw) <= keep:
        return raw
    return f"{raw[:keep]}..."


def candidate_env_values() -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in os.environ.items():
        upper = str(key).upper()
        if "HTTP_PATH" not in upper and "WAREHOUSE" not in upper:
            continue
        text = str(value or "").strip()
        if not text:
            continue
        out[str(key)] = path_preview(text, keep=40)
    return dict(sorted(out.items()))


def exception_chain(exc: BaseException, limit: int = 8) -> list[str]:
    chain: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and len(chain) < limit and id(current) not in seen:
        seen.add(id(current))
        message = str(current).strip()
        if message:
            chain.append(f"{current.__class__.__name__}: {message}")
        else:
            chain.append(current.__class__.__name__)
        current = current.__cause__ or current.__context__
    return chain


def probe(repo, relative_path: str, **format_args: Any) -> tuple[bool, list[str]]:
    try:
        repo._probe_file(relative_path, **format_args)
        return True, []
    except Exception as exc:
        return False, exception_chain(exc)


def diagnostic_recommendations(
    *,
    resolved_connection_context: dict[str, bool],
    connectivity_ok: bool,
    connectivity_errors: list[str],
    object_probe_failures: list[str],
) -> list[str]:
    recs: list[str] = []
    if not resolved_connection_context["has_server_hostname"]:
        recs.append("❌ Set DATABRICKS_SERVER_HOSTNAME (or DATABRICKS_HOST).")
    if not resolved_connection_context["has_http_path"] and not resolved_connection_context["has_warehouse_id_env"]:
        if not resolved_connection_context.get("has_warehouse_resource_binding", False):
            recs.append("❌ CRITICAL: No SQL warehouse configured. Add 'resources:' section to app.yaml with a warehouse binding.")
            recs.append("   Example: resources:\n     - name: sql-warehouse\n       sqlWarehouse:\n         id: your-warehouse-id")
        else:
            recs.append("⚠️ Warehouse resource binding exists but warehouse ID not detected in environment.")
    if not resolved_connection_context["has_pat_token"] and not resolved_connection_context["has_client_credentials"]:
        recs.append(
            "❌ No authentication configured. Use Databricks runtime OAuth (Databricks Apps), or configure DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET, or DATABRICKS_TOKEN."
        )
    if not connectivity_ok:
        for err in connectivity_errors:
            if "warehouse" in err.lower() or "http_path" in err.lower():
                recs.append("❌ WAREHOUSE ISSUE: " + err)
                if not resolved_connection_context.get("has_warehouse_resource_binding", False):
                    recs.append("   → Add warehouse resource binding to app.yaml (see above)")
                else:
                    recs.append("   → Verify the warehouse exists, is running, and the app service principal has CAN_USE permission")
            elif "auth" in err.lower() or "token" in err.lower() or "credential" in err.lower():
                recs.append("❌ AUTH ISSUE: " + err)
            elif "permission" in err.lower() or "denied" in err.lower():
                recs.append("❌ PERMISSION ISSUE: " + err)
                recs.append("   → Grant the app service principal CAN_USE on the warehouse")
                recs.append("   → Grant USE_CATALOG and USE_SCHEMA on Unity Catalog objects")
            else:
                recs.append("❌ " + err)
        
        if not any("warehouse" in err.lower() for err in connectivity_errors):
            recs.append("⚠️ If running in Databricks Apps, verify SQL warehouse resource binding exists and the app service principal has CAN_USE on that warehouse.")
        recs.append("⚠️ Verify Unity Catalog privileges: USE CATALOG, USE SCHEMA, and SELECT on required tables.")
    if object_probe_failures:
        recs.append(
            "FAIL: Schema objects missing or inaccessible. Run production bootstrap notebook: setup/production_push/production_push_setup.ipynb"
        )
        recs.append("   -> Use widgets: operation=apply, include_seed=true (include_optimize as needed).")
        recs.append("   -> Alternate notebook: setup/databricks/notebooks/v1_apply_database_changes.ipynb")
        recs.append(f"   → Missing/Failed: {', '.join(object_probe_failures[:5])}{'...' if len(object_probe_failures) > 5 else ''}")
    return recs


def build_bootstrap_diagnostics_payload(repo, config, identity: dict[str, str]) -> tuple[dict[str, Any], int]:
    resolved_connection_context = connection_context(config)
    checks: list[dict[str, Any]] = []

    checks.append(
        {
            "name": "config",
            "status": "pass",
            "details": [
                f"schema={config.fq_schema}",
                f"has_server_hostname={resolved_connection_context['has_server_hostname']}",
                f"has_http_path={resolved_connection_context['has_http_path']}",
                f"has_warehouse_id_env={resolved_connection_context['has_warehouse_id_env']}",
                f"warehouse_id_value={resolved_connection_context.get('warehouse_id_value', 'none')}",
                f"has_warehouse_resource_binding={resolved_connection_context.get('has_warehouse_resource_binding', False)}",
                f"has_client_credentials={resolved_connection_context['has_client_credentials']}",
                f"has_pat_token={resolved_connection_context['has_pat_token']}",
            ],
        }
    )

    connectivity_ok, connectivity_errors = probe(repo, "health/select_connectivity_check.sql")
    checks.append(
        {
            "name": "connectivity_probe",
            "status": "pass" if connectivity_ok else "fail",
            "details": ["SELECT 1 succeeded"] if connectivity_ok else connectivity_errors,
        }
    )

    object_probe_failures: list[str] = []
    if connectivity_ok:
        for table_name in RUNTIME_REQUIRED_TABLES:
            resolved_table_name = repo._table(table_name)
            ok, errors = probe(
                repo,
                "health/select_runtime_table_probe.sql",
                table_name=resolved_table_name,
            )
            if not ok:
                object_probe_failures.append(resolved_table_name)
            checks.append(
                {
                    "name": f"table_probe:{resolved_table_name}",
                    "status": "pass" if ok else "fail",
                    "details": ["table accessible"] if ok else errors,
                }
            )
        for view_name in RUNTIME_REQUIRED_VIEWS:
            resolved_view_name = repo._table(view_name)
            ok, errors = probe(
                repo,
                "health/select_runtime_employee_directory_probe.sql",
                employee_directory_view=resolved_view_name,
            )
            if not ok:
                object_probe_failures.append(resolved_view_name)
            checks.append(
                {
                    "name": f"view_probe:{resolved_view_name}",
                    "status": "pass" if ok else "fail",
                    "details": ["view accessible"] if ok else errors,
                }
            )

        offering_table = repo._table("core_vendor_offering")
        ok, errors = probe(
            repo,
            "health/select_runtime_offering_columns_probe.sql",
            core_vendor_offering=offering_table,
        )
        if not ok:
            object_probe_failures.append(f"{offering_table}.business_unit/service_type")
        checks.append(
            {
                "name": f"column_probe:{offering_table}.business_unit,service_type",
                "status": "pass" if ok else "fail",
                "details": ["columns accessible"] if ok else errors,
            }
        )

        lookup_table = repo._table("app_lookup_option")
        ok, errors = probe(
            repo,
            "health/select_runtime_lookup_scd_probe.sql",
            app_lookup_option=lookup_table,
        )
        if not ok:
            object_probe_failures.append(f"{lookup_table}.valid_from_ts/valid_to_ts/is_current/deleted_flag")
        checks.append(
            {
                "name": f"column_probe:{lookup_table}.valid_from_ts,valid_to_ts,is_current,deleted_flag",
                "status": "pass" if ok else "fail",
                "details": ["columns accessible"] if ok else errors,
            }
        )

    ok = connectivity_ok and not object_probe_failures
    recommendations = diagnostic_recommendations(
        resolved_connection_context=resolved_connection_context,
        connectivity_ok=connectivity_ok,
        connectivity_errors=connectivity_errors,
        object_probe_failures=object_probe_failures,
    )
    payload = {
        "ok": ok,
        "mode": "local" if config.use_local_db else "databricks",
        "schema": config.fq_schema,
        "principal": identity.get("principal") or None,
        "auth_context": {
            "forwarded_email": bool(identity.get("email")),
            "forwarded_network_id": bool(identity.get("network_id")),
        },
        "connection_context": resolved_connection_context,
        "resolved_connection": {
            "server_hostname_preview": path_preview(config.databricks_server_hostname, keep=40),
            "http_path_preview": path_preview(config.databricks_http_path, keep=60),
            "raw_env_key_presence": raw_env_key_presence(),
            "candidate_env_values": candidate_env_values(),
        },
        "checks": checks,
        "recommendations": recommendations,
    }
    return payload, (200 if ok else 503)
