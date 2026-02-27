from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from apps.core.sql.adapter import SqlAdapter


class Repository(Protocol):
    def query(self, statement: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        ...

    def execute(self, statement: str, params: tuple[Any, ...] = ()) -> int:
        ...


@dataclass
class SqlRepository:
    adapter: SqlAdapter

    def query(self, statement: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return self.adapter.query(statement, params).rows

    def execute(self, statement: str, params: tuple[Any, ...] = ()) -> int:
        return self.adapter.execute(statement, params)
