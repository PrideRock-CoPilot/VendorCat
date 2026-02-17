from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


REQUIRED_TABLES = {
    "lkp_line_of_business",
    "lkp_service_type",
    "lkp_owner_role",
    "lkp_contact_type",
    "lkp_lifecycle_state",
    "lkp_risk_tier",
    "vendor",
    "offering",
    "vendor_identifier",
    "project",
    "project_offering_map",
    "vendor_lob_assignment",
    "offering_lob_assignment",
    "vendor_owner_assignment",
    "offering_owner_assignment",
    "project_owner_assignment",
    "vendor_contact",
    "offering_contact",
    "change_request",
    "change_event",
    "schema_version",
    "vendor_merge_event",
    "vendor_merge_member",
    "vendor_merge_snapshot",
    "vendor_survivorship_decision",
    "app_user_directory",
    "app_user_settings",
    "app_usage_log",
    "sec_role_definition",
    "sec_role_permission",
    "sec_user_role_map",
    "sec_group_role_map",
    "sec_user_org_scope",
    "audit_entity_change",
    "audit_workflow_event",
    "audit_access_event",
    "vendor_help_article",
    "vendor_help_feedback",
    "vendor_help_issue",
    "src_ingest_batch",
    "src_peoplesoft_vendor_raw",
    "src_zycus_vendor_raw",
    "src_spreadsheet_vendor_raw",
    "core_vendor",
    "core_vendor_identifier",
    "core_vendor_contact",
    "core_vendor_org_assignment",
    "core_vendor_business_owner",
    "core_vendor_offering",
    "core_offering_business_owner",
    "core_offering_contact",
    "core_contract",
    "core_contract_event",
    "core_vendor_demo",
    "core_vendor_demo_score",
    "core_vendor_demo_note",
    "hist_vendor",
    "hist_vendor_offering",
    "hist_contract",
    "app_onboarding_request",
    "app_vendor_change_request",
    "app_onboarding_task",
    "app_onboarding_approval",
    "app_access_request",
    "app_note",
    "app_employee_directory",
    "app_lookup_option",
    "app_project",
    "app_project_vendor_map",
    "app_project_offering_map",
    "app_project_demo",
    "app_project_note",
    "app_offering_profile",
    "app_offering_data_flow",
    "app_offering_ticket",
    "app_offering_invoice",
    "app_document_link",
}

REQUIRED_FOREIGN_KEYS: dict[str, set[str]] = {
    "vendor": {"lkp_lifecycle_state", "lkp_risk_tier", "lkp_line_of_business"},
    "offering": {"vendor", "lkp_lifecycle_state", "lkp_line_of_business", "lkp_service_type"},
    "project": {"lkp_lifecycle_state", "lkp_line_of_business"},
    "vendor_identifier": {"vendor"},
    "vendor_lob_assignment": {"vendor", "lkp_line_of_business"},
    "offering_lob_assignment": {"offering", "lkp_line_of_business"},
    "vendor_owner_assignment": {"vendor", "lkp_owner_role"},
    "offering_owner_assignment": {"offering", "lkp_owner_role"},
    "project_owner_assignment": {"project", "lkp_owner_role"},
    "vendor_contact": {"vendor", "lkp_contact_type"},
    "offering_contact": {"offering", "lkp_contact_type"},
    "project_offering_map": {"project", "offering"},
    "change_event": {"change_request"},
    "vendor_merge_event": {"vendor", "change_request"},
    "vendor_merge_member": {"vendor_merge_event", "vendor"},
    "vendor_merge_snapshot": {"vendor_merge_event", "vendor"},
    "vendor_survivorship_decision": {"vendor_merge_event", "vendor"},
    "app_user_settings": {"app_user_directory"},
    "sec_role_permission": {"sec_role_definition"},
    "sec_user_role_map": {"sec_role_definition"},
    "sec_group_role_map": {"sec_role_definition"},
    "audit_entity_change": {"change_request"},
    "audit_access_event": {"sec_role_definition"},
    "vendor_help_feedback": {"vendor_help_article"},
    "vendor_help_issue": {"vendor_help_article"},
    "src_peoplesoft_vendor_raw": {"src_ingest_batch"},
    "src_zycus_vendor_raw": {"src_ingest_batch"},
    "src_spreadsheet_vendor_raw": {"src_ingest_batch"},
    "core_vendor_identifier": {"core_vendor"},
    "core_vendor_contact": {"core_vendor"},
    "core_vendor_org_assignment": {"core_vendor"},
    "core_vendor_business_owner": {"core_vendor"},
    "core_vendor_offering": {"core_vendor"},
    "core_offering_business_owner": {"core_vendor_offering"},
    "core_offering_contact": {"core_vendor_offering"},
    "core_contract": {"core_vendor", "core_vendor_offering"},
    "core_contract_event": {"core_contract"},
    "core_vendor_demo": {"core_vendor", "core_vendor_offering"},
    "core_vendor_demo_score": {"core_vendor_demo"},
    "core_vendor_demo_note": {"core_vendor_demo"},
    "hist_vendor": {"core_vendor"},
    "hist_vendor_offering": {"core_vendor_offering"},
    "hist_contract": {"core_contract"},
    "app_vendor_change_request": {"core_vendor"},
    "app_onboarding_task": {"app_onboarding_request"},
    "app_onboarding_approval": {"app_onboarding_request"},
    "app_access_request": {"sec_role_definition"},
    "app_project": {"core_vendor"},
    "app_project_vendor_map": {"app_project", "core_vendor"},
    "app_project_offering_map": {"app_project", "core_vendor", "core_vendor_offering"},
    "app_project_demo": {"app_project", "core_vendor", "core_vendor_offering", "core_vendor_demo"},
    "app_project_note": {"app_project", "core_vendor"},
    "app_offering_profile": {"core_vendor", "core_vendor_offering"},
    "app_offering_data_flow": {"core_vendor", "core_vendor_offering"},
    "app_offering_ticket": {"core_vendor", "core_vendor_offering"},
    "app_offering_invoice": {"core_vendor", "core_vendor_offering"},
}

