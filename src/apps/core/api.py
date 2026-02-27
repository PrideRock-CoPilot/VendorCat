from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.core.config.env import get_runtime_settings, validate_runtime_settings
from apps.core.observability import METRICS, evaluate_alert_thresholds, latest_schema_version
from apps.core.responses import api_error
from apps.core.services.policy_engine import PolicyEngine
from apps.core.sql.adapter import create_sql_adapter
from apps.identity.services import build_policy_snapshot, sync_user_directory


def _identity_snapshot(request: HttpRequest):
    from apps.core.contracts.identity import resolve_identity_context

    identity = resolve_identity_context(request)
    sync_user_directory(identity)
    return build_policy_snapshot(identity)


def _require_observability_read(request: HttpRequest) -> JsonResponse | None:
    snapshot = _identity_snapshot(request)
    decision = PolicyEngine.decide(snapshot, "observability.read")
    if decision.allowed:
        return None
    return api_error(
        request,
        code="forbidden",
        message="Missing permission: observability.read",
        status=403,
    )


def health_live(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"ok": True, "service": "vendorcatalog-rebuild", "status": "live"})


def _readiness_payload() -> tuple[dict[str, object], int]:
    settings = get_runtime_settings()
    config_issues = validate_runtime_settings(settings)
    adapter = create_sql_adapter(settings)
    db_ok = adapter.ping() if not config_issues else False
    status = 200 if db_ok else 503
    return (
        {
            "ok": db_ok,
            "service": "vendorcatalog-rebuild",
            "status": "ready" if db_ok else "not_ready",
            "runtime_profile": settings.runtime_profile,
            "config_issues": config_issues,
        },
        status,
    )


def health_ready(request: HttpRequest) -> JsonResponse:
    payload, status = _readiness_payload()
    return JsonResponse(payload, status=status)


def health(request: HttpRequest) -> JsonResponse:
    ready = health_ready(request)
    payload = json.loads(ready.content.decode("utf-8"))
    payload["status"] = "healthy" if payload.get("ok") else "degraded"
    return JsonResponse(payload, status=ready.status_code)


def runtime_metadata(request: HttpRequest) -> JsonResponse:
    settings = get_runtime_settings()
    return JsonResponse(
        {
            "runtime_profile": settings.runtime_profile,
            "env": settings.env,
            "databricks_configured": bool(settings.databricks_host and settings.databricks_http_path),
            "local_duckdb_path": settings.local_duckdb_path,
            "config_issues": validate_runtime_settings(settings),
        }
    )


def observability_metadata(request: HttpRequest) -> JsonResponse:
    request_id = getattr(request, "request_id", "")
    payload, readiness_status = _readiness_payload()
    return JsonResponse(
        {
            "request_id": request_id,
            "readiness_status_code": readiness_status,
            "runtime": payload,
        }
    )


def metrics_payload(request: HttpRequest) -> HttpResponse:
    denied = _require_observability_read(request)
    if denied is not None:
        return denied
    return HttpResponse(
        METRICS.render_prometheus(),
        content_type="text/plain; version=0.0.4; charset=utf-8",
        status=200,
    )


def _latest_perf_observations() -> dict[str, float]:
    settings = get_runtime_settings()
    adapter = create_sql_adapter(settings)

    try:
        rows = adapter.query(
            "SELECT scenario_key, p95_ms, created_at FROM vc_perf_baseline WHERE runtime_profile = ?",
            (settings.runtime_profile,),
        ).rows
    except Exception:
        return {}

    latest_by_key: dict[str, tuple[float, datetime]] = {}
    for row in rows:
        scenario_key = str(row.get("scenario_key", "")).strip()
        if not scenario_key:
            continue

        try:
            p95_value = float(row.get("p95_ms", 0.0))
        except (TypeError, ValueError):
            p95_value = 0.0

        raw_created_at = row.get("created_at")
        if isinstance(raw_created_at, datetime):
            created_at = raw_created_at
        else:
            try:
                created_at = datetime.fromisoformat(str(raw_created_at))
            except (TypeError, ValueError):
                created_at = datetime.min

        existing = latest_by_key.get(scenario_key)
        if existing is None or created_at > existing[1]:
            latest_by_key[scenario_key] = (p95_value, created_at)

    return {key: value[0] for key, value in latest_by_key.items()}


def diagnostics_bootstrap(request: HttpRequest) -> JsonResponse:
    denied = _require_observability_read(request)
    if denied is not None:
        return denied

    settings = get_runtime_settings()
    config_issues = validate_runtime_settings(settings)
    schema_version = latest_schema_version(Path("src/schema/canonical"))
    observed = _latest_perf_observations()
    threshold_eval = evaluate_alert_thresholds(settings.runtime_profile, observed)

    return JsonResponse(
        {
            "request_id": str(getattr(request, "request_id", "")),
            "runtime_profile": settings.runtime_profile,
            "env": settings.env,
            "schema_version": schema_version,
            "config_issues": config_issues,
            "alert_threshold_evaluation": threshold_eval,
        }
    )
