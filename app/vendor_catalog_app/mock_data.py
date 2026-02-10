from __future__ import annotations

import pandas as pd


def vendors() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "vendor_id": "vnd-001",
                "legal_name": "Microsoft Corporation",
                "display_name": "Microsoft",
                "lifecycle_state": "active",
                "owner_org_id": "IT-ENT",
                "risk_tier": "medium",
                "source_system": "PeopleSoft",
                "source_record_id": "ps-v-1001",
                "source_batch_id": "b-20260201-01",
                "source_extract_ts": "2026-02-01 02:00:00",
                "updated_at": "2026-02-01 10:00:00",
            },
            {
                "vendor_id": "vnd-002",
                "legal_name": "Salesforce, Inc.",
                "display_name": "Salesforce",
                "lifecycle_state": "active",
                "owner_org_id": "SALES-OPS",
                "risk_tier": "low",
                "source_system": "Zycus",
                "source_record_id": "zy-v-7721",
                "source_batch_id": "b-20260129-01",
                "source_extract_ts": "2026-01-29 01:30:00",
                "updated_at": "2026-01-29 09:15:00",
            },
            {
                "vendor_id": "vnd-003",
                "legal_name": "Example Legacy Vendor LLC",
                "display_name": "Legacy Vendor",
                "lifecycle_state": "retired",
                "owner_org_id": "FIN-AP",
                "risk_tier": "high",
                "source_system": "Spreadsheet",
                "source_record_id": "xls-row-44",
                "source_batch_id": "b-20251220-01",
                "source_extract_ts": "2025-12-20 08:00:00",
                "updated_at": "2025-12-20 16:30:00",
            },
        ]
    )


def offerings() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "offering_id": "off-001",
                "vendor_id": "vnd-001",
                "offering_name": "Microsoft 365",
                "offering_type": "SaaS",
                "lob": "Enterprise",
                "service_type": "Application",
                "lifecycle_state": "active",
                "criticality_tier": "tier_1",
            },
            {
                "offering_id": "off-002",
                "vendor_id": "vnd-001",
                "offering_name": "Azure",
                "offering_type": "Cloud",
                "lob": "IT",
                "service_type": "Infrastructure",
                "lifecycle_state": "active",
                "criticality_tier": "tier_1",
            },
            {
                "offering_id": "off-004",
                "vendor_id": "vnd-001",
                "offering_name": "Defender For Cloud",
                "offering_type": "Security",
                "lob": "Security",
                "service_type": "Security",
                "lifecycle_state": "in_review",
                "criticality_tier": "tier_2",
            },
            {
                "offering_id": "off-005",
                "vendor_id": "vnd-001",
                "offering_name": "Power Platform",
                "offering_type": "PaaS",
                "lob": "Operations",
                "service_type": "Platform",
                "lifecycle_state": "approved",
                "criticality_tier": "tier_2",
            },
            {
                "offering_id": "off-006",
                "vendor_id": "vnd-001",
                "offering_name": "Dynamics 365 Finance",
                "offering_type": "SaaS",
                "lob": "Finance",
                "service_type": "Application",
                "lifecycle_state": "retired",
                "criticality_tier": "tier_3",
            },
            {
                "offering_id": "off-003",
                "vendor_id": "vnd-002",
                "offering_name": "Sales Cloud",
                "offering_type": "SaaS",
                "lob": "Sales",
                "service_type": "Application",
                "lifecycle_state": "active",
                "criticality_tier": "tier_2",
            },
        ]
    )


def contacts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "vendor_contact_id": "con-001",
                "vendor_id": "vnd-001",
                "contact_type": "account_manager",
                "full_name": "Alex Rivers",
                "email": "alex.rivers@example.com",
                "phone": "555-0101",
                "active_flag": True,
            },
            {
                "vendor_contact_id": "con-002",
                "vendor_id": "vnd-002",
                "contact_type": "support",
                "full_name": "Jordan Lee",
                "email": "jordan.lee@example.com",
                "phone": "555-0142",
                "active_flag": True,
            },
        ]
    )


