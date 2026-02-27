from __future__ import annotations

import os
import threading
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

HISTOGRAM_BUCKETS_MS: tuple[float, ...] = (5, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000)

SEARCH_THRESHOLD_ENV = {
    "local": "VC_ALERT_P95_MS_SEARCH_LOCAL",
    "databricks": "VC_ALERT_P95_MS_SEARCH_DATABRICKS",
}
IMPORT_PREVIEW_THRESHOLD_ENV = {
    "local": "VC_ALERT_P95_MS_IMPORT_PREVIEW_LOCAL",
    "databricks": "VC_ALERT_P95_MS_IMPORT_PREVIEW_DATABRICKS",
}
REPORT_PREVIEW_THRESHOLD_ENV = {
    "local": "VC_ALERT_P95_MS_REPORT_PREVIEW_LOCAL",
    "databricks": "VC_ALERT_P95_MS_REPORT_PREVIEW_DATABRICKS",
}

THRESHOLD_DEFAULTS_MS: dict[str, dict[str, int]] = {
    "search": {"local": 250, "databricks": 500},
    "import_preview": {"local": 2000, "databricks": 5000},
    "report_preview": {"local": 1500, "databricks": 4000},
}


def _sanitize_label(value: str) -> str:
    return value.replace('"', "'").replace("\\", "\\\\")


def _bucket_boundaries() -> tuple[float, ...]:
    return HISTOGRAM_BUCKETS_MS + (float("inf"),)


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._http_totals: dict[tuple[str, str, int], int] = defaultdict(int)
        self._http_sum_ms: dict[tuple[str, str], float] = defaultdict(float)
        self._http_buckets: dict[tuple[str, str], dict[float, int]] = defaultdict(lambda: defaultdict(int))

        self._db_totals: dict[str, int] = defaultdict(int)
        self._db_sum_ms: dict[str, float] = defaultdict(float)
        self._db_buckets: dict[str, dict[float, int]] = defaultdict(lambda: defaultdict(int))

    def observe_http(self, path: str, method: str, status: int, duration_ms: float) -> None:
        with self._lock:
            route_key = (path, method.upper())
            self._http_totals[(path, method.upper(), status)] += 1
            self._http_sum_ms[route_key] += duration_ms
            for bucket in _bucket_boundaries():
                if duration_ms <= bucket:
                    self._http_buckets[route_key][bucket] += 1

    def observe_db(self, operation: str, duration_ms: float) -> None:
        op = operation.lower().strip() or "unknown"
        with self._lock:
            self._db_totals[op] += 1
            self._db_sum_ms[op] += duration_ms
            for bucket in _bucket_boundaries():
                if duration_ms <= bucket:
                    self._db_buckets[op][bucket] += 1

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            lines.extend(
                [
                    "# HELP vc_http_request_total Total HTTP requests by path/method/status",
                    "# TYPE vc_http_request_total counter",
                ]
            )
            if not self._http_totals:
                lines.append('vc_http_request_total{path="none",method="none",status="0"} 0')
            else:
                for (path, method, status), count in sorted(self._http_totals.items()):
                    lines.append(
                        "vc_http_request_total"
                        f'{{path="{_sanitize_label(path)}",method="{_sanitize_label(method)}",status="{status}"}} {count}'
                    )

            lines.extend(
                [
                    "# HELP vc_http_request_duration_ms_bucket HTTP request latency histogram buckets",
                    "# TYPE vc_http_request_duration_ms_bucket histogram",
                ]
            )
            if not self._http_sum_ms:
                for bucket in _bucket_boundaries():
                    le_value = "+Inf" if bucket == float("inf") else f"{int(bucket)}"
                    lines.append(
                        "vc_http_request_duration_ms_bucket"
                        f'{{path="none",method="none",le="{le_value}"}} 0'
                    )
                lines.append('vc_http_request_duration_ms_count{path="none",method="none"} 0')
                lines.append('vc_http_request_duration_ms_sum{path="none",method="none"} 0')
            else:
                for (path, method), sum_ms in sorted(self._http_sum_ms.items()):
                    bucket_counts = self._http_buckets[(path, method)]
                    total_count = 0
                    for bucket in _bucket_boundaries():
                        count = bucket_counts.get(bucket, 0)
                        total_count = max(total_count, count)
                        le_value = "+Inf" if bucket == float("inf") else f"{int(bucket)}"
                        lines.append(
                            "vc_http_request_duration_ms_bucket"
                            f'{{path="{_sanitize_label(path)}",method="{_sanitize_label(method)}",le="{le_value}"}} {count}'
                        )
                    lines.append(
                        "vc_http_request_duration_ms_count"
                        f'{{path="{_sanitize_label(path)}",method="{_sanitize_label(method)}"}} {total_count}'
                    )
                    lines.append(
                        "vc_http_request_duration_ms_sum"
                        f'{{path="{_sanitize_label(path)}",method="{_sanitize_label(method)}"}} {sum_ms:.6f}'
                    )

            lines.extend(
                [
                    "# HELP vc_db_query_total Total DB operations by operation type",
                    "# TYPE vc_db_query_total counter",
                ]
            )
            if not self._db_totals:
                lines.append('vc_db_query_total{operation="none"} 0')
            else:
                for operation, count in sorted(self._db_totals.items()):
                    lines.append(f'vc_db_query_total{{operation="{_sanitize_label(operation)}"}} {count}')

            lines.extend(
                [
                    "# HELP vc_db_query_duration_ms_bucket DB operation latency histogram buckets",
                    "# TYPE vc_db_query_duration_ms_bucket histogram",
                ]
            )
            if not self._db_sum_ms:
                for bucket in _bucket_boundaries():
                    le_value = "+Inf" if bucket == float("inf") else f"{int(bucket)}"
                    lines.append(f'vc_db_query_duration_ms_bucket{{operation="none",le="{le_value}"}} 0')
                lines.append('vc_db_query_duration_ms_count{operation="none"} 0')
                lines.append('vc_db_query_duration_ms_sum{operation="none"} 0')
            else:
                for operation, sum_ms in sorted(self._db_sum_ms.items()):
                    bucket_counts = self._db_buckets[operation]
                    total_count = 0
                    for bucket in _bucket_boundaries():
                        count = bucket_counts.get(bucket, 0)
                        total_count = max(total_count, count)
                        le_value = "+Inf" if bucket == float("inf") else f"{int(bucket)}"
                        lines.append(
                            "vc_db_query_duration_ms_bucket"
                            f'{{operation="{_sanitize_label(operation)}",le="{le_value}"}} {count}'
                        )
                    lines.append(
                        "vc_db_query_duration_ms_count"
                        f'{{operation="{_sanitize_label(operation)}"}} {total_count}'
                    )
                    lines.append(
                        "vc_db_query_duration_ms_sum"
                        f'{{operation="{_sanitize_label(operation)}"}} {sum_ms:.6f}'
                    )

        return "\n".join(lines) + "\n"


