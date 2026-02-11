from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
import re
import sqlite3
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


class DataConnectionError(RuntimeError):
    """Raised when a database connection cannot be established."""


class DataQueryError(RuntimeError):
    """Raised when a query operation fails."""


class DataExecutionError(RuntimeError):
    """Raised when a non-query execution fails."""


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
        try:
            self._enforce_prod_sql_policy(statement, is_query=True)
            with self._connection() as conn:
                if self.config.use_local_db:
                    cursor = conn.cursor()
                    cursor.execute(self._prepare(statement), self._prepare_params(params))
                    rows = cursor.fetchall()
                    cols = [desc[0] for desc in cursor.description] if cursor.description else []
                    cursor.close()
                    return pd.DataFrame(rows, columns=cols)
                with conn.cursor() as cursor:
                    cursor.execute(self._prepare(statement), self._prepare_params(params))
                    rows = cursor.fetchall()
                    cols = [desc[0] for desc in cursor.description] if cursor.description else []
                    return pd.DataFrame(rows, columns=cols)
        except DataConnectionError:
            raise
        except Exception as exc:
            raise DataQueryError("Query execution failed.") from exc

    def execute(self, statement: str, params: Iterable[Any] | None = None) -> None:
        try:
            self._enforce_prod_sql_policy(statement, is_query=False)
            with self._connection() as conn:
                if self.config.use_local_db:
                    cursor = conn.cursor()
                    cursor.execute(self._prepare(statement), self._prepare_params(params))
                    cursor.close()
                    conn.commit()
                    return
                with conn.cursor() as cursor:
                    cursor.execute(self._prepare(statement), self._prepare_params(params))
        except DataConnectionError:
            raise
        except Exception as exc:
            raise DataExecutionError("Statement execution failed.") from exc
