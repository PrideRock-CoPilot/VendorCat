from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any, Iterable

import pandas as pd
from databricks import sql as dbsql

from vendor_catalog_app.config import AppConfig


class DatabricksSQLClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def _validate(self) -> None:
        if self.config.use_local_db:
            return
        missing = []
        if not self.config.databricks_server_hostname:
            missing.append("DATABRICKS_SERVER_HOSTNAME")
        if not self.config.databricks_http_path:
            missing.append("DATABRICKS_HTTP_PATH")
        if not self.config.databricks_token:
            missing.append("DATABRICKS_TOKEN")
        if missing:
            raise RuntimeError(f"Missing Databricks settings: {', '.join(missing)}")

    @contextmanager
    def _connection(self):
        if self.config.use_local_db:
            db_path = Path(self.config.local_db_path).resolve()
            if not db_path.exists():
                raise RuntimeError(
                    f"Local DB not found: {db_path}. Run `python app/local_db/init_local_db.py --reset` first."
                )
            conn = sqlite3.connect(str(db_path))
        else:
            self._validate()
            conn = dbsql.connect(
                server_hostname=self.config.databricks_server_hostname,
                http_path=self.config.databricks_http_path,
                access_token=self.config.databricks_token,
            )
        try:
            yield conn
        finally:
            conn.close()

    def _prepare(self, statement: str) -> str:
        if not self.config.use_local_db:
            return statement
        normalized = statement.replace(f"{self.config.fq_schema}.", "")
        normalized = normalized.replace("%s", "?")
        return normalized

    def query(self, statement: str, params: Iterable[Any] | None = None) -> pd.DataFrame:
        with self._connection() as conn:
            if self.config.use_local_db:
                cursor = conn.cursor()
                cursor.execute(self._prepare(statement), params or ())
                rows = cursor.fetchall()
                cols = [desc[0] for desc in cursor.description] if cursor.description else []
                cursor.close()
                return pd.DataFrame(rows, columns=cols)
            with conn.cursor() as cursor:
                cursor.execute(self._prepare(statement), params or ())
                rows = cursor.fetchall()
                cols = [desc[0] for desc in cursor.description] if cursor.description else []
                return pd.DataFrame(rows, columns=cols)

    def execute(self, statement: str, params: Iterable[Any] | None = None) -> None:
        with self._connection() as conn:
            if self.config.use_local_db:
                cursor = conn.cursor()
                cursor.execute(self._prepare(statement), params or ())
                cursor.close()
                conn.commit()
                return
            with conn.cursor() as cursor:
                cursor.execute(self._prepare(statement), params or ())