def vendor_identifiers() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"vendor_identifier_id": "vid-001", "vendor_id": "vnd-001", "identifier_type": "duns", "identifier_value": "123456789", "is_primary": True, "country_code": "US"},
            {"vendor_identifier_id": "vid-002", "vendor_id": "vnd-001", "identifier_type": "peoplesoft_vendor_id", "identifier_value": "PS-1001", "is_primary": False, "country_code": "US"},
            {"vendor_identifier_id": "vid-003", "vendor_id": "vnd-002", "identifier_type": "zycus_supplier_id", "identifier_value": "ZY-7721", "is_primary": True, "country_code": "US"},
            {"vendor_identifier_id": "vid-004", "vendor_id": "vnd-003", "identifier_type": "legacy_id", "identifier_value": "LG-44", "is_primary": True, "country_code": "US"},
        ]
    )


def vendor_business_owners() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"vendor_owner_id": "vown-001", "vendor_id": "vnd-001", "owner_user_principal": "cio-office@example.com", "owner_role": "executive_owner", "active_flag": True},
            {"vendor_owner_id": "vown-002", "vendor_id": "vnd-001", "owner_user_principal": "cloud-platform@example.com", "owner_role": "service_owner", "active_flag": True},
            {"vendor_owner_id": "vown-003", "vendor_id": "vnd-002", "owner_user_principal": "sales-systems@example.com", "owner_role": "business_owner", "active_flag": True},
            {"vendor_owner_id": "vown-004", "vendor_id": "vnd-003", "owner_user_principal": "ap-ops@example.com", "owner_role": "legacy_owner", "active_flag": False},
        ]
    )


def vendor_org_assignments() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"vendor_org_assignment_id": "voa-001", "vendor_id": "vnd-001", "org_id": "IT-ENT", "assignment_type": "primary", "active_flag": True},
            {"vendor_org_assignment_id": "voa-002", "vendor_id": "vnd-001", "org_id": "SEC-OPS", "assignment_type": "consumer", "active_flag": True},
            {"vendor_org_assignment_id": "voa-003", "vendor_id": "vnd-002", "org_id": "SALES-OPS", "assignment_type": "primary", "active_flag": True},
            {"vendor_org_assignment_id": "voa-004", "vendor_id": "vnd-003", "org_id": "FIN-AP", "assignment_type": "primary", "active_flag": False},
        ]
    )


def offering_business_owners() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"offering_owner_id": "oown-001", "offering_id": "off-001", "owner_user_principal": "workspace-admin@example.com", "owner_role": "platform_owner", "active_flag": True},
            {"offering_owner_id": "oown-002", "offering_id": "off-002", "owner_user_principal": "cloud-architect@example.com", "owner_role": "technical_owner", "active_flag": True},
            {"offering_owner_id": "oown-004", "offering_id": "off-004", "owner_user_principal": "security-arch@example.com", "owner_role": "security_owner", "active_flag": True},
            {"offering_owner_id": "oown-005", "offering_id": "off-005", "owner_user_principal": "automation-lead@example.com", "owner_role": "business_owner", "active_flag": True},
            {"offering_owner_id": "oown-006", "offering_id": "off-006", "owner_user_principal": "erp-team@example.com", "owner_role": "legacy_owner", "active_flag": False},
            {"offering_owner_id": "oown-003", "offering_id": "off-003", "owner_user_principal": "salesforce-admin@example.com", "owner_role": "application_owner", "active_flag": True},
        ]
    )


def offering_contacts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"offering_contact_id": "ocon-001", "offering_id": "off-001", "contact_type": "support", "full_name": "M365 Support Desk", "email": "m365-support@example.com", "phone": "555-2001", "active_flag": True},
            {"offering_contact_id": "ocon-002", "offering_id": "off-002", "contact_type": "escalation", "full_name": "Azure Escalation Lead", "email": "azure-escalation@example.com", "phone": "555-2002", "active_flag": True},
            {"offering_contact_id": "ocon-004", "offering_id": "off-004", "contact_type": "security_specialist", "full_name": "Defender Security Specialist", "email": "defender-security@example.com", "phone": "555-2004", "active_flag": True},
            {"offering_contact_id": "ocon-005", "offering_id": "off-005", "contact_type": "product_manager", "full_name": "Power Platform PM", "email": "power-platform-pm@example.com", "phone": "555-2005", "active_flag": True},
            {"offering_contact_id": "ocon-006", "offering_id": "off-006", "contact_type": "support", "full_name": "Dynamics Legacy Support", "email": "dynamics-legacy@example.com", "phone": "555-2006", "active_flag": False},
            {"offering_contact_id": "ocon-003", "offering_id": "off-003", "contact_type": "customer_success", "full_name": "Salesforce CSM", "email": "sf-csm@example.com", "phone": "555-2003", "active_flag": True},
        ]
    )


