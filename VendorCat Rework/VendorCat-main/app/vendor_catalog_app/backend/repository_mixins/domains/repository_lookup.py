from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from vendor_catalog_app.core.repository_constants import *

LOGGER = logging.getLogger(__name__)

class RepositoryLookupMixin:
    @staticmethod
    def _lookup_columns() -> list[str]:
        return [
            "option_id",
            "lookup_type",
            "option_code",
            "option_label",
            "sort_order",
            "active_flag",
            "valid_from_ts",
            "valid_to_ts",
            "is_current",
            "deleted_flag",
            "updated_at",
            "updated_by",
        ]

    def _lookup_versions_frame(self, lookup_type: str | None = None) -> pd.DataFrame:
        normalized_lookup_type = self._normalize_lookup_type(lookup_type) if lookup_type else None
        cache_key = ("lookup_versions_frame", normalized_lookup_type or "__all__")

        def _load() -> pd.DataFrame:
            columns = self._lookup_columns()
            default_rows = [
                row
                for row in self._default_lookup_option_rows()
                if not normalized_lookup_type or str(row.get("lookup_type") or "") == normalized_lookup_type
            ]

            self._ensure_local_lookup_option_table()
            rows = self._query_file(
                "reporting/list_lookup_options.sql",
                params=(normalized_lookup_type, normalized_lookup_type),
                columns=columns,
                app_lookup_option=self._table("app_lookup_option"),
            )
            records = rows.to_dict("records")
            if not records:
                records = [dict(row) for row in default_rows]
            out = pd.DataFrame(records, columns=columns)

            if out.empty:
                return out
            out["sort_order"] = pd.to_numeric(out["sort_order"], errors="coerce").fillna(999).astype(int)
            if "active_flag" not in out.columns:
                out["active_flag"] = True
            if "is_current" not in out.columns:
                out["is_current"] = True
            if "deleted_flag" not in out.columns:
                out["deleted_flag"] = False
            out["active_flag"] = out["active_flag"].map(self._as_bool)
            out["is_current"] = out["is_current"].map(self._as_bool)
            out["deleted_flag"] = out["deleted_flag"].map(self._as_bool)
            return out.reset_index(drop=True)

        return self._cached(cache_key, _load, ttl_seconds=300)

    def _lookup_rows_with_status(self, rows: pd.DataFrame, *, as_of_ts: Any) -> pd.DataFrame:
        if rows.empty:
            out = rows.copy()
            out["status"] = pd.Series(dtype="object")
            return out

        as_of = self._parse_lookup_ts(as_of_ts, fallback=self._now())
        statuses: list[str] = []
        normalized_from: list[str] = []
        normalized_to: list[str] = []
        for row in rows.to_dict("records"):
            start, end = self._normalize_lookup_window(row.get("valid_from_ts"), row.get("valid_to_ts"))
            statuses.append(self._lookup_status_for_window(start, end, as_of=as_of))
            normalized_from.append(start.isoformat())
            normalized_to.append(end.isoformat())
        out = rows.copy()
        out["status"] = statuses
        out["valid_from_ts"] = normalized_from
        out["valid_to_ts"] = normalized_to
        return out

    def list_lookup_option_versions(
        self,
        lookup_type: str,
        *,
        as_of_ts: Any = None,
        status_filter: str = "all",
        include_deleted: bool = False,
    ) -> pd.DataFrame:
        lookup_key = self._normalize_lookup_type(lookup_type)
        out = self._lookup_versions_frame(lookup_key)
        if out.empty:
            return pd.DataFrame(columns=self._lookup_columns() + ["status"])
        out = out[out["is_current"]].copy()
        if not include_deleted:
            out = out[~out["deleted_flag"]].copy()
        out = self._lookup_rows_with_status(out, as_of_ts=as_of_ts)
        filter_value = str(status_filter or "all").strip().lower()
        if filter_value in {"active", "historical", "future"}:
            out = out[out["status"].astype(str) == filter_value].copy()
        return out.sort_values(
            ["sort_order", "option_label", "valid_from_ts", "option_code"],
            kind="stable",
        ).reset_index(drop=True)

    def list_lookup_options(
        self,
        lookup_type: str | None = None,
        *,
        active_only: bool = False,
        as_of_ts: Any = None,
    ) -> pd.DataFrame:
        out = self._lookup_versions_frame(lookup_type)
        if out.empty:
            return out
        out = out[out["is_current"]].copy()
        out = out[~out["deleted_flag"]].copy()
        out = self._lookup_rows_with_status(out, as_of_ts=as_of_ts)
        if active_only:
            out = out[out["status"].astype(str) == "active"].copy()
        return out.sort_values(
            ["lookup_type", "sort_order", "option_label", "option_code"],
            kind="stable",
        ).reset_index(drop=True)

    def list_doc_source_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_DOC_SOURCE, active_only=True)
        if rows.empty:
            return list(DEFAULT_DOC_SOURCE_OPTIONS)
        values: list[str] = []
        seen: set[str] = set()
        for raw in rows["option_code"].tolist():
            value = str(raw).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values or list(DEFAULT_DOC_SOURCE_OPTIONS)

    def list_doc_tag_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_DOC_TAG, active_only=True)
        if rows.empty:
            return list(DEFAULT_DOC_TAG_OPTIONS)
        values: list[str] = []
        seen: set[str] = set()
        for raw in rows["option_code"].tolist():
            value = str(raw).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values or list(DEFAULT_DOC_TAG_OPTIONS)

    def list_owner_role_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_OWNER_ROLE, active_only=True)
        if rows.empty:
            return list(DEFAULT_OWNER_ROLE_OPTIONS)
        values: list[str] = []
        seen: set[str] = set()
        for raw in rows["option_code"].tolist():
            value = str(raw).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values or list(DEFAULT_OWNER_ROLE_OPTIONS)

    def list_assignment_type_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_ASSIGNMENT_TYPE, active_only=True)
        if rows.empty:
            return list(DEFAULT_ASSIGNMENT_TYPE_OPTIONS)
        values: list[str] = []
        seen: set[str] = set()
        for raw in rows["option_code"].tolist():
            value = str(raw).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values or list(DEFAULT_ASSIGNMENT_TYPE_OPTIONS)

    def list_contact_type_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_CONTACT_TYPE, active_only=True)
        if rows.empty:
            return list(DEFAULT_CONTACT_TYPE_OPTIONS)
        values: list[str] = []
        seen: set[str] = set()
        for raw in rows["option_code"].tolist():
            value = str(raw).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values or list(DEFAULT_CONTACT_TYPE_OPTIONS)

    def list_project_type_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_PROJECT_TYPE, active_only=True)
        if rows.empty:
            return list(DEFAULT_PROJECT_TYPE_OPTIONS)
        values: list[str] = []
        seen: set[str] = set()
        for raw in rows["option_code"].tolist():
            value = str(raw).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values or list(DEFAULT_PROJECT_TYPE_OPTIONS)

    def list_workflow_status_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_WORKFLOW_STATUS, active_only=True)
        if rows.empty:
            return list(DEFAULT_WORKFLOW_STATUS_OPTIONS)
        values: list[str] = []
        seen: set[str] = set()
        for raw in rows["option_code"].tolist():
            value = str(raw).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
        return values or list(DEFAULT_WORKFLOW_STATUS_OPTIONS)

    def list_offering_type_options(self) -> list[str]:
        rows = self.list_lookup_options(LOOKUP_TYPE_OFFERING_TYPE, active_only=True)
        if rows.empty:
            return [label for _, label in DEFAULT_OFFERING_TYPE_CHOICES]
        out: list[str] = []
        for row in rows.to_dict("records"):
            label = str(row.get("option_label") or "").strip()
            code = str(row.get("option_code") or "").strip().lower()
            value = label or self._lookup_label_from_code(code)
            if value and value not in out:
                out.append(value)
        return out or [label for _, label in DEFAULT_OFFERING_TYPE_CHOICES]

    def _list_lookup_label_options(self, lookup_type: str, fallback_choices: list[tuple[str, str]]) -> list[str]:
        rows = self.list_lookup_options(lookup_type, active_only=True)
        if rows.empty:
            return [label for _, label in fallback_choices]
        out: list[str] = []
        for row in rows.to_dict("records"):
            label = str(row.get("option_label") or "").strip()
            code = str(row.get("option_code") or "").strip().lower()
            value = label or self._lookup_label_from_code(code)
            if value and value not in out:
                out.append(value)
        return out or [label for _, label in fallback_choices]

    def list_offering_business_unit_options(self) -> list[str]:
        return self._list_lookup_label_options(
            LOOKUP_TYPE_OFFERING_BUSINESS_UNIT,
            list(DEFAULT_OFFERING_BUSINESS_UNIT_CHOICES),
        )

    def list_offering_service_type_options(self) -> list[str]:
        return self._list_lookup_label_options(
            LOOKUP_TYPE_OFFERING_SERVICE_TYPE,
            list(DEFAULT_OFFERING_SERVICE_TYPE_CHOICES),
        )

    def list_owner_organization_options(self) -> list[str]:
        return self._list_lookup_label_options(
            LOOKUP_TYPE_OWNER_ORGANIZATION,
            list(DEFAULT_OWNER_ORGANIZATION_CHOICES),
        )

    def list_vendor_category_options(self) -> list[str]:
        return self._list_lookup_label_options(
            LOOKUP_TYPE_VENDOR_CATEGORY,
            list(DEFAULT_VENDOR_CATEGORY_CHOICES),
        )

    def list_compliance_category_options(self) -> list[str]:
        return self._list_lookup_label_options(
            LOOKUP_TYPE_COMPLIANCE_CATEGORY,
            list(DEFAULT_COMPLIANCE_CATEGORY_CHOICES),
        )

    def list_gl_category_options(self) -> list[str]:
        return self._list_lookup_label_options(
            LOOKUP_TYPE_GL_CATEGORY,
            list(DEFAULT_GL_CATEGORY_CHOICES),
        )

    def list_risk_tier_options(self) -> list[str]:
        return self._list_lookup_label_options(
            LOOKUP_TYPE_RISK_TIER,
            list(DEFAULT_RISK_TIER_CHOICES),
        )

    def list_lifecycle_state_options(self) -> list[str]:
        return self._list_lookup_label_options(
            LOOKUP_TYPE_LIFECYCLE_STATE,
            list(DEFAULT_LIFECYCLE_STATE_CHOICES),
        )

    def save_lookup_option(
        self,
        *,
        option_id: str | None,
        lookup_type: str,
        option_code: str,
        option_label: str | None,
        sort_order: int,
        valid_from_ts: Any,
        valid_to_ts: Any,
        updated_by: str,
    ) -> None:
        lookup_key = self._normalize_lookup_type(lookup_type)
        code = self._normalize_lookup_code(option_code)
        label = str(option_label or "").strip() or self._lookup_label_from_code(code)
        safe_sort_order = max(1, int(sort_order or 1))
        start_ts, end_ts = self._normalize_lookup_window(valid_from_ts, valid_to_ts)
        now = self._now()
        actor_ref = self._actor_ref(updated_by)
        current_rows = self.list_lookup_options(lookup_key, active_only=False).to_dict("records")

        selected_row: dict[str, Any] | None = None
        selected_id = str(option_id or "").strip()
        if selected_id:
            selected_row = next(
                (row for row in current_rows if str(row.get("option_id") or "") == selected_id),
                None,
            )
            if selected_row is None:
                raise ValueError("The selected option is no longer available for update.")
        else:
            matching_code_rows = [
                row
                for row in current_rows
                if self._normalize_lookup_code(str(row.get("option_code") or "")) == code
            ]
            if len(matching_code_rows) == 1:
                selected_row = matching_code_rows[0]

        for row in current_rows:
            if selected_row and str(row.get("option_id") or "") == str(selected_row.get("option_id") or ""):
                continue
            row_label = str(row.get("option_label") or "").strip().lower()
            if row_label != label.lower():
                continue
            row_start, row_end = self._normalize_lookup_window(row.get("valid_from_ts"), row.get("valid_to_ts"))
            if self._lookup_windows_overlap(start_ts, end_ts, row_start, row_end):
                raise ValueError("Label already exists in the selected active window.")

        overlapping_rows: list[dict[str, Any]] = []
        for row in current_rows:
            if selected_row and str(row.get("option_id") or "") == str(selected_row.get("option_id") or ""):
                continue
            row_start, row_end = self._normalize_lookup_window(row.get("valid_from_ts"), row.get("valid_to_ts"))
            if self._lookup_windows_overlap(start_ts, end_ts, row_start, row_end):
                overlapping_rows.append(row)
        overlapping_rows.sort(
            key=lambda item: (
                int(item.get("sort_order") or 999),
                str(item.get("option_label") or "").lower(),
                str(item.get("option_id") or ""),
            )
        )

        target = {
            "option_id": str(selected_row.get("option_id") or "") if selected_row else "",
            "lookup_type": lookup_key,
            "option_code": code,
            "option_label": label,
            "sort_order": safe_sort_order,
            "active_flag": True,
            "valid_from_ts": start_ts.isoformat(),
            "valid_to_ts": end_ts.isoformat(),
            "is_current": True,
            "deleted_flag": False,
            "updated_at": now.isoformat(),
            "updated_by": actor_ref,
        }
        target_index = min(safe_sort_order, len(overlapping_rows) + 1) - 1
        ordered = [dict(item) for item in overlapping_rows]
        ordered.insert(target_index, target)
        for idx, row in enumerate(ordered, start=1):
            row["sort_order"] = idx

        rows_to_close: dict[str, dict[str, Any]] = {}
        rows_to_insert: list[dict[str, Any]] = []
        overlap_by_id = {str(row.get("option_id") or ""): row for row in overlapping_rows}

        for row in ordered:
            row_id = str(row.get("option_id") or "")
            if row_id and row_id in overlap_by_id:
                prior = overlap_by_id[row_id]
                if int(prior.get("sort_order") or 0) == int(row.get("sort_order") or 0):
                    continue
                rows_to_close[row_id] = prior
                rows_to_insert.append(
                    {
                        "lookup_type": lookup_key,
                        "option_code": self._normalize_lookup_code(str(prior.get("option_code") or "")),
                        "option_label": str(prior.get("option_label") or "").strip()
                        or self._lookup_label_from_code(str(prior.get("option_code") or "")),
                        "sort_order": int(row.get("sort_order") or 1),
                        "active_flag": True,
                        "valid_from_ts": str(prior.get("valid_from_ts") or start_ts.isoformat()),
                        "valid_to_ts": str(prior.get("valid_to_ts") or end_ts.isoformat()),
                        "is_current": True,
                        "deleted_flag": False,
                    }
                )
                continue

            if selected_row:
                prior = selected_row
                changed = (
                    self._normalize_lookup_code(str(prior.get("option_code") or "")) != code
                    or str(prior.get("option_label") or "").strip() != label
                    or int(prior.get("sort_order") or 0) != int(row.get("sort_order") or 0)
                    or str(prior.get("valid_from_ts") or "") != start_ts.isoformat()
                    or str(prior.get("valid_to_ts") or "") != end_ts.isoformat()
                )
                if not changed:
                    continue
                rows_to_close[str(prior.get("option_id") or "")] = prior
            rows_to_insert.append(
                {
                    "lookup_type": lookup_key,
                    "option_code": code,
                    "option_label": label,
                    "sort_order": int(row.get("sort_order") or 1),
                    "active_flag": True,
                    "valid_from_ts": start_ts.isoformat(),
                    "valid_to_ts": end_ts.isoformat(),
                    "is_current": True,
                    "deleted_flag": False,
                }
            )

        if not rows_to_close and not rows_to_insert:
            return

        self._ensure_local_lookup_option_table()
        for close_row in rows_to_close.values():
            close_code = self._normalize_lookup_code(str(close_row.get("option_code") or ""))
            if close_code:
                self.client.execute(
                    (
                        f"DELETE FROM {self._table('app_lookup_option')} "
                        "WHERE lookup_type = %s AND option_code = %s AND coalesce(is_current, true) = false"
                    ),
                    (lookup_key, close_code),
                )
            self._execute_file(
                "updates/close_lookup_option_version.sql",
                params=(now, False, now, actor_ref, str(close_row.get("option_id") or "")),
                app_lookup_option=self._table("app_lookup_option"),
            )
        for row in rows_to_insert:
            self._execute_file(
                "inserts/create_lookup_option.sql",
                params=(
                    f"lkp-{lookup_key}-{row['option_code']}-{uuid.uuid4().hex[:12]}",
                    row["lookup_type"],
                    row["option_code"],
                    row["option_label"],
                    row["sort_order"],
                    row["active_flag"],
                    row["valid_from_ts"],
                    row["valid_to_ts"],
                    row["is_current"],
                    row["deleted_flag"],
                    now,
                    actor_ref,
                ),
                app_lookup_option=self._table("app_lookup_option"),
            )

    def delete_lookup_option(
        self,
        *,
        lookup_type: str,
        option_id: str,
        updated_by: str = "system",
    ) -> None:
        lookup_key = self._normalize_lookup_type(lookup_type)
        target_id = str(option_id or "").strip()
        if not target_id:
            raise ValueError("Lookup option id is required.")
        current_rows = self.list_lookup_options(lookup_key, active_only=False).to_dict("records")
        target = next((row for row in current_rows if str(row.get("option_id") or "") == target_id), None)
        if target is None:
            raise ValueError("The selected option is no longer available for removal.")
        now = self._now()
        actor_ref = self._actor_ref(updated_by)

        self._ensure_local_lookup_option_table()
        target_code = self._normalize_lookup_code(str(target.get("option_code") or "removed"))
        self.client.execute(
            (
                f"DELETE FROM {self._table('app_lookup_option')} "
                "WHERE lookup_type = %s AND option_code = %s AND coalesce(is_current, true) = false"
            ),
            (lookup_key, target_code),
        )
        self._execute_file(
            "updates/close_lookup_option_version.sql",
            params=(now, False, now, actor_ref, target_id),
            app_lookup_option=self._table("app_lookup_option"),
        )
        self._execute_file(
            "inserts/create_lookup_option.sql",
            params=(
                f"lkp-{lookup_key}-{self._normalize_lookup_code(str(target.get('option_code') or 'removed'))}-{uuid.uuid4().hex[:12]}",
                lookup_key,
                self._normalize_lookup_code(str(target.get("option_code") or "removed")),
                str(target.get("option_label") or ""),
                int(target.get("sort_order") or 999),
                False,
                now,
                datetime(9999, 12, 31, 23, 59, 59, tzinfo=UTC),
                True,
                True,
                now,
                actor_ref,
            ),
            app_lookup_option=self._table("app_lookup_option"),
        )

        target_start, target_end = self._normalize_lookup_window(
            target.get("valid_from_ts"),
            target.get("valid_to_ts"),
        )
        remaining = self.list_lookup_options(lookup_key, active_only=False).to_dict("records")
        overlapping: list[dict[str, Any]] = []
        for row in remaining:
            row_start, row_end = self._normalize_lookup_window(row.get("valid_from_ts"), row.get("valid_to_ts"))
            if self._lookup_windows_overlap(target_start, target_end, row_start, row_end):
                overlapping.append(row)
        overlapping.sort(
            key=lambda item: (
                int(item.get("sort_order") or 999),
                str(item.get("option_label") or "").lower(),
                str(item.get("option_id") or ""),
            )
        )
        rows_to_close: list[dict[str, Any]] = []
        rows_to_insert: list[dict[str, Any]] = []
        for idx, row in enumerate(overlapping, start=1):
            if int(row.get("sort_order") or 0) == idx:
                continue
            rows_to_close.append(row)
            rows_to_insert.append(
                {
                    "lookup_type": lookup_key,
                    "option_code": self._normalize_lookup_code(str(row.get("option_code") or "")),
                    "option_label": str(row.get("option_label") or "").strip()
                    or self._lookup_label_from_code(str(row.get("option_code") or "")),
                    "sort_order": idx,
                    "active_flag": True,
                    "valid_from_ts": str(row.get("valid_from_ts") or now.isoformat()),
                    "valid_to_ts": str(row.get("valid_to_ts") or datetime(9999, 12, 31, 23, 59, 59, tzinfo=UTC).isoformat()),
                    "is_current": True,
                    "deleted_flag": False,
                }
            )
        for close_row in rows_to_close:
            close_code = self._normalize_lookup_code(str(close_row.get("option_code") or ""))
            if close_code:
                self.client.execute(
                    (
                        f"DELETE FROM {self._table('app_lookup_option')} "
                        "WHERE lookup_type = %s AND option_code = %s AND coalesce(is_current, true) = false"
                    ),
                    (lookup_key, close_code),
                )
            self._execute_file(
                "updates/close_lookup_option_version.sql",
                params=(now, False, now, actor_ref, str(close_row.get("option_id") or "")),
                app_lookup_option=self._table("app_lookup_option"),
            )
        for row in rows_to_insert:
            self._execute_file(
                "inserts/create_lookup_option.sql",
                params=(
                    f"lkp-{lookup_key}-{row['option_code']}-{uuid.uuid4().hex[:12]}",
                    row["lookup_type"],
                    row["option_code"],
                    row["option_label"],
                    row["sort_order"],
                    row["active_flag"],
                    row["valid_from_ts"],
                    row["valid_to_ts"],
                    row["is_current"],
                    row["deleted_flag"],
                    now,
                    actor_ref,
                ),
                app_lookup_option=self._table("app_lookup_option"),
            )

    def record_contract_cancellation(
        self, contract_id: str, reason_code: str, notes: str, actor_user_principal: str
    ) -> str:
        event_id = str(uuid.uuid4())
        now = self._now()
        actor_ref = self._actor_ref(actor_user_principal)
        self._execute_file(
            "inserts/record_contract_cancellation_event.sql",
            params=(event_id, contract_id, "contract_cancelled", now, reason_code, notes, actor_ref),
            core_contract_event=self._table("core_contract_event"),
        )

        self._execute_file(
            "updates/record_contract_cancellation_contract_update.sql",
            params=("cancelled", True, now, actor_ref, contract_id),
            core_contract=self._table("core_contract"),
        )

        self._write_audit_entity_change(
            entity_name="core_contract",
            entity_id=contract_id,
            action_type="update",
            actor_user_principal=actor_ref,
            before_json=None,
            after_json={
                "contract_status": "cancelled",
                "cancelled_flag": True,
                "reason_code": reason_code,
                "notes": notes,
            },
            request_id=None,
        )
        return event_id

