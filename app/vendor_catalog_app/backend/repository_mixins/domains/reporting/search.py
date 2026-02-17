from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from vendor_catalog_app.core.repository_constants import *

LOGGER = logging.getLogger(__name__)


class RepositoryReportingSearchMixin:
    def search_vendors_typeahead(self, *, q: str = "", limit: int = 20) -> pd.DataFrame:
        limit = max(1, min(int(limit or 20), 100))
        columns = ["vendor_id", "label", "display_name", "legal_name", "lifecycle_state"]
        params: list[Any] = []
        where = "1 = 1"
        if q.strip():
            like = f"%{q.strip()}%"
            where = (
                "("
                "lower(v.vendor_id) LIKE lower(%s)"
                " OR lower(coalesce(v.display_name, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.legal_name, '')) LIKE lower(%s)"
                ")"
            )
            params.extend([like, like, like])
        return self._query_file(
            "reporting/search_vendors_typeahead.sql",
            params=tuple(params) if params else None,
            columns=columns,
            where_clause=where,
            limit=limit,
            core_vendor=self._table("core_vendor"),
        )

    def search_offerings_typeahead(self, *, vendor_id: str | None = None, q: str = "", limit: int = 20) -> pd.DataFrame:
        limit = max(1, min(int(limit or 20), 100))
        columns = [
            "offering_id",
            "vendor_id",
            "offering_name",
            "offering_type",
            "lob",
            "service_type",
            "lifecycle_state",
            "vendor_display_name",
            "label",
        ]
        filter_vendor = str(vendor_id or "").strip()
        where_parts = []
        params: list[Any] = []
        if filter_vendor:
            where_parts.append("o.vendor_id = %s")
            params.append(filter_vendor)
        if q.strip():
            like = f"%{q.strip()}%"
            where_parts.append(
                "("
                "lower(o.offering_id) LIKE lower(%s)"
                " OR lower(coalesce(o.offering_name, '')) LIKE lower(%s)"
                " OR lower(coalesce(o.offering_type, '')) LIKE lower(%s)"
                " OR lower(coalesce(o.lob, '')) LIKE lower(%s)"
                " OR lower(coalesce(o.service_type, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.display_name, v.legal_name, o.vendor_id)) LIKE lower(%s)"
                ")"
            )
            params.extend([like, like, like, like, like, like])
        where = " AND ".join(where_parts) if where_parts else "1 = 1"
        self._ensure_local_offering_columns()
        return self._query_file(
            "reporting/search_offerings_typeahead.sql",
            params=tuple(params) if params else None,
            columns=columns,
            where_clause=where,
            limit=limit,
            core_vendor_offering=self._table("core_vendor_offering"),
            core_vendor=self._table("core_vendor"),
        )

    def search_projects_typeahead(self, *, q: str = "", limit: int = 20) -> pd.DataFrame:
        limit = max(1, min(int(limit or 20), 100))
        columns = ["project_id", "project_name", "status", "vendor_id", "vendor_display_name", "label"]
        params: list[Any] = []
        where_parts = ["coalesce(p.active_flag, true) = true"]
        if q.strip():
            like = f"%{q.strip()}%"
            where_parts.append(
                "("
                "lower(p.project_id) LIKE lower(%s)"
                " OR lower(coalesce(p.project_name, '')) LIKE lower(%s)"
                " OR lower(coalesce(p.status, '')) LIKE lower(%s)"
                " OR lower(coalesce(p.owner_principal, '')) LIKE lower(%s)"
                " OR lower(coalesce(p.description, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.display_name, v.legal_name, p.vendor_id, '')) LIKE lower(%s)"
                ")"
            )
            params.extend([like, like, like, like, like, like])
        where = " AND ".join(where_parts)
        return self._query_file(
            "reporting/search_projects_typeahead.sql",
            params=tuple(params) if params else None,
            columns=columns,
            where_clause=where,
            limit=limit,
            app_project=self._table("app_project"),
            core_vendor=self._table("core_vendor"),
        )

    def search_contracts_typeahead(
        self,
        *,
        q: str = "",
        limit: int = 20,
        active_or_future_only: bool = False,
    ) -> pd.DataFrame:
        limit = max(1, min(int(limit or 20), 100))
        columns = [
            "contract_id",
            "vendor_id",
            "offering_id",
            "contract_number",
            "contract_status",
            "vendor_display_name",
            "offering_name",
            "label",
        ]
        params: list[Any] = []
        where_parts: list[str] = ["1 = 1"]
        if active_or_future_only:
            where_parts.append(
                "("
                "lower(coalesce(c.contract_status, '')) = 'active'"
                " OR c.start_date > current_date"
                ")"
            )
            where_parts.append("coalesce(c.cancelled_flag, false) = false")
        if q.strip():
            like = f"%{q.strip()}%"
            where_parts.append(
                "("
                "lower(c.contract_id) LIKE lower(%s)"
                " OR lower(coalesce(c.contract_number, '')) LIKE lower(%s)"
                " OR lower(coalesce(c.vendor_id, '')) LIKE lower(%s)"
                " OR lower(coalesce(c.offering_id, '')) LIKE lower(%s)"
                " OR lower(coalesce(c.contract_status, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.display_name, v.legal_name, c.vendor_id, '')) LIKE lower(%s)"
                " OR lower(coalesce(o.offering_name, c.offering_id, '')) LIKE lower(%s)"
                ")"
            )
            params.extend([like, like, like, like, like, like, like])
        where = " AND ".join(where_parts)
        return self._query_file(
            "reporting/search_contracts_typeahead.sql",
            params=tuple(params) if params else None,
            columns=columns,
            where_clause=where,
            limit=limit,
            core_contract=self._table("core_contract"),
            core_vendor=self._table("core_vendor"),
            core_vendor_offering=self._table("core_vendor_offering"),
        )

    def search_contacts_typeahead(self, *, vendor_id: str | None = None, q: str = "", limit: int = 20) -> pd.DataFrame:
        limit = max(1, min(int(limit or 20), 100))
        columns = [
            "full_name",
            "email",
            "phone",
            "contact_type",
            "vendor_id",
            "vendor_display_name",
            "usage_count",
            "label",
        ]
        filter_vendor = str(vendor_id or "").strip()
        where_parts = [
            "coalesce(src.active_flag, true) = true",
            "coalesce(trim(src.full_name), '') <> ''",
        ]
        params: list[Any] = []
        if filter_vendor:
            where_parts.append("src.vendor_id = %s")
            params.append(filter_vendor)
        if q.strip():
            like = f"%{q.strip()}%"
            where_parts.append(
                "("
                "lower(coalesce(src.full_name, '')) LIKE lower(%s)"
                " OR lower(coalesce(src.email, '')) LIKE lower(%s)"
                " OR lower(coalesce(src.phone, '')) LIKE lower(%s)"
                " OR lower(coalesce(src.contact_type, '')) LIKE lower(%s)"
                " OR lower(coalesce(src.vendor_display_name, '')) LIKE lower(%s)"
                ")"
            )
            params.extend([like, like, like, like, like])
        where = " AND ".join(where_parts)
        return self._query_file(
            "reporting/search_contacts_typeahead.sql",
            params=tuple(params) if params else None,
            columns=columns,
            where_clause=where,
            limit=limit,
            core_vendor_contact=self._table("core_vendor_contact"),
            core_offering_contact=self._table("core_offering_contact"),
            core_vendor_offering=self._table("core_vendor_offering"),
            core_vendor=self._table("core_vendor"),
        )

    def list_contracts_workspace(
        self,
        *,
        search_text: str = "",
        status: str = "all",
        contract_scope: str = "all",
        limit: int = 500,
    ) -> pd.DataFrame:
        limit = max(25, min(int(limit or 500), 5000))
        normalized_status = str(status or "all").strip().lower() or "all"
        normalized_scope = str(contract_scope or "all").strip().lower() or "all"
        columns = [
            "contract_id",
            "vendor_id",
            "vendor_display_name",
            "offering_id",
            "offering_name",
            "contract_number",
            "contract_status",
            "start_date",
            "end_date",
            "cancelled_flag",
            "annual_value",
            "updated_at",
        ]

        where_parts: list[str] = ["1 = 1"]
        params: list[Any] = []

        if normalized_status != "all":
            if normalized_status == "cancelled":
                where_parts.append(
                    "(coalesce(c.cancelled_flag, false) = true OR lower(coalesce(c.contract_status, '')) = 'cancelled')"
                )
            else:
                where_parts.append("lower(coalesce(c.contract_status, '')) = %s")
                params.append(normalized_status)

        if normalized_scope == "vendor":
            where_parts.append("coalesce(trim(c.offering_id), '') = ''")
        elif normalized_scope == "offering":
            where_parts.append("coalesce(trim(c.offering_id), '') <> ''")

        if search_text.strip():
            like = f"%{search_text.strip()}%"
            where_parts.append(
                "("
                "lower(c.contract_id) LIKE lower(%s)"
                " OR lower(coalesce(c.contract_number, '')) LIKE lower(%s)"
                " OR lower(coalesce(c.vendor_id, '')) LIKE lower(%s)"
                " OR lower(coalesce(c.offering_id, '')) LIKE lower(%s)"
                " OR lower(coalesce(c.contract_status, '')) LIKE lower(%s)"
                " OR lower(coalesce(v.display_name, v.legal_name, c.vendor_id, '')) LIKE lower(%s)"
                " OR lower(coalesce(o.offering_name, c.offering_id, '')) LIKE lower(%s)"
                ")"
            )
            params.extend([like, like, like, like, like, like, like])

        where_clause = " AND ".join(where_parts)

        def _load() -> pd.DataFrame:
            frame = self._query_file(
                "reporting/list_contracts_workspace.sql",
                params=tuple(params) if params else None,
                columns=columns,
                where_clause=where_clause,
                limit=limit,
                core_contract=self._table("core_contract"),
                core_vendor=self._table("core_vendor"),
                core_vendor_offering=self._table("core_vendor_offering"),
            )
            if frame.empty:
                return frame
            frame["annual_value"] = pd.to_numeric(frame.get("annual_value"), errors="coerce").fillna(0.0)
            return frame

        return self._cached(
            ("list_contracts_workspace", search_text.strip().lower(), normalized_status, normalized_scope, int(limit)),
            _load,
            ttl_seconds=60,
        )