def contracts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"contract_id": "ctr-101", "vendor_id": "vnd-001", "offering_id": "off-002", "contract_number": "MS-2024-001", "contract_status": "active", "start_date": "2024-04-01", "end_date": "2026-03-15", "cancelled_flag": False, "annual_value": 1880000.0},
            {"contract_id": "ctr-102", "vendor_id": "vnd-001", "offering_id": "off-001", "contract_number": "MS-2024-002", "contract_status": "active", "start_date": "2024-02-01", "end_date": "2026-06-30", "cancelled_flag": False, "annual_value": 720000.0},
            {"contract_id": "ctr-103", "vendor_id": "vnd-001", "offering_id": "off-006", "contract_number": "MS-2022-010", "contract_status": "retired", "start_date": "2022-01-01", "end_date": "2025-09-30", "cancelled_flag": True, "annual_value": 0.0},
            {"contract_id": "ctr-202", "vendor_id": "vnd-002", "offering_id": "off-003", "contract_number": "SF-2024-210", "contract_status": "active", "start_date": "2024-06-01", "end_date": "2026-04-01", "cancelled_flag": False, "annual_value": 745000.0},
            {"contract_id": "ctr-001", "vendor_id": "vnd-003", "offering_id": None, "contract_number": "LG-2022-005", "contract_status": "cancelled", "start_date": "2022-01-01", "end_date": "2025-12-05", "cancelled_flag": True, "annual_value": 0.0},
        ]
    )


def contract_events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"contract_event_id": "ce-001", "contract_id": "ctr-101", "event_type": "renewal_planned", "event_ts": "2026-01-05 09:00:00", "reason_code": None, "notes": "Preparing renewal proposal.", "actor_user_principal": "procurement@example.com"},
            {"contract_event_id": "ce-004", "contract_id": "ctr-102", "event_type": "renewal_planned", "event_ts": "2026-01-18 10:00:00", "reason_code": None, "notes": "Renewal package shared for review.", "actor_user_principal": "procurement@example.com"},
            {"contract_event_id": "ce-005", "contract_id": "ctr-103", "event_type": "contract_cancelled", "event_ts": "2025-09-30 14:30:00", "reason_code": "product_consolidation", "notes": "Consolidated into newer stack.", "actor_user_principal": "it-ops@example.com"},
            {"contract_event_id": "ce-002", "contract_id": "ctr-202", "event_type": "renewal_negotiation", "event_ts": "2026-01-12 11:30:00", "reason_code": None, "notes": "Negotiation round 1.", "actor_user_principal": "sourcing@example.com"},
            {"contract_event_id": "ce-003", "contract_id": "ctr-001", "event_type": "contract_cancelled", "event_ts": "2025-12-05 13:00:00", "reason_code": "cost_overrun", "notes": "Renewal cost exceeded target.", "actor_user_principal": "fin-ops@example.com"},
        ]
    )


def demo_outcomes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "demo_id": "demo-001",
                "vendor_id": "vnd-001",
                "offering_id": "off-002",
                "demo_date": "2026-01-10",
                "overall_score": 8.9,
                "selection_outcome": "selected",
                "non_selection_reason_code": None,
                "notes": "Strong security and integration.",
            },
            {
                "demo_id": "demo-003",
                "vendor_id": "vnd-001",
                "offering_id": "off-004",
                "demo_date": "2026-01-28",
                "overall_score": 6.1,
                "selection_outcome": "not_selected",
                "non_selection_reason_code": "insufficient_coverage",
                "notes": "Did not meet advanced detection requirements.",
            },
            {
                "demo_id": "demo-004",
                "vendor_id": "vnd-001",
                "offering_id": "off-005",
                "demo_date": "2026-02-02",
                "overall_score": 6.8,
                "selection_outcome": "not_selected",
                "non_selection_reason_code": "cost_overrun",
                "notes": "Total cost of ownership exceeded approved budget.",
            },
            {
                "demo_id": "demo-005",
                "vendor_id": "vnd-001",
                "offering_id": "off-006",
                "demo_date": "2025-07-10",
                "overall_score": 5.4,
                "selection_outcome": "deferred",
                "non_selection_reason_code": "roadmap_uncertain",
                "notes": "Deferred pending roadmap clarification.",
            },
            {
                "demo_id": "demo-002",
                "vendor_id": "vnd-003",
                "offering_id": None,
                "demo_date": "2025-11-01",
                "overall_score": 5.2,
                "selection_outcome": "not_selected",
                "non_selection_reason_code": "poor_scalability",
                "notes": "Failed on scale testing.",
            },
        ]
    )


