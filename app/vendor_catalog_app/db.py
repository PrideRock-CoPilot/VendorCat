from __future__ import annotations

import contextvars
from contextlib import contextmanager
from datetime import date, datetime
import hashlib
import logging
from pathlib import Path
import os
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

from vendor_catalog_app.config import AppConfig

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
        self._thread_state = threading.local()
        self._cache_lock = threading.Lock()
        self._query_cache: dict[tuple[str, tuple[Any, ...]], tuple[float, pd.DataFrame]] = {}
        self._cache_enabled = self._as_bool(os.getenv("TVENDOR_QUERY_CACHE_ENABLED"), default=True)
        self._cache_ttl_seconds = self._as_int(os.getenv("TVENDOR_QUERY_CACHE_TTL_SEC"), default=120, min_value=0)
        self._cache_max_entries = self._as_int(
            os.getenv("TVENDOR_QUERY_CACHE_MAX_ENTRIES"),
            default=256,
            min_value=1,
        )
        self._sql_trace_enabled = self._as_bool(os.getenv("TVENDOR_SQL_TRACE_ENABLED"), default=False)
        self._sql_trace_max_len = self._as_int(os.getenv("TVENDOR_SQL_TRACE_MAX_LEN"), default=180, min_value=80)
        self._slow_query_ms = self._as_float(os.getenv("TVENDOR_SLOW_QUERY_MS"), default=750.0, min_value=1.0)

    @staticmethod
    def _as_bool(value: str | None, default: bool = False) -> bool:
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def _as_int(value: str | None, default: int, min_value: int) -> int:
        try:
            parsed = int(str(value or "").strip())
        except Exception:
            parsed = default
        return max(min_value, parsed)

    @staticmethod
    def _as_float(value: str | None, default: float, min_value: float) -> float:
        try:
            parsed = float(str(value or "").strip())
        except Exception:
            parsed = float(default)
        return max(float(min_value), parsed)

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

    def _thread_connection(self):
        return getattr(self._thread_state, "conn", None)

    def _set_thread_connection(self, conn: Any | None) -> None:
        self._thread_state.conn = conn

    def _drop_thread_connection(self) -> None:
        conn = self._thread_connection()
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        self._set_thread_connection(None)

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

    @contextmanager
    def _connection(self):
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
            conn = self._thread_connection()
            if conn is None:
                self._validate()
                try:
                    conn = self._connect_databricks()
                except Exception as exc:
                    details = str(exc).strip()
                    message = "Failed to connect to Databricks SQL warehouse."
                    if details:
                        message = f"{message} Details: {details}"
                    raise DataConnectionError(message) from exc
                self._set_thread_connection(conn)
            close_after_use = False
        try:
            yield conn
        except Exception as exc:
            if not self.config.use_local_db and self._is_connection_error(exc):
                self._drop_thread_connection()
            raise
        finally:
            if close_after_use:
                conn.close()

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
        if not self._cache_enabled or self._cache_ttl_seconds <= 0:
            return None
        now = time.monotonic()
        with self._cache_lock:
            entry = self._query_cache.get(key)
            if entry is None:
                return None
            expires_at, frame = entry
            if expires_at <= now:
                self._query_cache.pop(key, None)
                return None
            return frame.copy(deep=True)

    def _cache_put(self, key: tuple[str, tuple[Any, ...]], frame: pd.DataFrame) -> None:
        if not self._cache_enabled or self._cache_ttl_seconds <= 0:
            return
        expires_at = time.monotonic() + float(self._cache_ttl_seconds)
        with self._cache_lock:
            if len(self._query_cache) >= self._cache_max_entries:
                self._query_cache.pop(next(iter(self._query_cache)))
            self._query_cache[key] = (expires_at, frame.copy(deep=True))

    def _cache_clear(self) -> None:
        with self._cache_lock:
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