METRICS = MetricsRegistry()


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, str(default))).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def threshold_config(runtime_profile: str) -> dict[str, int]:
    profile = runtime_profile if runtime_profile in {"local", "databricks"} else "local"
    return {
        "search": _env_int(SEARCH_THRESHOLD_ENV[profile], THRESHOLD_DEFAULTS_MS["search"][profile]),
        "import_preview": _env_int(
            IMPORT_PREVIEW_THRESHOLD_ENV[profile],
            THRESHOLD_DEFAULTS_MS["import_preview"][profile],
        ),
        "report_preview": _env_int(
            REPORT_PREVIEW_THRESHOLD_ENV[profile],
            THRESHOLD_DEFAULTS_MS["report_preview"][profile],
        ),
    }


def evaluate_alert_thresholds(runtime_profile: str, observed_p95_ms: dict[str, float]) -> dict[str, dict[str, float | bool]]:
    thresholds = threshold_config(runtime_profile)
    results: dict[str, dict[str, float | bool]] = {}
    for key, threshold_value in thresholds.items():
        observed_value = float(observed_p95_ms.get(key, 0.0))
        results[key] = {
            "threshold_ms": float(threshold_value),
            "observed_p95_ms": observed_value,
            "pass": observed_value <= float(threshold_value),
        }
    return results


def latest_schema_version(canonical_root: Path) -> str:
    files: Iterable[Path] = sorted(canonical_root.glob("*.sql"))
    last = ""
    for file_path in files:
        stem = file_path.stem
        if stem > last:
            last = stem
    return last or "unknown"