def demo_scores() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"demo_score_id": "ds-001", "demo_id": "demo-001", "score_category": "security", "score_value": 9.1, "weight": 0.3, "comments": "Strong controls."},
            {"demo_score_id": "ds-002", "demo_id": "demo-001", "score_category": "integration", "score_value": 8.8, "weight": 0.25, "comments": "Good integration patterns."},
            {"demo_score_id": "ds-003", "demo_id": "demo-001", "score_category": "cost", "score_value": 8.2, "weight": 0.2, "comments": "Competitive with enterprise discount."},
            {"demo_score_id": "ds-006", "demo_id": "demo-003", "score_category": "coverage", "score_value": 5.2, "weight": 0.3, "comments": "Coverage gaps in key use cases."},
            {"demo_score_id": "ds-007", "demo_id": "demo-003", "score_category": "integration", "score_value": 6.5, "weight": 0.2, "comments": "Adequate integration path."},
            {"demo_score_id": "ds-008", "demo_id": "demo-004", "score_category": "cost", "score_value": 4.7, "weight": 0.35, "comments": "Budget exceeded target range."},
            {"demo_score_id": "ds-009", "demo_id": "demo-004", "score_category": "business_fit", "score_value": 7.1, "weight": 0.25, "comments": "Good fit but too expensive."},
            {"demo_score_id": "ds-010", "demo_id": "demo-005", "score_category": "roadmap", "score_value": 5.0, "weight": 0.3, "comments": "Roadmap uncertainty for requirements."},
            {"demo_score_id": "ds-004", "demo_id": "demo-002", "score_category": "scalability", "score_value": 4.9, "weight": 0.35, "comments": "Could not meet throughput target."},
            {"demo_score_id": "ds-005", "demo_id": "demo-002", "score_category": "ux", "score_value": 6.0, "weight": 0.15, "comments": "Usable but dated."},
        ]
    )


def demo_notes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"demo_note_id": "dn-001", "demo_id": "demo-001", "note_type": "selection_rationale", "note_text": "Selected due to security baseline and integration maturity.", "created_at": "2026-01-10 15:00:00", "created_by": "architecture-board@example.com"},
            {"demo_note_id": "dn-003", "demo_id": "demo-003", "note_type": "non_selection_rationale", "note_text": "Coverage gaps against SOC monitoring and response criteria.", "created_at": "2026-01-28 16:20:00", "created_by": "security-board@example.com"},
            {"demo_note_id": "dn-004", "demo_id": "demo-004", "note_type": "non_selection_rationale", "note_text": "Not selected due to budget and duplicate capability overlap.", "created_at": "2026-02-02 17:05:00", "created_by": "procurement-board@example.com"},
            {"demo_note_id": "dn-005", "demo_id": "demo-005", "note_type": "defer_rationale", "note_text": "Deferred pending roadmap commitment from vendor.", "created_at": "2025-07-10 12:45:00", "created_by": "architecture-board@example.com"},
            {"demo_note_id": "dn-002", "demo_id": "demo-002", "note_type": "non_selection_rationale", "note_text": "Rejected due to poor scalability and uncertain roadmap.", "created_at": "2025-11-01 16:00:00", "created_by": "architecture-board@example.com"},
        ]
    )


def contract_cancellations() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "contract_id": "ctr-001",
                "vendor_id": "vnd-003",
                "offering_id": None,
                "cancelled_at": "2025-12-05 13:00:00",
                "reason_code": "cost_overrun",
                "notes": "Renewal cost exceeded target.",
            }
        ]
    )


