from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from apps.core.config.env import RuntimeSettings
from apps.core.observability import METRICS

try:
    from databricks import sql as _databricks_sql

    databricks_sql: Any = _databricks_sql
except Exception:  # pragma: no cover - optional dependency in local runtime
    databricks_sql = None


@dataclass(frozen=True)
class SqlQueryResult:
    rows: list[dict[str, Any]]


class SqlAdapter(ABC):
    @abstractmethod
    def ping(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def query(self, statement: str, params: tuple[Any, ...] = ()) -> SqlQueryResult:
        raise NotImplementedError

    @abstractmethod
    def execute(self, statement: str, params: tuple[Any, ...] = ()) -> int:
        raise NotImplementedError


class DuckDbAdapter(SqlAdapter):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

    def ping(self) -> bool:
        start = time.perf_counter()
        try:
            with duckdb.connect(self._db_path) as conn:
                conn.execute("SELECT 1")
            METRICS.observe_db("ping", (time.perf_counter() - start) * 1000)
            return True
        except Exception:
            METRICS.observe_db("ping", (time.perf_counter() - start) * 1000)
            return False

    def query(self, statement: str, params: tuple[Any, ...] = ()) -> SqlQueryResult:
        start = time.perf_counter()
        with duckdb.connect(self._db_path) as conn:
            rel = conn.execute(statement, params)
            cols = [d[0] for d in rel.description] if rel.description else []
            rows = [dict(zip(cols, row, strict=False)) for row in rel.fetchall()]
        METRICS.observe_db("query", (time.perf_counter() - start) * 1000)
        return SqlQueryResult(rows=rows)

    def execute(self, statement: str, params: tuple[Any, ...] = ()) -> int:
        start = time.perf_counter()
        with duckdb.connect(self._db_path) as conn:
            rel = conn.execute(statement, params)
            affected = rel.rowcount if rel.rowcount is not None else 0
        METRICS.observe_db("execute", (time.perf_counter() - start) * 1000)
        return int(affected)


class DatabricksSqlAdapter(SqlAdapter):
    def __init__(self, settings: RuntimeSettings) -> None:
        self._settings = settings

    def _connect(self) -> Any:
        if databricks_sql is None:
            raise RuntimeError("databricks-sql-connector is not available")
        if not (self._settings.databricks_host and self._settings.databricks_http_path):
            raise RuntimeError("Databricks host/http path is not configured")
        if not self._settings.databricks_token:
            raise RuntimeError("Databricks token auth is required for rebuild baseline")
        return databricks_sql.connect(
            server_hostname=self._settings.databricks_host,
            http_path=self._settings.databricks_http_path,
            access_token=self._settings.databricks_token,
        )

    def ping(self) -> bool:
        start = time.perf_counter()
        try:
            with self._connect() as conn, conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            METRICS.observe_db("ping", (time.perf_counter() - start) * 1000)
            return True
        except Exception:
            METRICS.observe_db("ping", (time.perf_counter() - start) * 1000)
            return False

    def query(self, statement: str, params: tuple[Any, ...] = ()) -> SqlQueryResult:
        start = time.perf_counter()
        with self._connect() as conn, conn.cursor() as cursor:
            cursor.execute(statement, params or None)
            data = cursor.fetchall()
            description = cursor.description or []
            cols = [col[0] for col in description]
            rows = [dict(zip(cols, row, strict=False)) for row in data]
        METRICS.observe_db("query", (time.perf_counter() - start) * 1000)
        return SqlQueryResult(rows=rows)

    def execute(self, statement: str, params: tuple[Any, ...] = ()) -> int:
        start = time.perf_counter()
        with self._connect() as conn, conn.cursor() as cursor:
            cursor.execute(statement, params or None)
            affected = cursor.rowcount if cursor.rowcount is not None else 0
        METRICS.observe_db("execute", (time.perf_counter() - start) * 1000)
        return int(affected)


def create_sql_adapter(settings: RuntimeSettings) -> SqlAdapter:
    if settings.runtime_profile == "databricks":
        return DatabricksSqlAdapter(settings)
    return DuckDbAdapter(settings.local_duckdb_path)
