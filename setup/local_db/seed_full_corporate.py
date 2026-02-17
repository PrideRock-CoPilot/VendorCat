from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class SeedConfig:
    vendor_count: int = 125
    employee_count: int = 260
    active_employee_count: int = 220
    project_count: int = 96
    onboarding_request_count: int = 48
    access_request_count: int = 72
    usage_event_count: int = 1200


def _as_ts(base_dt: datetime, day_offset: int, hour_offset: int = 0) -> str:
    return (base_dt + timedelta(days=day_offset, hours=hour_offset)).strftime("%Y-%m-%d %H:%M:%S")


def _as_date(base_dt: datetime, day_offset: int) -> str:
    return (base_dt + timedelta(days=day_offset)).strftime("%Y-%m-%d")


def _id_factory() -> callable:
    counters: dict[str, int] = defaultdict(int)

    def build(prefix: str) -> str:
        counters[prefix] += 1
        return f"{prefix}-{counters[prefix]:06d}"

    return build


def _cleanup_existing_corporate_rows(conn: sqlite3.Connection) -> None:
    statements: tuple[str, ...] = (
        "DELETE FROM app_project_demo WHERE project_demo_id LIKE 'pdm-corp-%'",
        "DELETE FROM app_project_note WHERE project_note_id LIKE 'pnt-corp-%'",
        "DELETE FROM app_project_offering_map WHERE project_offering_map_id LIKE 'pom-corp-%'",
        "DELETE FROM app_project_vendor_map WHERE project_vendor_map_id LIKE 'pvm-corp-%'",
        "DELETE FROM app_project WHERE project_id LIKE 'prj-corp-%'",
        "DELETE FROM app_offering_data_flow WHERE data_flow_id LIKE 'flow-corp-%'",
        "DELETE FROM app_offering_ticket WHERE ticket_id LIKE 'tkt-corp-%'",
        "DELETE FROM app_offering_invoice WHERE invoice_id LIKE 'inv-corp-%'",
        "DELETE FROM app_offering_profile WHERE offering_id LIKE 'off-corp-%'",
        "DELETE FROM core_vendor_demo_note WHERE demo_note_id LIKE 'dmn-corp-%'",
        "DELETE FROM core_vendor_demo_score WHERE demo_score_id LIKE 'dms-corp-%'",
        "DELETE FROM core_vendor_demo WHERE demo_id LIKE 'demo-corp-%'",
        "DELETE FROM core_contract_event WHERE contract_event_id LIKE 'ce-corp-%'",
        "DELETE FROM core_contract WHERE contract_id LIKE 'ctr-corp-%'",
        "DELETE FROM core_offering_contact WHERE offering_contact_id LIKE 'ocon-corp-%'",
        "DELETE FROM core_offering_business_owner WHERE offering_owner_id LIKE 'oown-corp-%'",
        "DELETE FROM core_vendor_offering WHERE offering_id LIKE 'off-corp-%'",
        "DELETE FROM core_vendor_business_owner WHERE vendor_owner_id LIKE 'vown-corp-%'",
        "DELETE FROM core_vendor_org_assignment WHERE vendor_org_assignment_id LIKE 'voa-corp-%'",
        "DELETE FROM core_vendor_contact WHERE vendor_contact_id LIKE 'vcon-corp-%'",
        "DELETE FROM core_vendor_identifier WHERE vendor_identifier_id LIKE 'vid-corp-%'",
        "DELETE FROM core_vendor WHERE vendor_id LIKE 'vnd-corp-%'",
        "DELETE FROM app_document_link WHERE doc_id LIKE 'doc-corp-%'",
        "DELETE FROM app_note WHERE note_id LIKE 'note-corp-%'",
        "DELETE FROM app_vendor_change_request WHERE change_request_id LIKE 'cr-corp-%'",
        "DELETE FROM app_onboarding_approval WHERE approval_id LIKE 'apr-corp-%'",
        "DELETE FROM app_onboarding_task WHERE task_id LIKE 'task-corp-%'",
        "DELETE FROM app_onboarding_request WHERE request_id LIKE 'onb-corp-%'",
        "DELETE FROM app_access_request WHERE access_request_id LIKE 'ar-corp-%'",
        "DELETE FROM app_usage_log WHERE usage_event_id LIKE 'use-corp-%'",
        "DELETE FROM app_user_settings WHERE setting_id LIKE 'set-corp-%'",
        "DELETE FROM audit_entity_change WHERE change_event_id LIKE 'ae-corp-%'",
        "DELETE FROM audit_workflow_event WHERE workflow_event_id LIKE 'awf-corp-%'",
        "DELETE FROM audit_access_event WHERE access_event_id LIKE 'aac-corp-%'",
        "DELETE FROM change_event WHERE request_id LIKE 'cr-corp-%'",
        "DELETE FROM change_request WHERE request_id LIKE 'cr-corp-%'",
        "DELETE FROM hist_contract WHERE contract_hist_id LIKE 'hctr-corp-%'",
        "DELETE FROM hist_vendor_offering WHERE vendor_offering_hist_id LIKE 'hoff-corp-%'",
        "DELETE FROM hist_vendor WHERE vendor_hist_id LIKE 'hvend-corp-%'",
        "DELETE FROM src_peoplesoft_vendor_raw WHERE batch_id LIKE 'b-corp-%'",
        "DELETE FROM src_zycus_vendor_raw WHERE batch_id LIKE 'b-corp-%'",
        "DELETE FROM src_spreadsheet_vendor_raw WHERE batch_id LIKE 'b-corp-%'",
        "DELETE FROM src_ingest_batch WHERE batch_id LIKE 'b-corp-%'",
        "DELETE FROM sec_user_org_scope WHERE user_principal LIKE 'emp%@example.com'",
        "DELETE FROM sec_user_role_map WHERE user_principal LIKE 'emp%@example.com'",
        "DELETE FROM sec_group_role_map WHERE group_principal LIKE 'group:corp_%'",
        "DELETE FROM app_user_directory WHERE user_id LIKE 'usr-corp-%'",
        "DELETE FROM app_employee_directory WHERE login_identifier LIKE 'emp%@example.com'",
        "DELETE FROM vendor_help_feedback WHERE feedback_id LIKE 'hfb-corp-%'",
        "DELETE FROM vendor_help_issue WHERE issue_id LIKE 'his-corp-%'",
    )
    for statement in statements:
        conn.execute(statement)