def change_requests() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"change_request_id": "cr-001", "vendor_id": "vnd-001", "requestor_user_principal": "cloud-platform@example.com", "change_type": "update_contact", "requested_payload_json": "{\"contact\":\"new escalation\"}", "status": "approved", "submitted_at": "2026-01-15 10:00:00", "updated_at": "2026-01-16 09:00:00"},
            {"change_request_id": "cr-002", "vendor_id": "vnd-001", "requestor_user_principal": "procurement@example.com", "change_type": "request_lifecycle_change", "requested_payload_json": "{\"state\":\"active\"}", "status": "submitted", "submitted_at": "2026-02-03 10:30:00", "updated_at": "2026-02-03 10:30:00"},
            {"change_request_id": "cr-003", "vendor_id": "vnd-003", "requestor_user_principal": "fin-ops@example.com", "change_type": "update_vendor_profile", "requested_payload_json": "{\"risk_tier\":\"high\"}", "status": "approved", "submitted_at": "2025-12-19 08:15:00", "updated_at": "2025-12-20 09:45:00"},
        ]
    )


def projects() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "project_id": "prj-001",
                "vendor_id": "vnd-001",
                "project_name": "Defender Rollout FY26",
                "project_type": "implementation",
                "status": "active",
                "start_date": "2026-01-05",
                "target_date": "2026-06-30",
                "owner_principal": "bob.smith@example.com",
                "description": "Expand Defender controls across core workloads.",
                "active_flag": True,
                "created_at": "2026-01-05 09:00:00",
                "created_by": "admin@example.com",
                "updated_at": "2026-02-01 14:00:00",
                "updated_by": "admin@example.com",
            },
            {
                "project_id": "prj-002",
                "vendor_id": "vnd-001",
                "project_name": "Power Platform Evaluation",
                "project_type": "poc",
                "status": "blocked",
                "start_date": "2026-01-20",
                "target_date": "2026-03-31",
                "owner_principal": "amy.johnson@example.com",
                "description": "Evaluate business automation use cases.",
                "active_flag": True,
                "created_at": "2026-01-20 11:00:00",
                "created_by": "admin@example.com",
                "updated_at": "2026-02-03 10:30:00",
                "updated_by": "admin@example.com",
            },
        ]
    )


def project_offering_maps() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "project_offering_map_id": "pom-001",
                "project_id": "prj-001",
                "offering_id": "off-004",
                "active_flag": True,
            },
            {
                "project_offering_map_id": "pom-002",
                "project_id": "prj-001",
                "offering_id": "off-002",
                "active_flag": True,
            },
            {
                "project_offering_map_id": "pom-003",
                "project_id": "prj-002",
                "offering_id": "off-005",
                "active_flag": True,
            },
        ]
    )


def project_demos() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "project_demo_id": "pdm-001",
                "project_id": "prj-001",
                "vendor_id": "vnd-001",
                "demo_name": "Defender Deep Dive",
                "demo_datetime_start": "2026-01-28 13:00:00",
                "demo_datetime_end": "2026-01-28 14:30:00",
                "demo_type": "workshop",
                "outcome": "follow_up",
                "score": 7.4,
                "attendees_internal": "security team; architecture",
                "attendees_vendor": "defender specialists",
                "notes": "Need additional endpoint coverage details.",
                "followups": "Review roadmap in next session.",
                "linked_offering_id": "off-004",
                "linked_vendor_demo_id": "demo-003",
                "active_flag": True,
                "created_at": "2026-01-28 15:00:00",
                "created_by": "admin@example.com",
                "updated_at": "2026-01-28 15:00:00",
                "updated_by": "admin@example.com",
            }
        ]
    )


def project_notes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "project_note_id": "pnt-001",
                "project_id": "prj-001",
                "vendor_id": "vnd-001",
                "note_text": "Initial kickoff complete; pending ownership confirmation.",
                "active_flag": True,
                "created_at": "2026-02-01 09:30:00",
                "created_by": "admin@example.com",
                "updated_at": "2026-02-01 09:30:00",
                "updated_by": "admin@example.com",
            }
        ]
    )


