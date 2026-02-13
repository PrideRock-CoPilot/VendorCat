from __future__ import annotations

import contextvars
from contextlib import contextmanager
from datetime import date, datetime
import hashlib
import logging
from pathlib import Path
import re
import sqlite3
import threading
import time
from typing import Any, Iterable

import pandas as pd
from databricks import sql as dbsql
try:
    from databricks.sdk.core import Config as DatabricksSDKConfig
    from databricks.sdk.core import oauth_service_principal
except Exception:  # pragma: no cover - optional until OAuth client credentials are used
    DatabricksSDKConfig = None
    oauth_service_principal = None

from vendor_catalog_app.infrastructure.cache import LruTtlCache
from vendor_catalog_app.core.config import AppConfig
from vendor_catalog_app.core.env import (
    TVENDOR_DB_POOL_ACQUIRE_TIMEOUT_SEC,
    TVENDOR_DB_POOL_ENABLED,
    TVENDOR_DB_POOL_IDLE_TTL_SEC,
    TVENDOR_DB_POOL_MAX_SIZE,
    TVENDOR_QUERY_CACHE_ENABLED,
    TVENDOR_QUERY_CACHE_MAX_ENTRIES,
    TVENDOR_QUERY_CACHE_TTL_SEC,
    TVENDOR_SLOW_QUERY_MS,
    TVENDOR_SQL_TRACE_ENABLED,
    TVENDOR_SQL_TRACE_MAX_LEN,
    get_env_bool,
    get_env_float,
    get_env_int,
)

PERF_LOGGER = logging.getLogger("vendor_catalog_app.perf")
_REQUEST_PERF_CONTEXT: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "tvendor_request_perf",
    default=None,
)


def start_request_perf_context(
    *,
    request_id: str,
    method: str,
    path: str,
    slow_query_ms: float,
) -> contextvars.Token:
    return _REQUEST_PERF_CONTEXT.set(
        {
            "request_id": request_id,
            "method": method,
            "path": path,
            "slow_query_ms": float(slow_query_ms),
            "db_calls": 0,
            "db_total_ms": 0.0,
            "db_max_ms": 0.0,
            "db_cache_hits": 0,
            "db_errors": 0,
            "slow_queries": [],
        }
    )


def get_request_perf_context() -> dict[str, Any] | None:
    return _REQUEST_PERF_CONTEXT.get()


def clear_request_perf_context(token: contextvars.Token) -> None:
    _REQUEST_PERF_CONTEXT.reset(token)


class DataConnectionError(RuntimeError):
    """Raised when a database connection cannot be established."""


class DataQueryError(RuntimeError):
    """Raised when a query operation fails."""


class DataExecutionError(RuntimeError):
    """Raised when a non-query execution fails."""


class DatabricksSQLClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._query_cache_enabled = get_env_bool(TVENDOR_QUERY_CACHE_ENABLED, default=True)
        self._query_cache_ttl_seconds = get_env_int(TVENDOR_QUERY_CACHE_TTL_SEC, default=120, min_value=0)
        self._query_cache_max_entries = get_env_int(
            TVENDOR_QUERY_CACHE_MAX_ENTRIES,
            default=256,
            min_value=1,
        )
        self._query_cache = LruTtlCache[tuple[str, tuple[Any, ...]], pd.DataFrame](
            enabled=self._query_cache_enabled,
            ttl_seconds=self._query_cache_ttl_seconds,
            max_entries=self._query_cache_max_entries,
            clone_value=lambda frame: frame.copy(deep=True),
        )

        self._pool_enabled = (not self.config.use_local_db) and get_env_bool(TVENDOR_DB_POOL_ENABLED, default=True)
        self._pool_max_size = get_env_int(TVENDOR_DB_POOL_MAX_SIZE, default=8, min_value=1)
        self._pool_acquire_timeout_sec = get_env_float(
            TVENDOR_DB_POOL_ACQUIRE_TIMEOUT_SEC,
            default=15.0,
            min_value=0.1,
        )
        self._pool_idle_ttl_sec = get_env_float(
            TVENDOR_DB_POOL_IDLE_TTL_SEC,
            default=600.0,
            min_value=0.0,
        )
        self._pool_condition = threading.Condition()
        self._pool_available: list[tuple[float, Any]] = []
        self._pool_total_connections = 0
        self._pool_closed = False

        self._sql_trace_enabled = get_env_bool(TVENDOR_SQL_TRACE_ENABLED, default=False)
        self._sql_trace_max_len = get_env_int(TVENDOR_SQL_TRACE_MAX_LEN, default=180, min_value=80)
        self._slow_query_ms = get_env_float(TVENDOR_SLOW_QUERY_MS, default=750.0, min_value=1.0)

    def _validate(self) -> None:
        if self.config.use_local_db:
            return
        missing = []
        if not self.config.databricks_server_hostname:
            missing.append("DATABRICKS_SERVER_HOSTNAME")
        if not self.config.databricks_http_path:
            missing.append("DATABRICKS_HTTP_PATH")
        has_pat = bool(str(self.config.databricks_token or "").strip())
        has_client_creds = bool(str(self.config.databricks_client_id or "").strip()) and bool(
            str(self.config.databricks_client_secret or "").strip()
        )
        has_sdk_fallback = DatabricksSDKConfig is not None
        if not has_pat and not has_client_creds and not has_sdk_fallback:
            missing.append("DATABRICKS_TOKEN or DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET")
        if missing:
            raise RuntimeError(f"Missing Databricks settings: {', '.join(missing)}")

    def _connect_databricks(self):
        common = {
            "server_hostname": self.config.databricks_server_hostname,
            "http_path": self.config.databricks_http_path,
        }
        token = str(self.config.databricks_token or "").strip()
        if token:
            return dbsql.connect(access_token=token, **common)

        host_url = f"https://{self.config.databricks_server_hostname}"
        client_id = str(self.config.databricks_client_id or "").strip()
        client_secret = str(self.config.databricks_client_secret or "").strip()

        if client_id and client_secret:
            if DatabricksSDKConfig is None or oauth_service_principal is None:
                raise RuntimeError(
                    "OAuth service-principal auth requires databricks-sdk. "
                    "Install dependencies from app/requirements.txt."
                )
            cfg = DatabricksSDKConfig(
                host=host_url,
                client_id=client_id,
                client_secret=client_secret,
            )
            sdk_credentials_provider = oauth_service_principal(cfg)

            # databricks-sql-connector expects credentials_provider() -> header_factory_callable,
            # where header_factory_callable() -> auth headers dict.
            def _credentials_provider():
                return sdk_credentials_provider

            return dbsql.connect(credentials_provider=_credentials_provider, **common)

        if DatabricksSDKConfig is None:
            raise RuntimeError(
                "No Databricks auth configured. Provide DATABRICKS_TOKEN, "
                "or DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET."
            )

        try:
            runtime_cfg = DatabricksSDKConfig(host=host_url)
        except Exception as exc:
            raise RuntimeError(
                "No explicit Databricks auth configured and runtime OAuth credentials were not detected. "
                "In Databricks Apps, ensure SQL scope consent is granted and SQL warehouse resource binding is configured."
            ) from exc

        def _runtime_credentials_provider():
            return runtime_cfg.authenticate

        return dbsql.connect(credentials_provider=_runtime_credentials_provider, **common)

    @staticmethod
    def _close_connection(conn: Any) -> None:
        try:
            conn.close()
        except Exception:
            pass

    @staticmethod
    def _is_connection_error(exc: BaseException) -> bool:
        message = str(exc).lower()
        signals = (
            "connection",
            "session",
            "closed",
            "timeout",
            "unreachable",
            "transport",
            "network",
            "socket",
            "cannot open",
            "failed to connect",
        )
        return any(token in message for token in signals)

    def _collect_expired_pool_connections_locked(self, now: float) -> list[Any]:
        if self._pool_idle_ttl_sec <= 0:
            return []
        stale: list[Any] = []
        active: list[tuple[float, Any]] = []
        for released_at, conn in self._pool_available:
            if (now - float(released_at)) >= float(self._pool_idle_ttl_sec):
                stale.append(conn)
            else:
                active.append((released_at, conn))
        if stale:
            self._pool_available = active
            self._pool_total_connections = max(0, self._pool_total_connections - len(stale))
        return stale

    def _acquire_pooled_connection(self) -> Any:
        deadline = time.monotonic() + float(self._pool_acquire_timeout_sec)
        while True:
            stale_to_close: list[Any] = []
            candidate_conn = None
            should_create = False
            with self._pool_condition:
                if self._pool_closed:
                    raise DataConnectionError("Databricks SQL client pool is closed.")
                now = time.monotonic()
                stale_to_close = self._collect_expired_pool_connections_locked(now)
                if self._pool_available:
                    _, candidate_conn = self._pool_available.pop()
                if candidate_conn is None and self._pool_total_connections < self._pool_max_size:
                    self._pool_total_connections += 1
                    should_create = True
                elif candidate_conn is None:
                    remaining = deadline - now
                    if remaining <= 0:
                        raise DataConnectionError(
                            (
                                "Timed out waiting for Databricks SQL connection from pool. "
                                f"max_size={self._pool_max_size}, timeout_sec={self._pool_acquire_timeout_sec:.1f}"
                            )
                        )
                    self._pool_condition.wait(timeout=remaining)

            for conn in stale_to_close:
                self._close_connection(conn)

            if candidate_conn is not None:
                return candidate_conn

            if not should_create:
                continue

            self._validate()
            try:
                return self._connect_databricks()
            except Exception as exc:
                with self._pool_condition:
                    self._pool_total_connections = max(0, self._pool_total_connections - 1)
                    self._pool_condition.notify()
                details = str(exc).strip()
                message = "Failed to connect to Databricks SQL warehouse."
                if details:
                    message = f"{message} Details: {details}"
                raise DataConnectionError(message) from exc

    def _release_pooled_connection(self, conn: Any, *, broken: bool) -> None:
        close_connection = False
        with self._pool_condition:
            if broken or self._pool_closed:
                self._pool_total_connections = max(0, self._pool_total_connections - 1)
                self._pool_condition.notify()
                close_connection = True
            else:
                self._pool_available.append((time.monotonic(), conn))
                self._pool_condition.notify()
        if close_connection:
            self._close_connection(conn)

    def close(self) -> None:
        if not self._pool_enabled:
            return
        to_close: list[Any] = []
        with self._pool_condition:
            self._pool_closed = True
            if self._pool_available:
                to_close = [conn for _, conn in self._pool_available]
                self._pool_available.clear()
                self._pool_total_connections = max(0, self._pool_total_connections - len(to_close))
            self._pool_condition.notify_all()
        for conn in to_close:
            self._close_connection(conn)

    @contextmanager
    def _connection(self):
        conn = None
        close_after_use = False
        release_to_pool = False
        pooled_connection_broken = False
        if self.config.use_local_db:
            db_path = Path(self.config.local_db_path).resolve()
            if not db_path.exists():
                raise RuntimeError(
                    f"Local DB not found: {db_path}. Run `python setup/local_db/init_local_db.py --reset` first."
                )
            try:
                conn = sqlite3.connect(str(db_path))
            except Exception as exc:
                raise DataConnectionError(f"Failed to connect to local SQLite DB at {db_path}.") from exc
            close_after_use = True
        else:
            if self._pool_enabled:
                conn = self._acquire_pooled_connection()
                release_to_pool = True
            else:
                self._validate()
                try:
                    conn = self._connect_databricks()
                except Exception as exc:
                    details = str(exc).strip()
                    message = "Failed to connect to Databricks SQL warehouse."
                    if details:
                        message = f"{message} Details: {details}"
                    raise DataConnectionError(message) from exc
                close_after_use = True
        try:
            yield conn
        except Exception as exc:
            if release_to_pool and self._is_connection_error(exc):
                pooled_connection_broken = True
            raise
        finally:
            if release_to_pool and conn is not None:
                self._release_pooled_connection(conn, broken=pooled_connection_broken)
            elif close_after_use and conn is not None:
                self._close_connection(conn)

    def _prepare(self, statement: str) -> str:
        normalized = str(statement or "")
        if normalized.startswith("\ufeff"):
            normalized = normalized.lstrip("\ufeff")
        # `%s` placeholders are not supported by databricks-sql native params;
        # normalize to qmark syntax which both sqlite and databricks connector accept.
        normalized = normalized.replace("%s", "?")
        if self.config.use_local_db:
            normalized = normalized.replace(f"{self.config.fq_schema}.", "")
        return normalized

    def _prepare_params(self, params: Iterable[Any] | None) -> tuple[Any, ...]:
        if not params:
            return ()
        if not self.config.use_local_db:
            return tuple(params)
        cleaned: list[Any] = []
        for value in params:
            if isinstance(value, datetime):
                cleaned.append(value.isoformat())
            elif isinstance(value, date):
                cleaned.append(value.isoformat())
            else:
                cleaned.append(value)
        return tuple(cleaned)

    def _cache_key(self, statement: str, params: tuple[Any, ...]) -> tuple[str, tuple[Any, ...]]:
        return statement, params

    def _cache_get(self, key: tuple[str, tuple[Any, ...]]) -> pd.DataFrame | None:
        return self._query_cache.get(key)

    def _cache_put(self, key: tuple[str, tuple[Any, ...]], frame: pd.DataFrame) -> None:
        self._query_cache.set(key, frame)

    def _cache_clear(self) -> None:
        self._query_cache.clear()

    @staticmethod
    def _sql_preview(statement: str, max_len: int = 180) -> str:
        compact = re.sub(r"\s+", " ", str(statement or "")).strip()
        if len(compact) <= max_len:
            return compact
        return f"{compact[: max_len - 3]}..."

    def _record_query_perf(
        self,
        *,
        operation: str,
        statement: str,
        elapsed_ms: float,
        cached: bool,
        row_count: int | None = None,
        error: bool = False,
    ) -> None:
        statement_text = str(statement or "")
        sql_hash = hashlib.sha1(statement_text.encode("utf-8", errors="ignore")).hexdigest()[:12]
        preview = self._sql_preview(statement_text, max_len=self._sql_trace_max_len)

        request_ctx = get_request_perf_context()
        if request_ctx is not None:
            request_ctx["db_calls"] = int(request_ctx.get("db_calls", 0)) + 1
            request_ctx["db_total_ms"] = float(request_ctx.get("db_total_ms", 0.0)) + float(elapsed_ms)
            request_ctx["db_max_ms"] = max(float(request_ctx.get("db_max_ms", 0.0)), float(elapsed_ms))
            if cached:
                request_ctx["db_cache_hits"] = int(request_ctx.get("db_cache_hits", 0)) + 1
            if error:
                request_ctx["db_errors"] = int(request_ctx.get("db_errors", 0)) + 1

            slow_threshold = float(request_ctx.get("slow_query_ms", self._slow_query_ms))
            if elapsed_ms >= slow_threshold:
                slow_queries = request_ctx.setdefault("slow_queries", [])
                if len(slow_queries) < 10:
                    slow_queries.append(
                        {
                            "operation": operation,
                            "elapsed_ms": round(float(elapsed_ms), 2),
                            "cached": bool(cached),
                            "rows": int(row_count) if row_count is not None else None,
                            "sql_hash": sql_hash,
                            "sql": preview,
                            "error": bool(error),
                        }
                    )

        should_log = self._sql_trace_enabled or elapsed_ms >= self._slow_query_ms or error
        if not should_log:
            return

        log_fn = PERF_LOGGER.warning if (elapsed_ms >= self._slow_query_ms or error) else PERF_LOGGER.info
        log_fn(
            "sql_perf op=%s ms=%.2f cached=%s rows=%s error=%s hash=%s sql=%s",
            operation,
            float(elapsed_ms),
            str(bool(cached)).lower(),
            "-" if row_count is None else int(row_count),
            str(bool(error)).lower(),
            sql_hash,
            preview,
            extra={
                "event": "sql_perf",
                "operation": operation,
                "elapsed_ms": round(float(elapsed_ms), 2),
                "cached": bool(cached),
                "rows": None if row_count is None else int(row_count),
                "error": bool(error),
                "sql_hash": sql_hash,
                "sql_preview": preview,
            },
        )

    @staticmethod
    def _leading_sql_keyword(statement: str) -> str:
        text = str(statement or "").strip()
        if not text:
            return ""
        text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
        lines: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("--"):
                continue
            lines.append(line)
        if not lines:
            return ""
        normalized = " ".join(lines).lstrip("(").strip()
        if not normalized:
            return ""
        return normalized.split(None, 1)[0].upper()

    def _enforce_prod_sql_policy(self, statement: str, *, is_query: bool) -> None:
        if self.config.use_local_db:
            return
        if self.config.env != "prod" or not self.config.enforce_prod_sql_policy:
            return

        verb = self._leading_sql_keyword(statement)
        if not verb:
            raise RuntimeError("SQL statement is empty.")

        ddl_verbs = {"CREATE", "ALTER", "DROP", "TRUNCATE"}
        if verb in ddl_verbs:
            raise RuntimeError(
                f"SQL verb '{verb}' is blocked in prod. Runtime schema changes are disabled."
            )

        if is_query:
            if verb not in {"SELECT", "WITH"}:
                raise RuntimeError(f"Read query verb '{verb}' is not allowed in prod query path.")
            return

        allowed = set(self.config.allowed_write_verbs)
        if verb not in allowed:
            allowed_text = ", ".join(sorted(allowed))
            raise RuntimeError(
                f"Write SQL verb '{verb}' is not allowed in prod. Allowed verbs: {allowed_text}."
            )

    def query(self, statement: str, params: Iterable[Any] | None = None) -> pd.DataFrame:
        prepared_statement = ""
        try:
            prepared_statement = self._prepare(statement)
            prepared_params = self._prepare_params(params)
            self._enforce_prod_sql_policy(prepared_statement, is_query=True)

            leading = self._leading_sql_keyword(prepared_statement)
            use_cache = leading in {"SELECT", "WITH"}
            cache_key = self._cache_key(prepared_statement, prepared_params)
            if use_cache:
                cache_started = time.perf_counter()
                cached = self._cache_get(cache_key)
                if cached is not None:
                    self._record_query_perf(
                        operation="query",
                        statement=prepared_statement,
                        elapsed_ms=(time.perf_counter() - cache_started) * 1000.0,
                        cached=True,
                        row_count=len(cached.index),
                    )
                    return cached

            query_started = time.perf_counter()
            with self._connection() as conn:
                if self.config.use_local_db:
                    cursor = conn.cursor()
                    cursor.execute(prepared_statement, prepared_params)
                    rows = cursor.fetchall()
                    cols = [desc[0] for desc in cursor.description] if cursor.description else []
                    cursor.close()
                    frame = pd.DataFrame(rows, columns=cols)
                    if use_cache:
                        self._cache_put(cache_key, frame)
                    self._record_query_perf(
                        operation="query",
                        statement=prepared_statement,
                        elapsed_ms=(time.perf_counter() - query_started) * 1000.0,
                        cached=False,
                        row_count=len(frame.index),
                    )
                    return frame
                with conn.cursor() as cursor:
                    cursor.execute(prepared_statement, prepared_params)
                    rows = cursor.fetchall()
                    cols = [desc[0] for desc in cursor.description] if cursor.description else []
                    frame = pd.DataFrame(rows, columns=cols)
                    if use_cache:
                        self._cache_put(cache_key, frame)
                    self._record_query_perf(
                        operation="query",
                        statement=prepared_statement,
                        elapsed_ms=(time.perf_counter() - query_started) * 1000.0,
                        cached=False,
                        row_count=len(frame.index),
                    )
                    return frame
        except DataConnectionError:
            if prepared_statement:
                self._record_query_perf(
                    operation="query",
                    statement=prepared_statement,
                    elapsed_ms=0.0,
                    cached=False,
                    row_count=None,
                    error=True,
                )
            raise
        except Exception as exc:
            if prepared_statement:
                self._record_query_perf(
                    operation="query",
                    statement=prepared_statement,
                    elapsed_ms=0.0,
                    cached=False,
                    row_count=None,
                    error=True,
                )
            raise DataQueryError("Query execution failed.") from exc

    def execute(self, statement: str, params: Iterable[Any] | None = None) -> None:
        prepared_statement = ""
        try:
            prepared_statement = self._prepare(statement)
            prepared_params = self._prepare_params(params)
            self._enforce_prod_sql_policy(prepared_statement, is_query=False)
            exec_started = time.perf_counter()
            with self._connection() as conn:
                if self.config.use_local_db:
                    cursor = conn.cursor()
                    cursor.execute(prepared_statement, prepared_params)
                    cursor.close()
                    conn.commit()
                    self._cache_clear()
                    self._record_query_perf(
                        operation="execute",
                        statement=prepared_statement,
                        elapsed_ms=(time.perf_counter() - exec_started) * 1000.0,
                        cached=False,
                        row_count=None,
                    )
                    return
                with conn.cursor() as cursor:
                    cursor.execute(prepared_statement, prepared_params)
                self._cache_clear()
                self._record_query_perf(
                    operation="execute",
                    statement=prepared_statement,
                    elapsed_ms=(time.perf_counter() - exec_started) * 1000.0,
                    cached=False,
                    row_count=None,
                )
        except DataConnectionError:
            if prepared_statement:
                self._record_query_perf(
                    operation="execute",
                    statement=prepared_statement,
                    elapsed_ms=0.0,
                    cached=False,
                    row_count=None,
                    error=True,
                )
            raise
        except Exception as exc:
            if prepared_statement:
                self._record_query_perf(
                    operation="execute",
                    statement=prepared_statement,
                    elapsed_ms=0.0,
                    cached=False,
                    row_count=None,
                    error=True,
                )
            raise DataExecutionError("Statement execution failed.") from exc
