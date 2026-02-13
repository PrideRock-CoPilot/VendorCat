from __future__ import annotations

import logging
import math
import re
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from vendor_catalog_app.core.env import (
    TVENDOR_ALERTS_ENABLED,
    TVENDOR_ALERT_COOLDOWN_SEC,
    TVENDOR_ALERT_DB_AVG_MS,
    TVENDOR_ALERT_ERROR_RATE_PCT,
    TVENDOR_ALERT_MIN_REQUESTS,
    TVENDOR_ALERT_REQUEST_P95_MS,
    TVENDOR_ALERT_WINDOW_SEC,
    TVENDOR_METRICS_ENABLED,
    TVENDOR_METRICS_PROMETHEUS_ENABLED,
    TVENDOR_METRICS_PROMETHEUS_PATH,
    TVENDOR_STATSD_ENABLED,
    TVENDOR_STATSD_HOST,
    TVENDOR_STATSD_PORT,
    TVENDOR_STATSD_PREFIX,
    get_env,
    get_env_bool,
    get_env_float,
    get_env_int,
)


METRICS_LOGGER = logging.getLogger("vendor_catalog_app.metrics")
ALERT_LOGGER = logging.getLogger("vendor_catalog_app.alerts")

REQUEST_DURATION_BUCKETS_MS: tuple[float, ...] = (
    5.0,
    10.0,
    25.0,
    50.0,
    100.0,
    250.0,
    500.0,
    1000.0,
    2500.0,
    5000.0,
    10000.0,
)
DB_DURATION_BUCKETS_MS: tuple[float, ...] = (
    1.0,
    5.0,
    10.0,
    25.0,
    50.0,
    100.0,
    250.0,
    500.0,
    1000.0,
    2500.0,
)
ALERT_REQUEST_P95_MS = "request_p95_ms"
ALERT_ERROR_RATE_PCT = "error_rate_pct"
ALERT_DB_AVG_MS = "db_avg_ms"
_ALERT_NAMES: tuple[str, ...] = (
    ALERT_REQUEST_P95_MS,
    ALERT_ERROR_RATE_PCT,
    ALERT_DB_AVG_MS,
)


@dataclass
class _HistogramState:
    buckets: list[int]
    count: int = 0
    sum_value: float = 0.0


@dataclass
class _WindowSample:
    ts: float
    request_ms: float
    is_error: bool
    db_ms: float


class _StatsDClient:
    def __init__(self) -> None:
        self.enabled = get_env_bool(TVENDOR_STATSD_ENABLED, default=False)
        self._host = get_env(TVENDOR_STATSD_HOST, "127.0.0.1")
        self._port = get_env_int(TVENDOR_STATSD_PORT, default=8125, min_value=1, max_value=65535)
        raw_prefix = get_env(TVENDOR_STATSD_PREFIX, "tvendor")
        sanitized_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw_prefix).strip(".")
        self._prefix = sanitized_prefix or "tvendor"
        self._socket: socket.socket | None = None
        self._lock = threading.Lock()
        self._last_error_log = 0.0

    def counter(self, name: str, value: int = 1) -> None:
        if value <= 0:
            return
        self._send(f"{self._metric_name(name)}:{int(value)}|c")

    def timing_ms(self, name: str, value_ms: float) -> None:
        if value_ms < 0:
            return
        self._send(f"{self._metric_name(name)}:{float(value_ms):.2f}|ms")

    def _metric_name(self, name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "").strip())
        cleaned = cleaned.strip("._")
        if not cleaned:
            cleaned = "metric"
        return f"{self._prefix}.{cleaned}"

    def _ensure_socket(self) -> socket.socket:
        with self._lock:
            if self._socket is None:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setblocking(False)
                self._socket = sock
            return self._socket

    def _send(self, line: str) -> None:
        if not self.enabled:
            return
        try:
            sock = self._ensure_socket()
            sock.sendto(line.encode("utf-8", errors="ignore"), (self._host, self._port))
        except Exception:
            now = time.monotonic()
            if (now - self._last_error_log) >= 60.0:
                self._last_error_log = now
                METRICS_LOGGER.warning(
                    "Failed to emit StatsD metric. host=%s port=%s",
                    self._host,
                    self._port,
                    exc_info=True,
                )