def seed_full_corporate(conn: sqlite3.Connection, config: SeedConfig | None = None) -> dict[str, int]:
    cfg = config or SeedConfig()
    base_dt = datetime(2026, 2, 14, 9, 0, 0)
    make_id = _id_factory()
    actor = "seed:corp"

    conn.execute("PRAGMA foreign_keys = ON")
    _cleanup_existing_corporate_rows(conn)

    org_ids = ("IT-ENT", "FIN-AP", "HR-OPS", "SEC-OPS", "SALES-OPS", "MKT-OPS", "CLIN-OPS", "SUPPLY")
    lifecycle_states = ("active", "active", "active", "in_review", "approved", "retired")
    risk_tiers = ("low", "medium", "high", "critical")
    offering_types = ("SaaS", "Cloud", "Security", "Data", "PaaS", "Integration")
    lob_values = ("Enterprise", "Finance", "HR", "IT", "Operations", "Sales", "Security")
    service_types = ("Application", "Infrastructure", "Integration", "Managed Service", "Platform", "Security")
    contract_statuses = ("active", "active", "active", "pending_renewal", "active", "expired")
    project_statuses = ("active", "planning", "blocked", "completed", "active", "active")
    project_types = ("implementation", "poc", "renewal", "rfp", "other")
    demo_outcomes = ("selected", "not_selected", "deferred")
    access_statuses = ("pending", "approved", "rejected", "pending", "approved")
    onboarding_statuses = ("submitted", "in_review", "pending_approval", "approved", "rejected")

    batch_rows = [
        (f"b-corp-202602-{index:02d}", source, "vendor", _as_ts(base_dt, -15 + index), _as_ts(base_dt, -15 + index, 1), 0, "loaded")
        for index, source in enumerate(("PeopleSoft", "Zycus", "Spreadsheet"), start=1)
    ]
    conn.executemany(
        """
        INSERT INTO src_ingest_batch
          (batch_id, source_system, source_object, extract_ts, loaded_ts, row_count, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        batch_rows,
    )

    employee_rows: list[tuple] = []
    user_directory_rows: list[tuple] = []
    for idx in range(1, cfg.employee_count + 1):
        login = f"emp{idx:03d}@example.com"
        first = f"Emp{idx:03d}"
        last = "User"
        display = f"{first} {last}"
        employee_id = f"E{2000 + idx:04d}"
        manager_num = 2001 if idx <= 8 else 2000 + max(1, ((idx - 1) // 8))
        manager_id = f"E{manager_num:04d}"
        active_flag = 1 if idx <= cfg.active_employee_count else 0
        employee_rows.append(
            (
                login,
                login,
                f"emp{idx:03d}",
                employee_id,
                manager_id,
                first,
                last,
                display,
                active_flag,
            )
        )
        user_directory_rows.append(
            (
                f"usr-corp-{idx:03d}",
                login,
                login,
                f"emp{idx:03d}",
                employee_id,
                manager_id,
                first,
                last,
                display,
                active_flag,
                _as_ts(base_dt, -60 + (idx % 20)),
                _as_ts(base_dt, -(idx % 7)),
                _as_ts(base_dt, -(idx % 3)),
            )
        )

    conn.executemany(
        """
        INSERT INTO app_employee_directory
          (login_identifier, email, network_id, employee_id, manager_id, first_name, last_name, display_name, active_flag)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        employee_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_user_directory
          (user_id, login_identifier, email, network_id, employee_id, manager_id, first_name, last_name, display_name, active_flag, created_at, updated_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        user_directory_rows,
    )

    role_rows: list[tuple] = []
    scope_rows: list[tuple] = []
    role_choices = ("vendor_admin", "vendor_steward", "vendor_editor", "vendor_viewer", "vendor_auditor")
    for idx in range(1, min(cfg.active_employee_count, 160) + 1):
        login = f"emp{idx:03d}@example.com"
        role = role_choices[(idx - 1) % len(role_choices)]
        role_rows.append((login, role, 1, "admin@example.com", _as_ts(base_dt, -45 + (idx % 20)), None))
        scope_rows.append((login, org_ids[idx % len(org_ids)], "full" if idx % 6 == 0 else "edit", 1, _as_ts(base_dt, -30 + (idx % 10))))

    conn.executemany(
        """
        INSERT INTO sec_user_role_map
          (user_principal, role_code, active_flag, granted_by, granted_at, revoked_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        role_rows,
    )
    conn.executemany(
        """
        INSERT INTO sec_user_org_scope
          (user_principal, org_id, scope_level, active_flag, granted_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        scope_rows,
    )
    conn.executemany(
        """
        INSERT INTO sec_group_role_map
          (group_principal, role_code, active_flag, granted_by, granted_at, revoked_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("group:corp_procurement", "vendor_steward", 1, "admin@example.com", _as_ts(base_dt, -40), None),
            ("group:corp_it_operations", "vendor_editor", 1, "admin@example.com", _as_ts(base_dt, -38), None),
            ("group:corp_security", "vendor_auditor", 1, "admin@example.com", _as_ts(base_dt, -37), None),
            ("group:corp_finance", "vendor_viewer", 1, "admin@example.com", _as_ts(base_dt, -35), None),
            ("group:corp_admin", "vendor_admin", 1, "admin@example.com", _as_ts(base_dt, -34), None),
        ],
    )

    vendor_rows: list[tuple] = []
    vendor_identifier_rows: list[tuple] = []
    vendor_contact_rows: list[tuple] = []
    vendor_assignment_rows: list[tuple] = []
    vendor_owner_rows: list[tuple] = []
    source_ps_rows: list[tuple] = []
    source_zy_rows: list[tuple] = []
    source_sheet_rows: list[tuple] = []

    offering_rows: list[tuple] = []
    offering_owner_rows: list[tuple] = []
    offering_contact_rows: list[tuple] = []
    offering_profile_rows: list[tuple] = []
    offering_flow_rows: list[tuple] = []
    offering_ticket_rows: list[tuple] = []
    offering_invoice_rows: list[tuple] = []

    contract_rows: list[tuple] = []
    contract_event_rows: list[tuple] = []

    demo_rows: list[tuple] = []
    demo_score_rows: list[tuple] = []
    demo_note_rows: list[tuple] = []

    hist_vendor_rows: list[tuple] = []
    hist_offering_rows: list[tuple] = []
    hist_contract_rows: list[tuple] = []

    doc_rows: list[tuple] = []
    app_note_rows: list[tuple] = []
    change_request_rows: list[tuple] = []
    audit_change_rows: list[tuple] = []

    offering_ids_by_vendor: dict[int, list[str]] = {}
    demo_id_by_vendor: dict[int, str] = {}
    for idx in range(1, cfg.vendor_count + 1):
        vendor_id = f"vnd-corp-{idx:03d}"
        legal_name = f"Corporate Vendor {idx:03d} Holdings, LLC"
        display_name = f"Vendor {idx:03d}"
        lifecycle_state = lifecycle_states[idx % len(lifecycle_states)]
        owner_org_id = org_ids[idx % len(org_ids)]
        risk_tier = risk_tiers[idx % len(risk_tiers)]
        source_system = ("PeopleSoft", "Zycus", "Spreadsheet")[idx % 3]
        source_batch_id = f"b-corp-202602-{(idx % 3) + 1:02d}"
        source_record_id = f"{source_system[:2].lower()}-corp-{idx:04d}"
        source_extract_ts = _as_ts(base_dt, -20 + (idx % 15))
        updated_at = _as_ts(base_dt, -(idx % 10))
        updated_by = actor

        vendor_rows.append(
            (
                vendor_id,
                legal_name,
                display_name,
                lifecycle_state,
                owner_org_id,
                risk_tier,
                source_system,
                source_record_id,
                source_batch_id,
                source_extract_ts,
                updated_at,
                updated_by,
            )
        )
        vendor_identifier_rows.extend(
            [
                (f"vid-corp-{idx:03d}-a", vendor_id, "duns", f"{720000000 + idx}", 1, "US", updated_at, updated_by),
                (f"vid-corp-{idx:03d}-b", vendor_id, "erp_id", f"ERP-{idx:05d}", 0, "US", updated_at, updated_by),
            ]
        )
        vendor_contact_rows.extend(
            [
                (f"vcon-corp-{idx:03d}-a", vendor_id, "business", f"Business Contact {idx:03d}", f"vendor{idx:03d}.business@example.com", f"555-{1000 + idx:04d}", 1, updated_at, updated_by),
                (f"vcon-corp-{idx:03d}-b", vendor_id, "support", f"Support Contact {idx:03d}", f"vendor{idx:03d}.support@example.com", f"555-{4000 + idx:04d}", 1, updated_at, updated_by),
            ]
        )
        vendor_assignment_rows.append((f"voa-corp-{idx:03d}-a", vendor_id, owner_org_id, "primary", 1, updated_at, updated_by))
        if idx % 2 == 0:
            vendor_assignment_rows.append((f"voa-corp-{idx:03d}-b", vendor_id, org_ids[(idx + 1) % len(org_ids)], "consumer", 1, updated_at, updated_by))

        owner_login = f"emp{((idx * 3) % cfg.active_employee_count) + 1:03d}@example.com"
        vendor_owner_rows.append((f"vown-corp-{idx:03d}-a", vendor_id, owner_login, "business_owner", 1, updated_at, updated_by))

        if source_system == "PeopleSoft":
            source_ps_rows.append((source_batch_id, source_record_id, source_extract_ts, json.dumps({"vendor_name": legal_name, "vendor_id": vendor_id}), updated_at))
        elif source_system == "Zycus":
            source_zy_rows.append((source_batch_id, source_record_id, source_extract_ts, json.dumps({"vendor_name": legal_name, "vendor_id": vendor_id}), updated_at))
        else:
            source_sheet_rows.append((source_batch_id, source_record_id, source_extract_ts, f"corp_vendor_import_{(idx % 4) + 1}.xlsx", json.dumps({"vendor_name": legal_name, "vendor_id": vendor_id}), updated_at))

        offerings_for_vendor = 1 if idx % 7 == 0 else 2 if idx % 5 == 0 else 3
        offering_ids: list[str] = []
        for off_idx in range(1, offerings_for_vendor + 1):
            offering_id = f"off-corp-{idx:03d}-{off_idx:02d}"
            offering_ids.append(offering_id)
            offering_type = offering_types[(idx + off_idx) % len(offering_types)]
            lob = lob_values[(idx + (off_idx * 2)) % len(lob_values)]
            service_type = service_types[(idx + off_idx) % len(service_types)]
            offering_state = ("active", "active", "approved", "in_review", "retired")[(idx + off_idx) % 5]
            criticality = ("tier_1", "tier_2", "tier_3")[(idx + off_idx) % 3]
            offering_rows.append(
                (
                    offering_id,
                    vendor_id,
                    f"{display_name} Service {off_idx}",
                    offering_type,
                    lob,
                    service_type,
                    offering_state,
                    criticality,
                    updated_at,
                    updated_by,
                )
            )
            owner_login = f"emp{((idx * 5 + off_idx) % cfg.active_employee_count) + 1:03d}@example.com"
            offering_owner_rows.append((f"oown-corp-{idx:03d}-{off_idx:02d}", offering_id, owner_login, "service_owner", 1, updated_at, updated_by))
            offering_contact_rows.append((f"ocon-corp-{idx:03d}-{off_idx:02d}", offering_id, "support", f"{display_name} Service {off_idx} Support", f"svc{idx:03d}{off_idx:02d}@example.com", f"555-{6000 + idx + off_idx:04d}", 1, updated_at, updated_by))
            estimated_monthly_cost = float(2200 + (idx * 95) + (off_idx * 140))
            offering_profile_rows.append(
                (
                    offering_id,
                    vendor_id,
                    estimated_monthly_cost,
                    f"Implementation runbook for {offering_id}",
                    "usage_metrics, events",
                    "status_updates, invoice_data",
                    ("api", "sftp", "manual")[off_idx % 3],
                    "api",
                    "raw_zone",
                    "vendor_account_id, contract_number",
                    "rpt_vendor_360",
                    "Nightly ingest schedule",
                    "api",
                    "Service request workflow",
                    "Published through secured API",
                    owner_login,
                    "Standardized integration profile",
                    updated_at,
                    updated_by,
                )
            )
            offering_flow_rows.extend(
                [
                    (
                        f"flow-corp-{idx:03d}-{off_idx:02d}-in",
                        offering_id,
                        vendor_id,
                        "inbound",
                        f"{offering_id} inbound",
                        "api",
                        "Inbound transaction payload",
                        f"https://api.vendor{idx:03d}.example.com/inbound",
                        "transaction_id, source_id",
                        "rpt_vendor_360",
                        None,
                        None,
                        owner_login,
                        "Validated by integration team",
                        1,
                        updated_at,
                        updated_by,
                        updated_at,
                        updated_by,
                    ),
                    (
                        f"flow-corp-{idx:03d}-{off_idx:02d}-out",
                        offering_id,
                        vendor_id,
                        "outbound",
                        f"{offering_id} outbound",
                        "sftp",
                        "Outbound reconciliation file",
                        f"sftp://vendor{idx:03d}.example.com/outbound",
                        "batch_id, file_id",
                        "rpt_contract_cancellations",
                        "Generated by scheduled workflow",
                        "Secure transfer to vendor",
                        owner_login,
                        "Produced weekly",
                        1,
                        updated_at,
                        updated_by,
                        updated_at,
                        updated_by,
                    ),
                ]
            )
            offering_ticket_rows.append(
                (
                    f"tkt-corp-{idx:03d}-{off_idx:02d}",
                    offering_id,
                    vendor_id,
                    "ServiceNow",
                    f"INC{idx:03d}{off_idx:02d}",
                    f"{offering_id} onboarding ticket",
                    ("open", "in_progress", "resolved")[(idx + off_idx) % 3],
                    ("high", "medium", "low")[(idx + off_idx) % 3],
                    _as_date(base_dt, -35 + ((idx + off_idx) % 20)),
                    _as_date(base_dt, -2 + ((idx + off_idx) % 3)) if (idx + off_idx) % 3 == 2 else None,
                    "Tracked under service onboarding stream",
                    1,
                    updated_at,
                    updated_by,
                    updated_at,
                    updated_by,
                )
            )
            offering_invoice_rows.append(
                (
                    f"inv-corp-{idx:03d}-{off_idx:02d}",
                    offering_id,
                    vendor_id,
                    f"INV-{idx:03d}-{off_idx:02d}",
                    _as_date(base_dt, -28 + ((idx + off_idx) % 18)),
                    round(estimated_monthly_cost * (1.0 + (off_idx * 0.05)), 2),
                    "USD",
                    ("paid", "pending", "approved", "disputed")[(idx + off_idx) % 4],
                    "Monthly billing statement",
                    1,
                    updated_at,
                    updated_by,
                    updated_at,
                    updated_by,
                )
            )
            hist_offering_rows.append(
                (
                    f"hoff-corp-{idx:03d}-{off_idx:02d}",
                    offering_id,
                    1,
                    _as_ts(base_dt, -120 + idx),
                    None,
                    1,
                    json.dumps({"offering_id": offering_id, "vendor_id": vendor_id, "offering_name": f"{display_name} Service {off_idx}", "lifecycle_state": offering_state}, separators=(",", ":")),
                    actor,
                    "initial_seed",
                )
            )

        offering_ids_by_vendor[idx] = offering_ids

        vendor_contract_id = f"ctr-corp-v-{idx:03d}"
        vendor_contract_status = contract_statuses[idx % len(contract_statuses)]
        vendor_contract_cancelled = 1 if vendor_contract_status == "expired" and idx % 4 == 0 else 0
        contract_rows.append(
            (
                vendor_contract_id,
                vendor_id,
                None,
                f"VND-{idx:03d}-MASTER",
                vendor_contract_status,
                _as_date(base_dt, -500 + idx),
                _as_date(base_dt, 120 + (idx % 180)),
                vendor_contract_cancelled,
                round(350000 + (idx * 15000), 2),
                updated_at,
                updated_by,
            )
        )
        contract_event_rows.append((make_id("ce-corp"), vendor_contract_id, "renewal_planned", _as_ts(base_dt, -20 + (idx % 8)), None, "Master agreement renewal planned.", owner_login))
        if vendor_contract_cancelled:
            contract_event_rows.append((make_id("ce-corp"), vendor_contract_id, "contract_cancelled", _as_ts(base_dt, -3 + (idx % 2)), "portfolio_consolidation", "Contract closed during vendor consolidation.", owner_login))

        if offering_ids:
            offering_contract_id = f"ctr-corp-o-{idx:03d}"
            contract_rows.append(
                (
                    offering_contract_id,
                    vendor_id,
                    offering_ids[0],
                    f"OFR-{idx:03d}-01",
                    "active",
                    _as_date(base_dt, -365 + idx),
                    _as_date(base_dt, 180 + (idx % 120)),
                    0,
                    round(90000 + (idx * 2100), 2),
                    updated_at,
                    updated_by,
                )
            )
            contract_event_rows.append((make_id("ce-corp"), offering_contract_id, "renewal_negotiation", _as_ts(base_dt, -14 + (idx % 6)), None, "Negotiation in progress.", owner_login))

        if idx % 2 == 0 and offering_ids:
            demo_id = f"demo-corp-{idx:03d}"
            demo_id_by_vendor[idx] = demo_id
            outcome = demo_outcomes[idx % len(demo_outcomes)]
            reason = None
            if outcome == "not_selected":
                reason = ("cost_overrun", "insufficient_coverage", "integration_gaps")[idx % 3]
            elif outcome == "deferred":
                reason = ("roadmap_uncertain", "budget_pending", "rescope_required")[idx % 3]
            score = round(5.4 + ((idx % 10) * 0.38), 2)
            demo_rows.append((demo_id, vendor_id, offering_ids[0], _as_date(base_dt, -45 + (idx % 30)), score, outcome, reason, f"Corporate evaluation outcome: {outcome}.", updated_at, updated_by))
            demo_score_rows.extend(
                [
                    (make_id("dms-corp"), demo_id, "security", round(max(1.0, score - 0.4), 2), 0.35, "Security rubric score"),
                    (make_id("dms-corp"), demo_id, "integration", round(min(10.0, score + 0.2), 2), 0.35, "Integration rubric score"),
                    (make_id("dms-corp"), demo_id, "cost", round(max(1.0, score - 0.7), 2), 0.30, "Cost rubric score"),
                ]
            )
            demo_note_rows.append((make_id("dmn-corp"), demo_id, "evaluation_summary", "Cross-functional demo review completed.", updated_at, owner_login))

        hist_vendor_rows.append(
            (
                f"hvend-corp-{idx:03d}",
                vendor_id,
                1,
                _as_ts(base_dt, -180 + idx),
                None,
                1,
                json.dumps({"vendor_id": vendor_id, "display_name": display_name, "lifecycle_state": lifecycle_state, "risk_tier": risk_tier}, separators=(",", ":")),
                actor,
                "initial_seed",
            )
        )
        doc_rows.append((f"doc-corp-v-{idx:03d}", "vendor", vendor_id, f"{display_name} governance packet", f"https://contoso.sharepoint.com/sites/vendor-catalog/{vendor_id}/governance-packet.pdf", "sharepoint", "contract,operations,compliance", owner_login, 1, updated_at, actor, updated_at, actor))
        app_note_rows.append((f"note-corp-v-{idx:03d}", "vendor", vendor_id, "governance_note", "Annual compliance and SLA review logged for enterprise validation.", updated_at, owner_login))
        change_request_rows.append((f"cr-corp-{idx:03d}", vendor_id, owner_login, ("update_vendor_profile", "update_contact", "request_lifecycle_change")[idx % 3], json.dumps({"vendor_id": vendor_id, "risk_tier": risk_tier, "request_batch": "corp_seed"}, separators=(",", ":")), ("submitted", "pending_approval", "approved", "rejected")[idx % 4], _as_ts(base_dt, -20 + (idx % 10)), _as_ts(base_dt, -10 + (idx % 8))))
        audit_change_rows.append((make_id("ae-corp"), "core_vendor", vendor_id, "update", None, json.dumps({"risk_tier": risk_tier}, separators=(",", ":")), owner_login, _as_ts(base_dt, -6 + (idx % 5)), f"cr-corp-{idx:03d}"))

    conn.executemany(
        """
        INSERT INTO core_vendor
          (vendor_id, legal_name, display_name, lifecycle_state, owner_org_id, risk_tier, source_system, source_record_id, source_batch_id, source_extract_ts, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        vendor_rows,
    )
    conn.executemany(
        """
        INSERT INTO core_vendor_identifier
          (vendor_identifier_id, vendor_id, identifier_type, identifier_value, is_primary, country_code, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        vendor_identifier_rows,
    )
    conn.executemany(
        """
        INSERT INTO core_vendor_contact
          (vendor_contact_id, vendor_id, contact_type, full_name, email, phone, active_flag, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        vendor_contact_rows,
    )
    conn.executemany(
        """
        INSERT INTO core_vendor_org_assignment
          (vendor_org_assignment_id, vendor_id, org_id, assignment_type, active_flag, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        vendor_assignment_rows,
    )
    conn.executemany(
        """
        INSERT INTO core_vendor_business_owner
          (vendor_owner_id, vendor_id, owner_user_principal, owner_role, active_flag, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        vendor_owner_rows,
    )
    conn.executemany(
        """
        INSERT INTO src_peoplesoft_vendor_raw
          (batch_id, source_record_id, source_extract_ts, payload_json, ingested_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        source_ps_rows,
    )
    conn.executemany(
        """
        INSERT INTO src_zycus_vendor_raw
          (batch_id, source_record_id, source_extract_ts, payload_json, ingested_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        source_zy_rows,
    )
    conn.executemany(
        """
        INSERT INTO src_spreadsheet_vendor_raw
          (batch_id, source_record_id, source_extract_ts, file_name, payload_json, ingested_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        source_sheet_rows,
    )
    conn.executemany(
        """
        INSERT INTO core_vendor_offering
          (offering_id, vendor_id, offering_name, offering_type, lob, service_type, lifecycle_state, criticality_tier, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        offering_rows,
    )
    conn.executemany(
        """
        INSERT INTO core_offering_business_owner
          (offering_owner_id, offering_id, owner_user_principal, owner_role, active_flag, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        offering_owner_rows,
    )
    conn.executemany(
        """
        INSERT INTO core_offering_contact
          (offering_contact_id, offering_id, contact_type, full_name, email, phone, active_flag, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        offering_contact_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_offering_profile
          (offering_id, vendor_id, estimated_monthly_cost, implementation_notes, data_sent, data_received, integration_method, inbound_method, inbound_landing_zone, inbound_identifiers, inbound_reporting_layer, inbound_ingestion_notes, outbound_method, outbound_creation_process, outbound_delivery_process, outbound_responsible_owner, outbound_notes, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        offering_profile_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_offering_data_flow
          (data_flow_id, offering_id, vendor_id, direction, flow_name, method, data_description, endpoint_details, identifiers, reporting_layer, creation_process, delivery_process, owner_user_principal, notes, active_flag, created_at, created_by, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        offering_flow_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_offering_ticket
          (ticket_id, offering_id, vendor_id, ticket_system, external_ticket_id, title, status, priority, opened_date, closed_date, notes, active_flag, created_at, created_by, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        offering_ticket_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_offering_invoice
          (invoice_id, offering_id, vendor_id, invoice_number, invoice_date, amount, currency_code, invoice_status, notes, active_flag, created_at, created_by, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        offering_invoice_rows,
    )
    conn.executemany(
        """
        INSERT INTO core_contract
          (contract_id, vendor_id, offering_id, contract_number, contract_status, start_date, end_date, cancelled_flag, annual_value, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        contract_rows,
    )
    conn.executemany(
        """
        INSERT INTO core_contract_event
          (contract_event_id, contract_id, event_type, event_ts, reason_code, notes, actor_user_principal)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        contract_event_rows,
    )
    for row in contract_rows:
        contract_id = row[0]
        hist_contract_rows.append(
            (
                f"hctr-corp-{contract_id}",
                contract_id,
                1,
                _as_ts(base_dt, -150),
                None,
                1,
                json.dumps({"contract_id": contract_id, "status": row[4], "annual_value": row[8]}, separators=(",", ":")),
                actor,
                "initial_seed",
            )
        )
    conn.executemany(
        """
        INSERT INTO core_vendor_demo
          (demo_id, vendor_id, offering_id, demo_date, overall_score, selection_outcome, non_selection_reason_code, notes, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        demo_rows,
    )
    conn.executemany(
        """
        INSERT INTO core_vendor_demo_score
          (demo_score_id, demo_id, score_category, score_value, weight, comments)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        demo_score_rows,
    )
    conn.executemany(
        """
        INSERT INTO core_vendor_demo_note
          (demo_note_id, demo_id, note_type, note_text, created_at, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        demo_note_rows,
    )
    conn.executemany(
        """
        INSERT INTO hist_vendor
          (vendor_hist_id, vendor_id, version_no, valid_from_ts, valid_to_ts, is_current, snapshot_json, changed_by, change_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        hist_vendor_rows,
    )
    conn.executemany(
        """
        INSERT INTO hist_vendor_offering
          (vendor_offering_hist_id, offering_id, version_no, valid_from_ts, valid_to_ts, is_current, snapshot_json, changed_by, change_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        hist_offering_rows,
    )
    conn.executemany(
        """
        INSERT INTO hist_contract
          (contract_hist_id, contract_id, version_no, valid_from_ts, valid_to_ts, is_current, snapshot_json, changed_by, change_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        hist_contract_rows,
    )

    project_rows: list[tuple] = []
    project_vendor_map_rows: list[tuple] = []
    project_offering_map_rows: list[tuple] = []
    project_demo_rows: list[tuple] = []
    project_note_rows: list[tuple] = []
    workflow_event_rows: list[tuple] = []
    access_event_rows: list[tuple] = []
    for idx in range(1, cfg.project_count + 1):
        vendor_num = ((idx - 1) % cfg.vendor_count) + 1
        vendor_id = f"vnd-corp-{vendor_num:03d}"
        offering_ids = offering_ids_by_vendor[vendor_num]
        offering_id = offering_ids[0]
        owner_login = f"emp{((idx * 7) % cfg.active_employee_count) + 1:03d}@example.com"
        project_id = f"prj-corp-{idx:03d}"
        created_at = _as_ts(base_dt, -80 + (idx % 20))
        updated_at = _as_ts(base_dt, -15 + (idx % 10))
        status = project_statuses[idx % len(project_statuses)]
        project_rows.append((project_id, vendor_id, f"Enterprise Initiative {idx:03d}", project_types[idx % len(project_types)], status, _as_date(base_dt, -90 + idx), _as_date(base_dt, 60 + (idx % 160)), owner_login, f"Corporate scale project {idx:03d} for vendor modernization.", 1, created_at, owner_login, updated_at, owner_login))
        project_vendor_map_rows.append((f"pvm-corp-{idx:03d}", project_id, vendor_id, 1, created_at, owner_login, updated_at, owner_login))
        project_offering_map_rows.append((f"pom-corp-{idx:03d}", project_id, vendor_id, offering_id, 1, created_at, owner_login, updated_at, owner_login))
        project_note_rows.append((f"pnt-corp-{idx:03d}", project_id, vendor_id, "Project cadence and risk notes captured for enterprise review.", 1, updated_at, owner_login, updated_at, owner_login))
        if idx % 2 == 0:
            linked_demo = demo_id_by_vendor.get(vendor_num)
            project_demo_rows.append((f"pdm-corp-{idx:03d}", project_id, vendor_id, f"Project Demo {idx:03d}", _as_ts(base_dt, -10 + (idx % 6), idx % 8), _as_ts(base_dt, -10 + (idx % 6), (idx % 8) + 1), ("demo", "workshop", "review")[idx % 3], ("follow_up", "approved", "deferred")[idx % 3], round(6.2 + ((idx % 9) * 0.35), 2), "IT, Procurement, Security", "Vendor team, account manager", "Enterprise readiness discussion completed.", "Follow-up actions tracked in workflow queue.", offering_id, linked_demo, 1, updated_at, owner_login, updated_at, owner_login))
        workflow_event_rows.append((make_id("awf-corp"), "project", project_id, "queued", status, owner_login, updated_at, "Project workflow state refreshed."))
        access_event_rows.append((make_id("aac-corp"), "admin@example.com", "grant_role", owner_login, role_choices[idx % len(role_choices)], updated_at, "Corporate seed role assignment"))

    conn.executemany(
        """
        INSERT INTO app_project
          (project_id, vendor_id, project_name, project_type, status, start_date, target_date, owner_principal, description, active_flag, created_at, created_by, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        project_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_project_vendor_map
          (project_vendor_map_id, project_id, vendor_id, active_flag, created_at, created_by, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        project_vendor_map_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_project_offering_map
          (project_offering_map_id, project_id, vendor_id, offering_id, active_flag, created_at, created_by, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        project_offering_map_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_project_demo
          (project_demo_id, project_id, vendor_id, demo_name, demo_datetime_start, demo_datetime_end, demo_type, outcome, score, attendees_internal, attendees_vendor, notes, followups, linked_offering_id, linked_vendor_demo_id, active_flag, created_at, created_by, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        project_demo_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_project_note
          (project_note_id, project_id, vendor_id, note_text, active_flag, created_at, created_by, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        project_note_rows,
    )

    onboarding_rows: list[tuple] = []
    onboarding_task_rows: list[tuple] = []
    onboarding_approval_rows: list[tuple] = []
    access_request_rows: list[tuple] = []
    user_settings_rows: list[tuple] = []
    for idx in range(1, cfg.onboarding_request_count + 1):
        requester = f"emp{((idx * 3) % cfg.active_employee_count) + 1:03d}@example.com"
        request_id = f"onb-corp-{idx:03d}"
        status = onboarding_statuses[idx % len(onboarding_statuses)]
        submitted_at = _as_ts(base_dt, -25 + (idx % 12))
        updated_at = _as_ts(base_dt, -8 + (idx % 6))
        onboarding_rows.append((request_id, requester, f"New Vendor Candidate {idx:03d}", ("low", "medium", "high")[idx % 3], status, submitted_at, updated_at))
        onboarding_task_rows.append((f"task-corp-{idx:03d}", request_id, ("validation", "risk_review", "legal_review")[idx % 3], ("group:corp_procurement", "group:corp_security", "group:corp_finance")[idx % 3], _as_ts(base_dt, 2 + (idx % 8)), ("open", "in_progress", "done")[idx % 3], updated_at, requester))
        onboarding_approval_rows.append((f"apr-corp-{idx:03d}", request_id, ("security", "legal", "finance")[idx % 3], f"emp{((idx * 5) % cfg.active_employee_count) + 1:03d}@example.com", ("approved", "pending", "rejected")[idx % 3], _as_ts(base_dt, -4 + (idx % 4)) if idx % 3 != 1 else None, "Corporate approval stage note.", updated_at))
        workflow_event_rows.append((make_id("awf-corp"), "onboarding_request", request_id, "submitted", status, requester, updated_at, "Onboarding request workflow transition"))

    for idx in range(1, cfg.access_request_count + 1):
        requester = f"emp{((idx * 9) % cfg.active_employee_count) + 1:03d}@example.com"
        status = access_statuses[idx % len(access_statuses)]
        submitted_at = _as_ts(base_dt, -18 + (idx % 7))
        updated_at = _as_ts(base_dt, -2 + (idx % 3))
        requested_role = role_choices[idx % len(role_choices)]
        access_request_rows.append((f"ar-corp-{idx:03d}", requester, requested_role, f"Role request for enterprise function {idx:03d}.", status, submitted_at, updated_at))
        workflow_event_rows.append((make_id("awf-corp"), "access_request", f"ar-corp-{idx:03d}", "submitted", status, requester, updated_at, "Access request workflow transition"))

    for idx in range(1, 81):
        principal = f"emp{idx:03d}@example.com"
        user_settings_rows.append(
            (
                f"set-corp-{idx:03d}",
                principal,
                "vendor360_list",
                json.dumps(
                    {
                        "filters": {"lifecycle_state": "active"},
                        "visible_fields": ["display_name", "lifecycle_state", "owner_org_id", "risk_tier"],
                        "sort_by": "display_name",
                        "sort_dir": "asc",
                    },
                    separators=(",", ":"),
                ),
                _as_ts(base_dt, -5 + (idx % 3)),
                principal,
            )
        )

    conn.executemany(
        """
        INSERT INTO app_onboarding_request
          (request_id, requestor_user_principal, vendor_name_raw, priority, status, submitted_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        onboarding_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_onboarding_task
          (task_id, request_id, task_type, assignee_group, due_at, status, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        onboarding_task_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_onboarding_approval
          (approval_id, request_id, stage_name, approver_user_principal, decision, decided_at, comments, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        onboarding_approval_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_access_request
          (access_request_id, requester_user_principal, requested_role, justification, status, submitted_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        access_request_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_user_settings
          (setting_id, user_principal, setting_key, setting_value_json, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        user_settings_rows,
    )

    for idx in range(1, min(cfg.vendor_count, 70) + 1):
        offering_id = offering_ids_by_vendor[idx][0]
        owner_login = f"emp{((idx * 11) % cfg.active_employee_count) + 1:03d}@example.com"
        doc_rows.append((f"doc-corp-o-{idx:03d}", "offering", offering_id, f"{offering_id} integration guide", f"https://example.atlassian.net/wiki/spaces/VC/pages/{5000 + idx}/{offering_id}", "confluence", "integration,runbook,operations", owner_login, 1, _as_ts(base_dt, -12 + (idx % 5)), actor, _as_ts(base_dt, -12 + (idx % 5)), actor))
        app_note_rows.append((f"note-corp-p-{idx:03d}", "project", f"prj-corp-{idx:03d}", "status_note", "Program increment status captured for steering review.", _as_ts(base_dt, -9 + (idx % 4)), owner_login))

    usage_rows: list[tuple] = []
    pages = ("Dashboard", "Vendor 360", "Projects", "Contracts", "Demos", "Reports", "Admin")
    for idx in range(1, cfg.usage_event_count + 1):
        principal = f"emp{((idx * 13) % cfg.active_employee_count) + 1:03d}@example.com"
        page_name = pages[idx % len(pages)]
        usage_rows.append((f"use-corp-{idx:05d}", principal, page_name, "page_view" if idx % 5 else "action", _as_ts(base_dt, -(idx % 14), idx % 23), json.dumps({"event_index": idx, "page": page_name.lower().replace(" ", "_")}, separators=(",", ":"))))

    conn.executemany(
        """
        INSERT INTO app_document_link
          (doc_id, entity_type, entity_id, doc_title, doc_url, doc_type, tags, owner, active_flag, created_at, created_by, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        doc_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_note
          (note_id, entity_name, entity_id, note_type, note_text, created_at, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        app_note_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_vendor_change_request
          (change_request_id, vendor_id, requestor_user_principal, change_type, requested_payload_json, status, submitted_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        change_request_rows,
    )
    change_request_v1_rows = [
        (
            row[0],
            "vendor",
            row[1],
            row[3],
            row[4],
            row[5],
            row[6],
            row[2],
        )
        for row in change_request_rows
    ]
    conn.executemany(
        """
        INSERT INTO change_request
          (request_id, entity_type, entity_id, change_type, payload_json, request_status, created_at, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        change_request_v1_rows,
    )
    conn.executemany(
        """
        INSERT INTO audit_entity_change
          (change_event_id, entity_name, entity_id, action_type, before_json, after_json, actor_user_principal, event_ts, request_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        audit_change_rows,
    )
    conn.executemany(
        """
        INSERT INTO audit_workflow_event
          (workflow_event_id, workflow_type, workflow_id, old_status, new_status, actor_user_principal, event_ts, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        workflow_event_rows,
    )
    conn.executemany(
        """
        INSERT INTO audit_access_event
          (access_event_id, actor_user_principal, action_type, target_user_principal, target_role, event_ts, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        access_event_rows,
    )
    conn.executemany(
        """
        INSERT INTO app_usage_log
          (usage_event_id, user_principal, page_name, event_type, event_ts, payload_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        usage_rows,
    )

    help_feedback_rows = [
        (
            "hfb-corp-000001",
            "help-003",
            "add-vendor",
            1,
            "Clear steps and good example.",
            "emp005@example.com",
            "/help/add-vendor",
            _as_ts(base_dt, -2),
        ),
        (
            "hfb-corp-000002",
            "help-013",
            "add-document-link",
            0,
            "Need a note about owner field.",
            "emp021@example.com",
            "/help/add-document-link",
            _as_ts(base_dt, -1),
        ),
    ]
    conn.executemany(
        """
        INSERT INTO vendor_help_feedback
          (feedback_id, article_id, article_slug, was_helpful, comment, user_principal, page_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        help_feedback_rows,
    )

    help_issue_rows = [
        (
            "his-corp-000001",
            "help-008",
            "create-project",
            "Update owner example",
            "Owner example should use a real email address format.",
            "/help/create-project",
            "emp017@example.com",
            _as_ts(base_dt, -1, 2),
        )
    ]
    conn.executemany(
        """
        INSERT INTO vendor_help_issue
          (issue_id, article_id, article_slug, issue_title, issue_description, page_path, user_principal, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        help_issue_rows,
    )

    table_rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    table_names = [str(row[0]) for row in table_rows]
    empty_tables: list[str] = []
    row_counts: dict[str, int] = {}
    for table_name in table_names:
        count = int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
        row_counts[table_name] = count
        if count == 0:
            empty_tables.append(table_name)
    if empty_tables:
        print("Warning: full corporate seed left empty tables: " + ", ".join(empty_tables))
    return row_counts