def document_links() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "doc_id": "doc-001",
                "entity_type": "vendor",
                "entity_id": "vnd-001",
                "doc_title": "sharepoint.com - Vendor_Master_Packet.pdf",
                "doc_url": "https://contoso.sharepoint.com/sites/vendor/Documents/Vendor_Master_Packet.pdf",
                "doc_type": "sharepoint",
                "tags": "master,contract",
                "owner": "procurement@example.com",
                "active_flag": True,
                "created_at": "2026-01-18 10:00:00",
                "created_by": "admin@example.com",
                "updated_at": "2026-01-18 10:00:00",
                "updated_by": "admin@example.com",
            },
            {
                "doc_id": "doc-002",
                "entity_type": "project",
                "entity_id": "prj-001",
                "doc_title": "confluence - Defender-Rollout-Notes",
                "doc_url": "https://example.atlassian.net/wiki/spaces/SEC/pages/12345/Defender-Rollout-Notes",
                "doc_type": "confluence",
                "tags": "notes",
                "owner": "bob.smith@example.com",
                "active_flag": True,
                "created_at": "2026-01-29 09:15:00",
                "created_by": "admin@example.com",
                "updated_at": "2026-01-29 09:15:00",
                "updated_by": "admin@example.com",
            },
            {
                "doc_id": "doc-003",
                "entity_type": "offering",
                "entity_id": "off-004",
                "doc_title": "github.com - threat-model.md",
                "doc_url": "https://github.com/example/security-docs/blob/main/threat-model.md",
                "doc_type": "github",
                "tags": "security,architecture",
                "owner": "security-arch@example.com",
                "active_flag": True,
                "created_at": "2026-01-30 08:00:00",
                "created_by": "admin@example.com",
                "updated_at": "2026-01-30 08:00:00",
                "updated_by": "admin@example.com",
            },
        ]
    )


def audit_entity_changes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "change_event_id": "ae-001",
                "entity_name": "core_vendor",
                "entity_id": "vnd-001",
                "action_type": "update",
                "before_json": {"risk_tier": "low", "owner_org_id": "IT-ENT"},
                "after_json": {"risk_tier": "medium", "owner_org_id": "IT-ENT"},
                "event_ts": "2026-01-16 09:00:00",
                "actor_user_principal": "vendor_steward@example.com",
                "request_id": "cr-001",
            },
            {
                "change_event_id": "ae-002",
                "entity_name": "core_vendor_demo",
                "entity_id": "demo-002",
                "action_type": "insert",
                "before_json": None,
                "after_json": {"demo_date": "2025-11-01", "overall_score": 7.9, "selection_outcome": "selected"},
                "event_ts": "2025-11-01 16:00:00",
                "actor_user_principal": "architecture-board@example.com",
                "request_id": None,
            },
            {
                "change_event_id": "ae-003",
                "entity_name": "core_contract",
                "entity_id": "ctr-001",
                "action_type": "update",
                "before_json": {"contract_status": "active", "cancelled_flag": False},
                "after_json": {"contract_status": "cancelled", "cancelled_flag": True},
                "event_ts": "2025-12-05 13:00:00",
                "actor_user_principal": "fin-ops@example.com",
                "request_id": None,
            },
        ]
    )


def source_records() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"source_system": "PeopleSoft", "source_record_id": "ps-v-1001", "source_batch_id": "b-20260201-01", "source_extract_ts": "2026-02-01 02:00:00", "entity_hint": "Vendor"},
            {"source_system": "Zycus", "source_record_id": "zy-v-7721", "source_batch_id": "b-20260129-01", "source_extract_ts": "2026-01-29 01:30:00", "entity_hint": "Vendor"},
            {"source_system": "Spreadsheet", "source_record_id": "xls-row-44", "source_batch_id": "b-20251220-01", "source_extract_ts": "2025-12-20 08:00:00", "entity_hint": "Vendor"},
        ]
    )


def role_map() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "user_principal": "admin@example.com",
                "role_code": "vendor_admin",
                "active_flag": True,
                "granted_by": "bootstrap",
                "granted_at": "2026-01-01 00:00:00",
                "revoked_at": None,
            },
            {
                "user_principal": "editor@example.com",
                "role_code": "vendor_editor",
                "active_flag": True,
                "granted_by": "admin@example.com",
                "granted_at": "2026-01-15 08:00:00",
                "revoked_at": None,
            },
        ]
    )


