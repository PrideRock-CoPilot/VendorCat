from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


BASELINE_RULES: dict[str, tuple[str, int]] = {
    "active_roles": ("SELECT COUNT(*) FROM sec_role_definition WHERE active_flag = 1", 3),
    "role_permissions": ("SELECT COUNT(*) FROM sec_role_permission WHERE active_flag = 1", 5),
    "user_role_grants": ("SELECT COUNT(*) FROM sec_user_role_map WHERE active_flag = 1", 3),
    "user_directory": ("SELECT COUNT(*) FROM app_user_directory WHERE active_flag = 1", 3),
    "employee_directory": ("SELECT COUNT(*) FROM app_employee_directory WHERE active_flag = 1", 3),
    "vendors": ("SELECT COUNT(*) FROM core_vendor", 2),
    "vendor_identifiers": ("SELECT COUNT(*) FROM core_vendor_identifier", 2),
    "vendor_contacts": ("SELECT COUNT(*) FROM core_vendor_contact", 2),
    "vendor_owners": ("SELECT COUNT(*) FROM core_vendor_business_owner WHERE active_flag = 1", 1),
    "offerings": ("SELECT COUNT(*) FROM core_vendor_offering", 3),
    "offering_owners": ("SELECT COUNT(*) FROM core_offering_business_owner WHERE active_flag = 1", 1),
    "offering_contacts": ("SELECT COUNT(*) FROM core_offering_contact WHERE active_flag = 1", 1),
    "offering_profiles": ("SELECT COUNT(*) FROM app_offering_profile", 1),
    "offering_tickets": ("SELECT COUNT(*) FROM app_offering_ticket WHERE active_flag = 1", 1),
    "offering_invoices": ("SELECT COUNT(*) FROM app_offering_invoice WHERE active_flag = 1", 1),
    "offering_data_flows": ("SELECT COUNT(*) FROM app_offering_data_flow WHERE active_flag = 1", 1),
    "contracts": ("SELECT COUNT(*) FROM core_contract", 2),
    "contract_events": ("SELECT COUNT(*) FROM core_contract_event", 1),
    "demos": ("SELECT COUNT(*) FROM core_vendor_demo", 1),
    "demo_scores": ("SELECT COUNT(*) FROM core_vendor_demo_score", 1),
    "demo_notes": ("SELECT COUNT(*) FROM core_vendor_demo_note", 1),
    "projects": ("SELECT COUNT(*) FROM app_project WHERE active_flag = 1", 1),
    "project_vendor_map": ("SELECT COUNT(*) FROM app_project_vendor_map WHERE active_flag = 1", 1),
    "project_offering_map": ("SELECT COUNT(*) FROM app_project_offering_map WHERE active_flag = 1", 1),
    "project_demos": ("SELECT COUNT(*) FROM app_project_demo WHERE active_flag = 1", 1),
    "project_notes": ("SELECT COUNT(*) FROM app_project_note WHERE active_flag = 1", 1),
    "doc_links": ("SELECT COUNT(*) FROM app_document_link WHERE active_flag = 1", 1),
    "onboarding_requests": ("SELECT COUNT(*) FROM app_onboarding_request", 1),
    "onboarding_tasks": ("SELECT COUNT(*) FROM app_onboarding_task", 1),
    "onboarding_approvals": ("SELECT COUNT(*) FROM app_onboarding_approval", 1),
    "vendor_change_requests": ("SELECT COUNT(*) FROM app_vendor_change_request", 1),
    "ingest_batches": ("SELECT COUNT(*) FROM src_ingest_batch", 1),
    "source_peoplesoft": ("SELECT COUNT(*) FROM src_peoplesoft_vendor_raw", 1),
    "help_articles": ("SELECT COUNT(*) FROM vendor_help_article", 3),
    "help_feedback": ("SELECT COUNT(*) FROM vendor_help_feedback", 1),
    "help_issues": ("SELECT COUNT(*) FROM vendor_help_issue", 1),
    "usage_events": ("SELECT COUNT(*) FROM app_usage_log", 1),
    "audit_entity_events": ("SELECT COUNT(*) FROM audit_entity_change", 1),
    "audit_workflow_events": ("SELECT COUNT(*) FROM audit_workflow_event", 1),
    "audit_access_events": ("SELECT COUNT(*) FROM audit_access_event", 1),
    "hist_vendor": ("SELECT COUNT(*) FROM hist_vendor", 1),
    "hist_offering": ("SELECT COUNT(*) FROM hist_vendor_offering", 1),
    "hist_contract": ("SELECT COUNT(*) FROM hist_contract", 1),
    "rpt_spend_fact_rows": ("SELECT COUNT(*) FROM rpt_spend_fact", 1),
    "rpt_contract_renewals_rows": ("SELECT COUNT(*) FROM rpt_contract_renewals", 1),
    "vw_employee_directory_rows": ("SELECT COUNT(*) FROM vw_employee_directory", 1),
}

FULL_PROFILE_ADDITIONAL_RULES: dict[str, tuple[str, int]] = {
    "full_vendors": ("SELECT COUNT(*) FROM core_vendor", 100),
    "full_projects": ("SELECT COUNT(*) FROM app_project", 50),
    "full_usage_events": ("SELECT COUNT(*) FROM app_usage_log", 1000),
    "full_user_directory": ("SELECT COUNT(*) FROM app_user_directory", 200),
    "full_onboarding_requests": ("SELECT COUNT(*) FROM app_onboarding_request", 40),
}

RELATIONSHIP_RULES: dict[str, str] = {
    "contracts_join_vendors": """
        SELECT COUNT(*)
        FROM core_contract c
        INNER JOIN core_vendor v ON c.vendor_id = v.vendor_id
    """,
    "project_map_links_offerings": """
        SELECT COUNT(*)
        FROM app_project_offering_map pom
        INNER JOIN core_vendor_offering o ON pom.offering_id = o.offering_id
    """,
    "project_demo_links": """
        SELECT COUNT(*)
        FROM app_project_demo pd
        LEFT JOIN app_project p ON pd.project_id = p.project_id
        LEFT JOIN core_vendor v ON pd.vendor_id = v.vendor_id
        WHERE p.project_id IS NOT NULL AND v.vendor_id IS NOT NULL
    """,
}


def _scalar(conn: sqlite3.Connection, query: str) -> int:
    row = conn.execute(query).fetchone()
    return int(row[0]) if row else 0


def verify(db_path: Path, profile: str) -> list[str]:
    failures: list[str] = []

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        rules = dict(BASELINE_RULES)
        if profile == "full":
            rules.update(FULL_PROFILE_ADDITIONAL_RULES)

        for name, (query, minimum) in rules.items():
            value = _scalar(conn, query)
            if value < minimum:
                failures.append(f"{name}: expected >= {minimum}, found {value}")

        for name, query in RELATIONSHIP_RULES.items():
            value = _scalar(conn, query)
            if value <= 0:
                failures.append(f"{name}: expected linked rows, found {value}")

    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify V1 seed coverage for functional test use cases."
    )
    parser.add_argument(
        "--db-path",
        default=str(Path(__file__).resolve().parents[1] / "local_db" / "twvendor_local_v1.db"),
        help="Path to SQLite V1 database.",
    )
    parser.add_argument(
        "--profile",
        default="baseline",
        choices=("baseline", "full"),
        help="Coverage profile to validate.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    db_path = Path(args.db_path).resolve()

    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}")
        raise SystemExit(2)

    failures = verify(db_path, profile=args.profile)
    if failures:
        print("V1 seed coverage verification FAILED")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    print(f"V1 seed coverage verification PASSED ({args.profile})")