class ObservabilityManager:
    def __init__(self) -> None:
        self.metrics_enabled = get_env_bool(TVENDOR_METRICS_ENABLED, default=True)
        self.prometheus_enabled = self.metrics_enabled and get_env_bool(
            TVENDOR_METRICS_PROMETHEUS_ENABLED,
            default=True,
        )
        metrics_path = get_env(TVENDOR_METRICS_PROMETHEUS_PATH, "/api/metrics") or "/api/metrics"
        if not metrics_path.startswith("/"):
            metrics_path = f"/{metrics_path}"
        self.prometheus_path = metrics_path
        self.alerts_enabled = get_env_bool(TVENDOR_ALERTS_ENABLED, default=True)
        self.alert_window_sec = get_env_int(TVENDOR_ALERT_WINDOW_SEC, default=300, min_value=10)
        self.alert_min_requests = get_env_int(TVENDOR_ALERT_MIN_REQUESTS, default=20, min_value=1)
        self.alert_cooldown_sec = get_env_int(TVENDOR_ALERT_COOLDOWN_SEC, default=300, min_value=10)
        self.alert_request_p95_ms = get_env_float(TVENDOR_ALERT_REQUEST_P95_MS, default=0.0, min_value=0.0)
        self.alert_error_rate_pct = get_env_float(TVENDOR_ALERT_ERROR_RATE_PCT, default=0.0, min_value=0.0)
        self.alert_db_avg_ms = get_env_float(TVENDOR_ALERT_DB_AVG_MS, default=0.0, min_value=0.0)
        self._lock = threading.Lock()
        self._started_ts = time.time()

        self._request_total: dict[tuple[str, str, str], int] = {}
        self._request_errors_total: dict[tuple[str, str], int] = {}
        self._request_duration: dict[tuple[str, str], _HistogramState] = {}
        self._db_calls_total: dict[tuple[str, str], int] = {}
        self._db_cache_hits_total: dict[tuple[str, str], int] = {}
        self._db_errors_total: dict[tuple[str, str], int] = {}
        self._db_duration: dict[tuple[str, str], _HistogramState] = {}

        self._alert_breaches_total: dict[str, int] = {name: 0 for name in _ALERT_NAMES}
        self._alert_active: dict[str, int] = {name: 0 for name in _ALERT_NAMES}
        self._alert_state: dict[str, bool] = {name: False for name in _ALERT_NAMES}
        self._alert_last_log_ts: dict[str, float] = {}
        self._window: deque[_WindowSample] = deque()

        self._statsd = _StatsDClient()

    @staticmethod
    def _clean_label(value: str, *, default: str = "unknown", max_len: int = 160) -> str:
        text = str(value or "").strip()
        if not text:
            text = default
        text = text.replace("\n", " ").replace("\r", " ")
        if len(text) > max_len:
            text = f"{text[: max_len - 3]}..."
        return text

    @staticmethod
    def _status_class(status_code: int) -> str:
        try:
            code = int(status_code)
        except Exception:
            return "0xx"
        if code < 100:
            return "0xx"
        return f"{code // 100}xx"

    @staticmethod
    def _prometheus_escape(value: str) -> str:
        return (
            str(value)
            .replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace('"', '\\"')
        )

    @classmethod
    def _prom_labels(cls, labels: dict[str, str] | None = None) -> str:
        if not labels:
            return ""
        parts = [f'{key}="{cls._prometheus_escape(value)}"' for key, value in labels.items()]
        return "{" + ",".join(parts) + "}"

    @staticmethod
    def _prom_float(value: float) -> str:
        if math.isfinite(value):
            return f"{float(value):.6f}".rstrip("0").rstrip(".")
        return "0"

    @staticmethod
    def _observe_histogram(
        store: dict[tuple[str, str], _HistogramState],
        key: tuple[str, str],
        *,
        value: float,
        buckets: tuple[float, ...],
    ) -> None:
        state = store.get(key)
        if state is None:
            state = _HistogramState(buckets=[0 for _ in buckets])
            store[key] = state
        state.count += 1
        state.sum_value += float(value)
        for idx, upper in enumerate(buckets):
            if value <= upper:
                state.buckets[idx] += 1
                return

    @staticmethod
    def _counter_inc(store: dict[tuple[str, str], int], key: tuple[str, str], amount: int = 1) -> None:
        store[key] = int(store.get(key, 0)) + int(amount)

    @staticmethod
    def _counter_inc3(store: dict[tuple[str, str, str], int], key: tuple[str, str, str], amount: int = 1) -> None:
        store[key] = int(store.get(key, 0)) + int(amount)

    def record_request(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        elapsed_ms: float,
        db_calls: int,
        db_total_ms: float,
        db_cache_hits: int,
        db_errors: int,
    ) -> None:
        method_label = self._clean_label(str(method or "").upper(), default="UNKNOWN", max_len=16)
        path_label = self._clean_label(path, default="/", max_len=160)
        status_class = self._status_class(status_code)
        total_ms = max(0.0, float(elapsed_ms))
        db_calls_value = max(0, int(db_calls))
        db_total_value = max(0.0, float(db_total_ms))
        db_cache_hits_value = max(0, int(db_cache_hits))
        db_errors_value = max(0, int(db_errors))
        is_error = int(status_code) >= 500
        now = time.monotonic()

        if self.metrics_enabled or self.alerts_enabled:
            with self._lock:
                if self.metrics_enabled:
                    self._counter_inc3(
                        self._request_total,
                        (method_label, path_label, status_class),
                        amount=1,
                    )
                    self._observe_histogram(
                        self._request_duration,
                        (method_label, path_label),
                        value=total_ms,
                        buckets=REQUEST_DURATION_BUCKETS_MS,
                    )
                    if is_error:
                        self._counter_inc(self._request_errors_total, (method_label, path_label), amount=1)
                    if db_calls_value > 0:
                        self._counter_inc(
                            self._db_calls_total,
                            (method_label, path_label),
                            amount=db_calls_value,
                        )
                    if db_total_value > 0:
                        self._observe_histogram(
                            self._db_duration,
                            (method_label, path_label),
                            value=db_total_value,
                            buckets=DB_DURATION_BUCKETS_MS,
                        )
                    if db_cache_hits_value > 0:
                        self._counter_inc(
                            self._db_cache_hits_total,
                            (method_label, path_label),
                            amount=db_cache_hits_value,
                        )
                    if db_errors_value > 0:
                        self._counter_inc(
                            self._db_errors_total,
                            (method_label, path_label),
                            amount=db_errors_value,
                        )

                if self.alerts_enabled:
                    self._window.append(
                        _WindowSample(
                            ts=now,
                            request_ms=total_ms,
                            is_error=is_error,
                            db_ms=db_total_value,
                        )
                    )
                    self._prune_window_locked(now)
                    self._evaluate_alerts_locked(now)

        if self.metrics_enabled and self._statsd.enabled:
            self._statsd.counter("http.requests_total", 1)
            self._statsd.counter(f"http.status_{status_class}", 1)
            self._statsd.timing_ms("http.request_duration_ms", total_ms)
            if is_error:
                self._statsd.counter("http.request_errors_total", 1)
            if db_calls_value > 0:
                self._statsd.counter("db.calls_total", db_calls_value)
            if db_total_value > 0:
                self._statsd.timing_ms("db.duration_ms", db_total_value)
            if db_cache_hits_value > 0:
                self._statsd.counter("db.cache_hits_total", db_cache_hits_value)
            if db_errors_value > 0:
                self._statsd.counter("db.errors_total", db_errors_value)

    def _prune_window_locked(self, now: float) -> None:
        cutoff = now - float(self.alert_window_sec)
        while self._window and self._window[0].ts < cutoff:
            self._window.popleft()

    def _evaluate_alerts_locked(self, now: float) -> None:
        total_requests = len(self._window)
        if total_requests < self.alert_min_requests:
            for name in _ALERT_NAMES:
                self._update_alert_state_locked(
                    name,
                    breached=False,
                    observed_value=None,
                    threshold_value=None,
                    sample_size=total_requests,
                    now=now,
                )
            return

        request_times = sorted(sample.request_ms for sample in self._window)
        p95_index = max(0, min(len(request_times) - 1, math.ceil(len(request_times) * 0.95) - 1))
        request_p95_ms = float(request_times[p95_index]) if request_times else 0.0
        error_count = sum(1 for sample in self._window if sample.is_error)
        error_rate_pct = (float(error_count) * 100.0 / float(total_requests)) if total_requests else 0.0
        db_avg_ms = sum(sample.db_ms for sample in self._window) / float(total_requests)

        threshold_defs = (
            (ALERT_REQUEST_P95_MS, request_p95_ms, self.alert_request_p95_ms),
            (ALERT_ERROR_RATE_PCT, error_rate_pct, self.alert_error_rate_pct),
            (ALERT_DB_AVG_MS, db_avg_ms, self.alert_db_avg_ms),
        )
        for name, observed, threshold in threshold_defs:
            if float(threshold) <= 0:
                self._update_alert_state_locked(
                    name,
                    breached=False,
                    observed_value=observed,
                    threshold_value=threshold,
                    sample_size=total_requests,
                    now=now,
                )
                continue
            self._update_alert_state_locked(
                name,
                breached=bool(observed > float(threshold)),
                observed_value=observed,
                threshold_value=threshold,
                sample_size=total_requests,
                now=now,
            )

    def _update_alert_state_locked(
        self,
        alert_name: str,
        *,
        breached: bool,
        observed_value: float | None,
        threshold_value: float | None,
        sample_size: int,
        now: float,
    ) -> None:
        was_active = bool(self._alert_state.get(alert_name, False))
        self._alert_state[alert_name] = bool(breached)
        self._alert_active[alert_name] = 1 if breached else 0

        if breached:
            last_log = float(self._alert_last_log_ts.get(alert_name, 0.0))
            if (not was_active) or ((now - last_log) >= float(self.alert_cooldown_sec)):
                self._alert_last_log_ts[alert_name] = now
                self._alert_breaches_total[alert_name] = int(self._alert_breaches_total.get(alert_name, 0)) + 1
                ALERT_LOGGER.warning(
                    (
                        "Performance alert breached. alert=%s observed=%.2f threshold=%.2f "
                        "window_sec=%s sample_size=%s"
                    ),
                    alert_name,
                    float(observed_value or 0.0),
                    float(threshold_value or 0.0),
                    self.alert_window_sec,
                    sample_size,
                    extra={
                        "event": "performance_alert",
                        "alert_name": alert_name,
                        "observed": round(float(observed_value or 0.0), 2),
                        "threshold": round(float(threshold_value or 0.0), 2),
                        "window_sec": self.alert_window_sec,
                        "sample_size": int(sample_size),
                    },
                )
            return

        if was_active:
            ALERT_LOGGER.info(
                "Performance alert recovered. alert=%s observed=%.2f threshold=%.2f sample_size=%s",
                alert_name,
                float(observed_value or 0.0),
                float(threshold_value or 0.0),
                sample_size,
                extra={
                    "event": "performance_alert_recovered",
                    "alert_name": alert_name,
                    "observed": round(float(observed_value or 0.0), 2),
                    "threshold": round(float(threshold_value or 0.0), 2),
                    "sample_size": int(sample_size),
                },
            )

    def render_prometheus(self) -> str:
        if not self.prometheus_enabled:
            return ""

        with self._lock:
            request_total = dict(self._request_total)
            request_errors_total = dict(self._request_errors_total)
            request_duration = {
                key: _HistogramState(buckets=list(state.buckets), count=state.count, sum_value=state.sum_value)
                for key, state in self._request_duration.items()
            }
            db_calls_total = dict(self._db_calls_total)
            db_cache_hits_total = dict(self._db_cache_hits_total)
            db_errors_total = dict(self._db_errors_total)
            db_duration = {
                key: _HistogramState(buckets=list(state.buckets), count=state.count, sum_value=state.sum_value)
                for key, state in self._db_duration.items()
            }
            alert_breaches_total = dict(self._alert_breaches_total)
            alert_active = dict(self._alert_active)

        lines: list[str] = []
        lines.append("# HELP tvendor_http_requests_total Total HTTP requests.")
        lines.append("# TYPE tvendor_http_requests_total counter")
        for (method, path, status_class), value in sorted(request_total.items()):
            labels = self._prom_labels({"method": method, "path": path, "status_class": status_class})
            lines.append(f"tvendor_http_requests_total{labels} {int(value)}")

        lines.append("# HELP tvendor_http_request_errors_total Total HTTP 5xx requests.")
        lines.append("# TYPE tvendor_http_request_errors_total counter")
        for (method, path), value in sorted(request_errors_total.items()):
            labels = self._prom_labels({"method": method, "path": path})
            lines.append(f"tvendor_http_request_errors_total{labels} {int(value)}")

        lines.append("# HELP tvendor_http_request_duration_ms HTTP request duration in milliseconds.")
        lines.append("# TYPE tvendor_http_request_duration_ms histogram")
        for (method, path), state in sorted(request_duration.items()):
            labels_base = {"method": method, "path": path}
            cumulative = 0
            for idx, upper in enumerate(REQUEST_DURATION_BUCKETS_MS):
                cumulative += int(state.buckets[idx])
                labels = dict(labels_base)
                labels["le"] = self._prom_float(upper)
                lines.append(
                    f"tvendor_http_request_duration_ms_bucket{self._prom_labels(labels)} {cumulative}"
                )
            labels_inf = dict(labels_base)
            labels_inf["le"] = "+Inf"
            lines.append(
                f"tvendor_http_request_duration_ms_bucket{self._prom_labels(labels_inf)} {int(state.count)}"
            )
            lines.append(
                f"tvendor_http_request_duration_ms_sum{self._prom_labels(labels_base)} "
                f"{self._prom_float(state.sum_value)}"
            )
            lines.append(
                f"tvendor_http_request_duration_ms_count{self._prom_labels(labels_base)} {int(state.count)}"
            )

        lines.append("# HELP tvendor_db_calls_total Total DB calls per request path.")
        lines.append("# TYPE tvendor_db_calls_total counter")
        for (method, path), value in sorted(db_calls_total.items()):
            labels = self._prom_labels({"method": method, "path": path})
            lines.append(f"tvendor_db_calls_total{labels} {int(value)}")

        lines.append("# HELP tvendor_db_cache_hits_total Total DB cache hits per request path.")
        lines.append("# TYPE tvendor_db_cache_hits_total counter")
        for (method, path), value in sorted(db_cache_hits_total.items()):
            labels = self._prom_labels({"method": method, "path": path})
            lines.append(f"tvendor_db_cache_hits_total{labels} {int(value)}")

        lines.append("# HELP tvendor_db_errors_total Total DB errors per request path.")
        lines.append("# TYPE tvendor_db_errors_total counter")
        for (method, path), value in sorted(db_errors_total.items()):
            labels = self._prom_labels({"method": method, "path": path})
            lines.append(f"tvendor_db_errors_total{labels} {int(value)}")

        lines.append("# HELP tvendor_db_duration_ms Total DB duration in milliseconds per request.")
        lines.append("# TYPE tvendor_db_duration_ms histogram")
        for (method, path), state in sorted(db_duration.items()):
            labels_base = {"method": method, "path": path}
            cumulative = 0
            for idx, upper in enumerate(DB_DURATION_BUCKETS_MS):
                cumulative += int(state.buckets[idx])
                labels = dict(labels_base)
                labels["le"] = self._prom_float(upper)
                lines.append(
                    f"tvendor_db_duration_ms_bucket{self._prom_labels(labels)} {cumulative}"
                )
            labels_inf = dict(labels_base)
            labels_inf["le"] = "+Inf"
            lines.append(
                f"tvendor_db_duration_ms_bucket{self._prom_labels(labels_inf)} {int(state.count)}"
            )
            lines.append(
                f"tvendor_db_duration_ms_sum{self._prom_labels(labels_base)} "
                f"{self._prom_float(state.sum_value)}"
            )
            lines.append(f"tvendor_db_duration_ms_count{self._prom_labels(labels_base)} {int(state.count)}")

        lines.append("# HELP tvendor_alert_breaches_total Total number of alert threshold breaches.")
        lines.append("# TYPE tvendor_alert_breaches_total counter")
        for alert_name, value in sorted(alert_breaches_total.items()):
            labels = self._prom_labels({"alert": alert_name})
            lines.append(f"tvendor_alert_breaches_total{labels} {int(value)}")

        lines.append("# HELP tvendor_alert_active Alert active state (1 active, 0 inactive).")
        lines.append("# TYPE tvendor_alert_active gauge")
        for alert_name, value in sorted(alert_active.items()):
            labels = self._prom_labels({"alert": alert_name})
            lines.append(f"tvendor_alert_active{labels} {int(value)}")

        lines.append("# HELP tvendor_uptime_seconds Process uptime in seconds.")
        lines.append("# TYPE tvendor_uptime_seconds gauge")
        lines.append(f"tvendor_uptime_seconds {int(max(0, time.time() - self._started_ts))}")
        lines.append("")
        return "\n".join(lines)

    def health_snapshot(self) -> dict[str, Any]:
        with self._lock:
            active_alerts = sorted(
                [name for name, active in self._alert_active.items() if int(active) > 0]
            )
            alert_breaches_total = {name: int(value) for name, value in self._alert_breaches_total.items()}
            window_sample_size = len(self._window)

        return {
            "metrics_enabled": bool(self.metrics_enabled),
            "prometheus_enabled": bool(self.prometheus_enabled),
            "prometheus_path": self.prometheus_path if self.prometheus_enabled else None,
            "statsd_enabled": bool(self._statsd.enabled),
            "alerts_enabled": bool(self.alerts_enabled),
            "alert_window_sec": int(self.alert_window_sec),
            "alert_min_requests": int(self.alert_min_requests),
            "alert_cooldown_sec": int(self.alert_cooldown_sec),
            "active_alert_count": len(active_alerts),
            "active_alerts": active_alerts,
            "alert_breaches_total": alert_breaches_total,
            "window_sample_size": int(window_sample_size),
            "uptime_seconds": int(max(0, time.time() - self._started_ts)),
        }


@lru_cache(maxsize=1)
def get_observability_manager() -> ObservabilityManager:
    return ObservabilityManager()