def org_scope() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "user_principal": "admin@example.com",
                "org_id": "IT-ENT",
                "scope_level": "full",
                "active_flag": True,
                "granted_at": "2026-01-01 00:00:00",
            },
            {
                "user_principal": "editor@example.com",
                "org_id": "SALES-OPS",
                "scope_level": "edit",
                "active_flag": True,
                "granted_at": "2026-01-15 08:00:00",
            },
        ]
    )


def spend_facts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"month": "2025-09-01", "vendor_id": "vnd-001", "org_id": "IT-ENT", "category": "Cloud", "amount": 285000.0},
            {"month": "2025-10-01", "vendor_id": "vnd-001", "org_id": "IT-ENT", "category": "Cloud", "amount": 292000.0},
            {"month": "2025-11-01", "vendor_id": "vnd-001", "org_id": "IT-ENT", "category": "Productivity", "amount": 164000.0},
            {"month": "2025-12-01", "vendor_id": "vnd-001", "org_id": "IT-ENT", "category": "Cloud", "amount": 301500.0},
            {"month": "2026-01-01", "vendor_id": "vnd-001", "org_id": "IT-ENT", "category": "Productivity", "amount": 171000.0},
            {"month": "2026-02-01", "vendor_id": "vnd-001", "org_id": "IT-ENT", "category": "Cloud", "amount": 309200.0},
            {"month": "2025-09-01", "vendor_id": "vnd-002", "org_id": "SALES-OPS", "category": "CRM", "amount": 118000.0},
            {"month": "2025-10-01", "vendor_id": "vnd-002", "org_id": "SALES-OPS", "category": "CRM", "amount": 121500.0},
            {"month": "2025-11-01", "vendor_id": "vnd-002", "org_id": "SALES-OPS", "category": "CRM", "amount": 120750.0},
            {"month": "2025-12-01", "vendor_id": "vnd-002", "org_id": "SALES-OPS", "category": "CRM", "amount": 122100.0},
            {"month": "2026-01-01", "vendor_id": "vnd-002", "org_id": "SALES-OPS", "category": "CRM", "amount": 124900.0},
            {"month": "2026-02-01", "vendor_id": "vnd-002", "org_id": "SALES-OPS", "category": "CRM", "amount": 126000.0},
            {"month": "2025-09-01", "vendor_id": "vnd-003", "org_id": "FIN-AP", "category": "Legacy ERP", "amount": 58000.0},
            {"month": "2025-10-01", "vendor_id": "vnd-003", "org_id": "FIN-AP", "category": "Legacy ERP", "amount": 56000.0},
            {"month": "2025-11-01", "vendor_id": "vnd-003", "org_id": "FIN-AP", "category": "Legacy ERP", "amount": 53500.0},
            {"month": "2025-12-01", "vendor_id": "vnd-003", "org_id": "FIN-AP", "category": "Legacy ERP", "amount": 0.0},
            {"month": "2026-01-01", "vendor_id": "vnd-003", "org_id": "FIN-AP", "category": "Legacy ERP", "amount": 0.0},
            {"month": "2026-02-01", "vendor_id": "vnd-003", "org_id": "FIN-AP", "category": "Legacy ERP", "amount": 0.0},
        ]
    )


def renewal_pipeline() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "contract_id": "ctr-101",
                "vendor_id": "vnd-001",
                "vendor_name": "Microsoft",
                "org_id": "IT-ENT",
                "category": "Cloud",
                "renewal_date": "2026-03-15",
                "annual_value": 1880000.0,
                "risk_tier": "medium",
                "renewal_status": "planned",
            },
            {
                "contract_id": "ctr-202",
                "vendor_id": "vnd-002",
                "vendor_name": "Salesforce",
                "org_id": "SALES-OPS",
                "category": "CRM",
                "renewal_date": "2026-04-01",
                "annual_value": 745000.0,
                "risk_tier": "low",
                "renewal_status": "in_negotiation",
            },
            {
                "contract_id": "ctr-303",
                "vendor_id": "vnd-003",
                "vendor_name": "Legacy Vendor",
                "org_id": "FIN-AP",
                "category": "Legacy ERP",
                "renewal_date": "2026-02-20",
                "annual_value": 0.0,
                "risk_tier": "high",
                "renewal_status": "retired",
            },
        ]
    )
