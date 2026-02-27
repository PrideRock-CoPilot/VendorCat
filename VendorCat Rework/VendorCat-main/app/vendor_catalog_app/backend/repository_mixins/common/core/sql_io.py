from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd


class RepositoryCoreSqlMixin:
    _REPORT_TABLE_ALIASES: dict[str, str] = {
        "core_vendor": "vw_reporting_core_vendor",
        "core_vendor_offering": "vw_reporting_core_vendor_offering",
        "core_vendor_business_owner": "vw_reporting_core_vendor_business_owner",
        "core_offering_business_owner": "vw_reporting_core_offering_business_owner",
        "core_vendor_contact": "vw_reporting_core_vendor_contact",
        "core_offering_contact": "vw_reporting_core_offering_contact",
        "core_vendor_identifier": "vw_reporting_core_vendor_identifier",
        "core_vendor_org_assignment": "vw_reporting_core_vendor_org_assignment",
        "core_contract": "vw_reporting_core_contract",
        "core_contract_event": "vw_reporting_core_contract_event",
        "core_vendor_demo": "vw_reporting_core_vendor_demo",
        "core_vendor_demo_score": "vw_reporting_core_vendor_demo_score",
        "core_vendor_demo_note": "vw_reporting_core_vendor_demo_note",
    }

    def _table(self, name: str) -> str:
        if self.config.use_local_db:
            return name
        return f"{self.config.fq_schema}.{name}"

    def _report_table(self, name: str) -> str:
        mapped = self._REPORT_TABLE_ALIASES.get(str(name or "").strip(), str(name or "").strip())
        return self._table(mapped)

    def _employee_directory_view(self) -> str:
        return self._table("vw_employee_directory")

    @staticmethod
    def _sql_root() -> Path:
        return Path(__file__).resolve().parents[4] / "sql"

    @staticmethod
    @lru_cache(maxsize=512)
    def _read_sql_file(path_str: str) -> str:
        path = Path(path_str)
        if not path.exists():
            raise FileNotFoundError(f"SQL file not found: {path}")
        return path.read_text(encoding="utf-8")

    def preload_sql_templates(self) -> int:
        sql_root = self._sql_root()
        loaded = 0
        for sql_path in sorted(sql_root.rglob("*.sql")):
            if not sql_path.is_file():
                continue
            self._read_sql_file(str(sql_path.resolve()))
            loaded += 1
        return loaded

    def _sql(self, relative_path: str, **format_args: Any) -> str:
        sql_root = self._sql_root()
        sql_path = (sql_root / relative_path).resolve()
        template = self._read_sql_file(str(sql_path))
        return template.format(**format_args) if format_args else template

    def _query_file(
        self,
        relative_path: str,
        *,
        params: tuple | None = None,
        columns: list[str] | None = None,
        **format_args: Any,
    ) -> pd.DataFrame:
        statement = self._sql(relative_path, **format_args)
        return self._query_or_empty(statement, params=params, columns=columns)

    def _execute_file(
        self,
        relative_path: str,
        *,
        params: tuple | None = None,
        **format_args: Any,
    ) -> None:
        statement = self._sql(relative_path, **format_args)
        self.client.execute(statement, params)
        self._cache_clear()

    def _probe_file(
        self,
        relative_path: str,
        *,
        params: tuple | None = None,
        **format_args: Any,
    ) -> pd.DataFrame:
        statement = self._sql(relative_path, **format_args)
        return self.client.query(statement, params)
