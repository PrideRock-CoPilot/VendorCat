from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

import pandas as pd

from vendor_catalog_app.core.security import (
    MAX_APPROVAL_LEVEL,
    MIN_CHANGE_APPROVAL_LEVEL,
    required_approval_level,
)
from vendor_catalog_app.infrastructure.db import DataConnectionError, DataExecutionError

LOGGER = logging.getLogger(__name__)


class RepositoryCoreAuditMixin:
    def _serialize_payload(self, payload: dict[str, Any] | None) -> str:
        if not payload:
            return "{}"
        return json.dumps(payload)

    @staticmethod
    def _safe_payload_json(payload_json: Any) -> dict[str, Any]:
        if isinstance(payload_json, dict):
            return payload_json
        if not isinstance(payload_json, str):
            return {}
        try:
            parsed = json.loads(payload_json)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _audit_field_label(field_name: str) -> str:
        cleaned = re.sub(r"[_\s]+", " ", str(field_name or "").strip())
        cleaned = cleaned.strip()
        return cleaned.title() if cleaned else "Field"

    @staticmethod
    def _audit_value_for_compare(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, float) and pd.isna(value):
            return None
        if isinstance(value, (dict, list, tuple, set)):
            return json.dumps(value, default=str, sort_keys=True)
        if isinstance(value, str):
            return value.strip()
        return str(value)

    @classmethod
    def _audit_values_equal(cls, left: Any, right: Any) -> bool:
        return cls._audit_value_for_compare(left) == cls._audit_value_for_compare(right)

    @staticmethod
    def _audit_value_text(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, float) and pd.isna(value):
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (dict, list, tuple, set)):
            text = json.dumps(value, default=str, sort_keys=True)
        else:
            text = str(value)
        text = re.sub(r"\s+", " ", text).strip()
        return text if len(text) <= 72 else f"{text[:69]}..."

    def _build_audit_change_summary(
        self,
        *,
        action_type: str,
        before_payload: dict[str, Any],
        after_payload: dict[str, Any],
    ) -> str:
        action = str(action_type or "").strip().lower()
        ignored_fields = {
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "event_ts",
            "last_seen_at",
        }

        changes: list[str] = []
        if action == "insert":
            for key in sorted(after_payload.keys()):
                if key in ignored_fields:
                    continue
                changes.append(f"{self._audit_field_label(key)} = {self._audit_value_text(after_payload.get(key))}")
        elif action == "delete":
            for key in sorted(before_payload.keys()):
                if key in ignored_fields:
                    continue
                changes.append(f"{self._audit_field_label(key)} was {self._audit_value_text(before_payload.get(key))}")
        else:
            for key in sorted(set(before_payload.keys()) | set(after_payload.keys())):
                if key in ignored_fields:
                    continue
                before_value = before_payload.get(key)
                after_value = after_payload.get(key)
                if self._audit_values_equal(before_value, after_value):
                    continue
                changes.append(
                    f"{self._audit_field_label(key)}: {self._audit_value_text(before_value)} -> {self._audit_value_text(after_value)}"
                )

        if not changes:
            if action == "insert":
                return "Created record."
            if action == "delete":
                return "Removed record."
            return "Updated record (field-level details unavailable)."

        visible = changes[:4]
        summary = "; ".join(visible)
        if len(changes) > 4:
            summary = f"{summary}; +{len(changes) - 4} more"
        return summary

    def _with_audit_change_summaries(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            out = df.copy()
            if "change_summary" not in out.columns:
                out["change_summary"] = pd.Series(dtype="object")
            return out

        out = df.copy()
        if "before_json" not in out.columns:
            out["before_json"] = None
        if "after_json" not in out.columns:
            out["after_json"] = None

        summaries: list[str] = []
        for row in out.to_dict("records"):
            before_payload = self._safe_payload_json(row.get("before_json"))
            after_payload = self._safe_payload_json(row.get("after_json"))
            summaries.append(
                self._build_audit_change_summary(
                    action_type=str(row.get("action_type") or ""),
                    before_payload=before_payload,
                    after_payload=after_payload,
                )
            )
        out["change_summary"] = summaries
        return out

    def _prepare_change_request_payload(self, change_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        out = dict(payload or {})
        meta = out.get("_meta") if isinstance(out.get("_meta"), dict) else {}
        required_level = required_approval_level(change_type)
        try:
            required_level = int(meta.get("approval_level_required", required_level))
        except Exception:
            required_level = required_approval_level(change_type)
        required_level = max(MIN_CHANGE_APPROVAL_LEVEL, min(required_level, MAX_APPROVAL_LEVEL))
        meta["approval_level_required"] = required_level
        meta["workflow_action"] = (change_type or "").strip().lower()
        out["_meta"] = meta
        return out

    @staticmethod
    @staticmethod
    def _apply_row_overrides(
        df: pd.DataFrame,
        overrides: dict[str, dict[str, Any]],
        key_column: str,
    ) -> pd.DataFrame:
        if df.empty or not overrides or key_column not in df.columns:
            return df
        out = df.copy()
        for row_id, row_overrides in overrides.items():
            mask = out[key_column].astype(str) == str(row_id)
            if not mask.any():
                continue
            for key, value in row_overrides.items():
                if key in out.columns:
                    out.loc[mask, key] = value
        return out

    def _write_audit_entity_change(
        self,
        *,
        entity_name: str,
        entity_id: str,
        action_type: str,
        actor_user_principal: str,
        before_json: dict[str, Any] | None = None,
        after_json: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> str:
        change_event_id = str(uuid.uuid4())
        actor_ref = self._actor_ref(actor_user_principal)
        try:
            self._execute_file(
                "inserts/audit_entity_change.sql",
                params=(
                    change_event_id,
                    entity_name,
                    entity_id,
                    action_type,
                    json.dumps(before_json, default=str) if before_json is not None else None,
                    json.dumps(after_json, default=str) if after_json is not None else None,
                    actor_ref,
                    self._now(),
                    request_id,
                ),
                audit_entity_change=self._table("audit_entity_change"),
            )
        except (DataExecutionError, DataConnectionError):
            LOGGER.debug(
                "Failed to write audit_entity_change for '%s/%s'.",
                entity_name,
                entity_id,
                exc_info=True,
            )
        return change_event_id