REQUIRED_UNIQUE_GROUPS: dict[str, set[tuple[str, ...]]] = {
    "vendor_identifier": {("source_system_code", "source_vendor_key")},
    "vendor_merge_member": {("merge_id", "vendor_id")},
    "app_user_directory": {("login_identifier",)},
    "app_user_settings": {("user_principal", "setting_key")},
    "sec_role_permission": {("role_code", "object_name", "action_code")},
    "sec_user_role_map": {("user_principal", "role_code", "active_flag")},
    "sec_group_role_map": {("group_principal", "role_code", "active_flag")},
    "sec_user_org_scope": {("user_principal", "org_id", "scope_level", "active_flag")},
    "vendor_help_article": {("slug",)},
    "src_peoplesoft_vendor_raw": {("batch_id", "source_record_id", "source_extract_ts")},
    "src_zycus_vendor_raw": {("batch_id", "source_record_id", "source_extract_ts")},
    "src_spreadsheet_vendor_raw": {("batch_id", "source_record_id", "source_extract_ts")},
    "core_vendor_identifier": {("vendor_id", "identifier_type", "identifier_value")},
    "core_vendor_offering": {("vendor_id", "offering_name")},
    "hist_vendor": {("vendor_id", "version_no")},
    "hist_vendor_offering": {("offering_id", "version_no")},
    "hist_contract": {("contract_id", "version_no")},
    "app_lookup_option": {("lookup_type", "option_code", "is_current")},
    "app_project_vendor_map": {("project_id", "vendor_id", "active_flag")},
    "app_project_offering_map": {("project_id", "offering_id", "active_flag")},
    "app_offering_data_flow": {("offering_id", "flow_name", "direction", "active_flag")},
    "app_document_link": {("entity_type", "entity_id", "doc_url", "active_flag")},
}

REQUIRED_VIEWS = {
    "vw_employee_directory",
    "rpt_spend_fact",
    "rpt_contract_renewals",
    "rpt_contract_cancellations",
}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()
    return {row[0] for row in rows}


def _view_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'view'
        """
    ).fetchall()
    return {row[0] for row in rows}


def _fk_targets(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    return {row[2] for row in rows}


def _unique_index_column_sets(conn: sqlite3.Connection, table_name: str) -> set[tuple[str, ...]]:
    index_rows = conn.execute(f"PRAGMA index_list({table_name})").fetchall()
    unique_sets: set[tuple[str, ...]] = set()
    for index_row in index_rows:
        index_name = index_row[1]
        is_unique = int(index_row[2]) == 1
        if not is_unique:
            continue
        columns_rows = conn.execute(f"PRAGMA index_info({index_name})").fetchall()
        ordered = tuple(row[2] for row in sorted(columns_rows, key=lambda x: x[0]))
        if ordered:
            unique_sets.add(ordered)
    return unique_sets


def verify(db_path: Path) -> list[str]:
    failures: list[str] = []

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        tables = _table_names(conn)
        views = _view_names(conn)
        missing_tables = sorted(REQUIRED_TABLES - tables)
        if missing_tables:
            failures.append("Missing required tables: " + ", ".join(missing_tables))

        missing_views = sorted(REQUIRED_VIEWS - views)
        if missing_views:
            failures.append("Missing required views: " + ", ".join(missing_views))

        for table_name, expected_refs in REQUIRED_FOREIGN_KEYS.items():
            if table_name not in tables:
                continue
            fk_refs = _fk_targets(conn, table_name)
            missing_refs = sorted(expected_refs - fk_refs)
            if missing_refs:
                failures.append(
                    f"Missing foreign keys on {table_name}: expected refs to {', '.join(missing_refs)}"
                )

        for table_name, expected_unique_groups in REQUIRED_UNIQUE_GROUPS.items():
            if table_name not in tables:
                continue
            actual_unique_groups = _unique_index_column_sets(conn, table_name)
            for expected_group in expected_unique_groups:
                if expected_group not in actual_unique_groups:
                    failures.append(
                        f"Missing unique constraint on {table_name}: ({', '.join(expected_group)})"
                    )

    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify V1 local schema quality: required tables, FKs, and unique constraints."
    )
    parser.add_argument(
        "--db-path",
        default=str(Path(__file__).resolve().parents[1] / "local_db" / "twvendor_local_v1.db"),
        help="Path to SQLite V1 database.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    db_path = Path(args.db_path).resolve()

    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}")
        raise SystemExit(2)

    failures = verify(db_path)
    if failures:
        print("V1 schema quality verification FAILED")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print("V1 schema quality verification PASSED")
