from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
from vendor_catalog_app.infrastructure.db import DataConnectionError, DataQueryError


class RepositoryCoreFrameMixin:
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_choice(
        value: str | None,
        *,
        field_name: str,
        allowed: set[str],
        default: str,
    ) -> str:
        normalized = (value or "").strip().lower()
        if not normalized:
            return default
        if normalized not in allowed:
            allowed_text = ", ".join(sorted(allowed))
            raise ValueError(f"{field_name} must be one of: {allowed_text}.")
        return normalized

    def _query_or_empty(
        self, statement: str, params: tuple | None = None, columns: list[str] | None = None
    ) -> pd.DataFrame:
        try:
            return self.client.query(statement, params)
        except (DataQueryError, DataConnectionError):
            return pd.DataFrame(columns=columns or [])

    @staticmethod
    def _apply_org_filter(df: pd.DataFrame, org_id: str | None, org_column: str = "org_id") -> pd.DataFrame:
        if org_id and org_id != "all" and org_column in df.columns:
            return df[df[org_column] == org_id].copy()
        return df.copy()

    @staticmethod
    def _months_window(df: pd.DataFrame, month_col: str, months: int) -> pd.DataFrame:
        if month_col not in df.columns:
            return df
        months = max(1, min(months, 36))
        frame = df.copy()
        frame[month_col] = pd.to_datetime(frame[month_col], errors="coerce")
        if frame[month_col].isna().all():
            return frame
        max_month = frame[month_col].max()
        cutoff = (max_month - pd.DateOffset(months=months - 1)).replace(day=1)
        return frame[frame[month_col] >= cutoff]

    @staticmethod
    def _matches_needle(value: Any, needle: str) -> bool:
        if value is None:
            return False
        return needle in str(value).strip().lower()

    @staticmethod
    def _filter_contains_any(df: pd.DataFrame, needle: str, columns: list[str]) -> pd.DataFrame:
        cleaned = (needle or "").strip().lower()
        if df.empty or not cleaned:
            return df
        mask = pd.Series(False, index=df.index)
        for column in columns:
            if column in df.columns:
                mask = mask | df[column].astype(str).str.lower().str.contains(cleaned, regex=False, na=False)
        return df[mask].copy()

    @staticmethod
    def _vendor_sort_column(sort_by: str) -> str:
        mapping = {
            "vendor_name": "display_name",
            "display_name": "display_name",
            "vendor_id": "vendor_id",
            "legal_name": "legal_name",
            "lifecycle_state": "lifecycle_state",
            "owner_org_id": "owner_org_id",
            "risk_tier": "risk_tier",
            "updated_at": "updated_at",
        }
        return mapping.get((sort_by or "").strip().lower(), "display_name")

    @staticmethod
    def _vendor_sort_expr(sort_by: str) -> str:
        mapping = {
            "vendor_name": "lower(coalesce(v.display_name, v.legal_name, v.vendor_id))",
            "display_name": "lower(coalesce(v.display_name, v.legal_name, v.vendor_id))",
            "vendor_id": "lower(v.vendor_id)",
            "legal_name": "lower(coalesce(v.legal_name, ''))",
            "lifecycle_state": "lower(coalesce(v.lifecycle_state, ''))",
            "owner_org_id": "lower(coalesce(v.owner_org_id, ''))",
            "risk_tier": "lower(coalesce(v.risk_tier, ''))",
            "updated_at": "v.updated_at",
        }
        return mapping.get((sort_by or "").strip().lower(), mapping["vendor_name"])

