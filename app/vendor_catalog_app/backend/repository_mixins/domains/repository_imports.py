from __future__ import annotations

import json
import uuid
from typing import Any

IMPORT_STAGE_AREA_TABLES = {
    "vendor": "app_import_stage_vendor",
    "vendor_contact": "app_import_stage_vendor_contact",
    "vendor_owner": "app_import_stage_vendor_owner",
    "offering": "app_import_stage_offering",
    "offering_owner": "app_import_stage_offering_owner",
    "offering_contact": "app_import_stage_offering_contact",
    "contract": "app_import_stage_contract",
    "project": "app_import_stage_project",
    "invoice": "app_import_stage_invoice",
    "payment": "app_import_stage_payment",
}


class RepositoryImportsMixin:
    def create_import_stage_job(
        self,
        *,
        layout_key: str,
        source_system: str,
        source_object: str | None,
        file_name: str | None,
        file_type: str | None,
        detected_format: str | None,
        parser_config: dict[str, Any] | None,
        row_count: int,
        actor_user_principal: str,
    ) -> str:
        import_job_id = f"imjob-{uuid.uuid4()}"
        now = self._now().isoformat()
        self._execute_file(
            "inserts/create_import_stage_job.sql",
            params=(
                import_job_id,
                str(layout_key or "").strip().lower(),
                str(source_system or "").strip().lower() or "unknown",
                (str(source_object or "").strip() or None),
                (str(file_name or "").strip() or None),
                (str(file_type or "").strip().lower() or None),
                (str(detected_format or "").strip().lower() or None),
                (json.dumps(parser_config or {}, default=str) if parser_config else None),
                int(row_count or 0),
                "staged",
                0,
                0,
                0,
                0,
                None,
                now,
                str(actor_user_principal or "").strip() or "system",
                None,
                None,
            ),
            app_import_job=self._table("app_import_job"),
        )
        return import_job_id

    def create_import_stage_rows(
        self,
        *,
        import_job_id: str,
        preview_rows: list[dict[str, Any]],
    ) -> int:
        if not import_job_id or not preview_rows:
            return 0

        statement = self._sql(
            "inserts/create_import_stage_row.sql",
            app_import_stage_row=self._table("app_import_stage_row"),
        )
        now = self._now().isoformat()
        staged_count = 0
        for row in preview_rows:
            row_index = int(row.get("row_index") or 0)
            if row_index <= 0:
                continue
            staged_count += 1
            stage_row_id = f"imrow-{uuid.uuid4()}"
            payload = {
                "line_number": str(row.get("line_number") or ""),
                "row_data": dict(row.get("row_data") or {}),
                "notes": list(row.get("notes") or []),
                "errors": list(row.get("errors") or []),
                "row_status": str(row.get("row_status") or ""),
            }
            self.client.execute(
                statement,
                (
                    stage_row_id,
                    import_job_id,
                    row_index,
                    str(row.get("line_number") or None) if row.get("line_number") else None,
                    json.dumps(payload, default=str),
                    str(row.get("suggested_action") or "").strip().lower() or None,
                    str(row.get("suggested_target_id") or "").strip() or None,
                    now,
                ),
            )
        self._cache_clear()
        return staged_count

    def finalize_import_stage_job(
        self,
        *,
        import_job_id: str,
        created_count: int,
        merged_count: int,
        skipped_count: int,
        failed_count: int,
        actor_user_principal: str,
        error_message: str | None = None,
    ) -> None:
        if not import_job_id:
            return
        final_status = "applied" if int(failed_count or 0) == 0 else "applied_with_errors"
        self._execute_file(
            "updates/finalize_import_stage_job.sql",
            params=(
                final_status,
                int(created_count or 0),
                int(merged_count or 0),
                int(skipped_count or 0),
                int(failed_count or 0),
                (str(error_message or "").strip() or None),
                self._now().isoformat(),
                str(actor_user_principal or "").strip() or "system",
                import_job_id,
            ),
            app_import_job=self._table("app_import_job"),
        )

    def create_import_stage_area_rows(
        self,
        *,
        import_job_id: str,
        stage_area_rows: dict[str, list[dict[str, Any]]],
    ) -> int:
        if not import_job_id or not stage_area_rows:
            return 0
        staged_count = 0
        now = self._now().isoformat()
        for area_key, rows in dict(stage_area_rows or {}).items():
            area = str(area_key or "").strip().lower()
            table_name = str(IMPORT_STAGE_AREA_TABLES.get(area) or "").strip()
            if not table_name:
                continue
            statement = self._sql(
                "inserts/create_import_stage_area_row.sql",
                area_stage_table=self._table(table_name),
            )
            for row in list(rows or []):
                payload = dict(row.get("payload") or {})
                if not payload:
                    continue
                try:
                    self.client.execute(
                        statement,
                        (
                            f"imarea-{uuid.uuid4()}",
                            import_job_id,
                            int(row.get("row_index") or 0),
                            str(row.get("line_number") or None) if row.get("line_number") else None,
                            json.dumps(payload, default=str),
                            now,
                        ),
                    )
                    staged_count += 1
                except Exception:
                    # Area staging should not block core import stage behavior.
                    continue
        if staged_count:
            self._cache_clear()
        return staged_count
