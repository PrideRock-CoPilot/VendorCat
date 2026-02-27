"""Observability and performance monitoring views."""

from __future__ import annotations

import json
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from apps.core.observability import METRICS


@require_http_methods(["GET"])
def metrics_prometheus(request: HttpRequest) -> HttpResponse:
    """
    Prometheus metrics endpoint.
    Returns metrics in OpenMetrics text format.
    """
    content = METRICS.render_prometheus()
    return HttpResponse(content, content_type="text/plain; version=0.0.4; charset=utf-8")


@require_http_methods(["GET"])
def performance_summary_json(request: HttpRequest) -> JsonResponse:
    """
    JSON summary of performance metrics.
    Used for dashboard visualization.
    """
    summary = {
        "timestamp_iso": "",  # Could add time.time()
        "http_routes": [],
        "db_operations": [],
        "recommendations": [],
    }

    # Extract HTTP route metrics
    with METRICS._lock:
        for (path, method), sum_ms in sorted(METRICS._http_sum_ms.items()):
            totals = [
                count
                for (p, m, status), count in METRICS._http_totals.items()
                if p == path and m == method
            ]
            total_requests = sum(totals) if totals else 1
            avg_ms = sum_ms / total_requests if total_requests > 0 else 0

            summary["http_routes"].append(
                {
                    "path": path,
                    "method": method,
                    "avg_ms": round(avg_ms, 2),
                    "total_requests": total_requests,
                    "total_time_ms": round(sum_ms, 2),
                    "p95_slow": avg_ms > 500,
                }
            )

        # Extract DB operation metrics
        for operation, sum_ms in sorted(METRICS._db_sum_ms.items()):
            total_ops = METRICS._db_totals.get(operation, 1)
            avg_ms = sum_ms / total_ops if total_ops > 0 else 0

            summary["db_operations"].append(
                {
                    "operation": operation,
                    "avg_ms": round(avg_ms, 2),
                    "total_ops": total_ops,
                    "total_time_ms": round(sum_ms, 2),
                    "p95_slow": avg_ms > 250,
                }
            )

        # Generate recommendations
        slow_routes = [r for r in summary["http_routes"] if r["p95_slow"]]
        slow_ops = [o for o in summary["db_operations"] if o["p95_slow"]]

        if slow_routes:
            summary["recommendations"].append(
                {
                    "type": "slow_routes",
                    "severity": "warning",
                    "message": f"{len(slow_routes)} route(s) exceeding 500ms threshold",
                    "routes": [r["path"] for r in slow_routes],
                }
            )

        if slow_ops:
            summary["recommendations"].append(
                {
                    "type": "slow_db",
                    "severity": "warning",
                    "message": f"{len(slow_ops)} DB operation(s) exceeding 250ms threshold",
                    "operations": [o["operation"] for o in slow_ops],
                }
            )

    return JsonResponse(summary)
