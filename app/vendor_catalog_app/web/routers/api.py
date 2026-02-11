from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from vendor_catalog_app.repository import SchemaBootstrapRequiredError
from vendor_catalog_app.web.services import (
    ensure_session_started,
    get_config,
    get_repo,
    get_user_context,
    resolve_databricks_request_identity,
)


router = APIRouter(prefix="/api")
RUNTIME_REQUIRED_TABLES = (
    "core_vendor",
    "sec_user_role_map",
    "app_user_settings",
    "app_user_directory",
    "app_lookup_option",
)


def _normalize_limit(limit: int) -> int:
    return max(1, min(int(limit or 20), 50))


def _connection_context(config) -> dict[str, bool]:
    return {
        "has_server_hostname": bool(config.databricks_server_hostname),
        "has_http_path": bool(config.databricks_http_path),
        "has_warehouse_id_env": bool(str(os.getenv("DATABRICKS_WAREHOUSE_ID", "")).strip()),
        "has_pat_token": bool(str(config.databricks_token or "").strip()),
        "has_client_credentials": bool(
            str(config.databricks_client_id or "").strip()
            and str(config.databricks_client_secret or "").strip()
        ),
    }


def _exception_chain(exc: BaseException, limit: int = 8) -> list[str]:
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


def _probe(repo, relative_path: str, **format_args: Any) -> tuple[bool, list[str]]:
    try:
        repo._probe_file(relative_path, **format_args)
        return True, []
    except Exception as exc:
        return False, _exception_chain(exc)


def _diagnostic_recommendations(
    *,
    connection_context: dict[str, bool],
    connectivity_ok: bool,
    object_probe_failures: list[str],
) -> list[str]:
    recs: list[str] = []
    if not connection_context["has_server_hostname"]:
        recs.append("Set DATABRICKS_SERVER_HOSTNAME (or DATABRICKS_HOST).")
    if not connection_context["has_http_path"] and not connection_context["has_warehouse_id_env"]:
        recs.append("Set DATABRICKS_HTTP_PATH or bind DATABRICKS_WAREHOUSE_ID via app.yaml valueFrom: sql-warehouse.")
    if not connection_context["has_pat_token"] and not connection_context["has_client_credentials"]:
        recs.append(
            "Use Databricks runtime OAuth (Databricks Apps), or configure DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET, or DATABRICKS_TOKEN."
        )
    if not connectivity_ok:
        recs.append(
            "If running in Databricks Apps, verify SQL warehouse resource binding exists and the app service principal has Can use on that warehouse."
        )
        recs.append(
            "Verify Unity Catalog privileges for the app service principal: USE CATALOG, USE SCHEMA, and required table permissions."
        )
    if object_probe_failures:
        recs.append(
            "Run bootstrap/migration SQL for this schema: setup/databricks/001_create_databricks_schema.sql through setup/databricks/006_add_offering_data_flow.sql."
        )
    return recs


@router.get("/health")
def api_health(request: Request):
    repo = get_repo()
    config = get_config()
    identity = resolve_databricks_request_identity(request)
    payload = {
        "ok": True,
        "mode": "local" if config.use_local_db else "databricks",
        "schema": config.fq_schema,
        "principal": identity.get("principal") or None,
        "auth_context": {
            "forwarded_email": bool(identity.get("email")),
            "forwarded_network_id": bool(identity.get("network_id")),
        },
        "connection_context": _connection_context(config),
    }
    try:
        repo.ensure_runtime_tables()
        return JSONResponse(payload, status_code=200)
    except SchemaBootstrapRequiredError as exc:
        payload["ok"] = False
        payload["error"] = str(exc)
        return JSONResponse(payload, status_code=503)
    except Exception as exc:
        payload["ok"] = False
        payload["error"] = f"Connection check failed: {exc}"
        return JSONResponse(payload, status_code=503)


@router.get("/bootstrap-diagnostics")
def api_bootstrap_diagnostics(request: Request):
    repo = get_repo()
    config = get_config()
    identity = resolve_databricks_request_identity(request)
    connection_context = _connection_context(config)
    checks: list[dict[str, Any]] = []

    checks.append(
        {
            "name": "config",
            "status": "pass",
            "details": [
                f"schema={config.fq_schema}",
                f"has_server_hostname={connection_context['has_server_hostname']}",
                f"has_http_path={connection_context['has_http_path']}",
                f"has_warehouse_id_env={connection_context['has_warehouse_id_env']}",
                f"has_client_credentials={connection_context['has_client_credentials']}",
                f"has_pat_token={connection_context['has_pat_token']}",
            ],
        }
    )

    connectivity_ok, connectivity_errors = _probe(repo, "health/select_connectivity_check.sql")
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
            ok, errors = _probe(
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

        offering_table = repo._table("core_vendor_offering")
        ok, errors = _probe(
            repo,
            "health/select_runtime_offering_columns_probe.sql",
            core_vendor_offering=offering_table,
        )
        if not ok:
            object_probe_failures.append(f"{offering_table}.lob/service_type")
        checks.append(
            {
                "name": f"column_probe:{offering_table}.lob,service_type",
                "status": "pass" if ok else "fail",
                "details": ["columns accessible"] if ok else errors,
            }
        )

        lookup_table = repo._table("app_lookup_option")
        ok, errors = _probe(
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
    recommendations = _diagnostic_recommendations(
        connection_context=connection_context,
        connectivity_ok=connectivity_ok,
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
        "connection_context": connection_context,
        "checks": checks,
        "recommendations": recommendations,
    }
    return JSONResponse(payload, status_code=200 if ok else 503)


@router.get("/vendors/search")
def api_vendor_search(request: Request, q: str = "", limit: int = 20):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    rows = repo.search_vendors_typeahead(q=q, limit=_normalize_limit(limit)).to_dict("records")
    return JSONResponse({"items": rows})


@router.get("/offerings/search")
def api_offering_search(request: Request, vendor_id: str = "", q: str = "", limit: int = 20):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    rows = repo.search_offerings_typeahead(
        vendor_id=vendor_id.strip() or None,
        q=q,
        limit=_normalize_limit(limit),
    ).to_dict("records")
    return JSONResponse({"items": rows})


@router.get("/projects/search")
def api_project_search(request: Request, q: str = "", limit: int = 20):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    rows = repo.search_projects_typeahead(q=q, limit=_normalize_limit(limit)).to_dict("records")
    return JSONResponse({"items": rows})


@router.get("/users/search")
def api_user_search(request: Request, q: str = "", limit: int = 20):
    repo = get_repo()
    user = get_user_context(request)
    ensure_session_started(request, user)
    rows = repo.search_user_directory(q=q, limit=_normalize_limit(limit)).to_dict("records")
    return JSONResponse({"items": rows})
