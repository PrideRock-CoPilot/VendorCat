from __future__ import annotations

from vendor_catalog_app.core.defaults import (
    DEFAULT_CONTRACT_STATUS,
    DEFAULT_FILTER_OPTION_ALL,
    DEFAULT_GROUP_OPTION_NONE,
    DEFAULT_RETURN_TO_PATH,
    DEFAULT_VENDOR_SETTINGS_KEY,
)

DEFAULT_VENDOR_FIELDS = [
    "display_name",
    "vendor_id",
    "legal_name",
    "lifecycle_state",
    "owner_org_id",
    "risk_tier",
    "updated_at",
]
DEFAULT_VENDOR_PAGE_SIZE = 25
VENDOR_PAGE_SIZES = [1, 5, 10, 25, 50, 100]
DEFAULT_VENDOR_SORT_BY = "vendor_name"
DEFAULT_VENDOR_SORT_DIR = "asc"
VENDOR_SORT_FIELDS = ["vendor_name", "vendor_id", "legal_name", "lifecycle_state", "owner_org_id", "risk_tier", "updated_at"]
VENDOR_FIELD_SORT_MAP = {
    "display_name": "vendor_name",
    "vendor_id": "vendor_id",
    "legal_name": "legal_name",
    "lifecycle_state": "lifecycle_state",
    "owner_org_id": "owner_org_id",
    "risk_tier": "risk_tier",
    "updated_at": "updated_at",
}
VENDOR_DEFAULT_RETURN_TO = DEFAULT_RETURN_TO_PATH
VENDOR_FILTER_ALL = DEFAULT_FILTER_OPTION_ALL
VENDOR_GROUP_NONE = DEFAULT_GROUP_OPTION_NONE
VENDOR_SETTINGS_KEY = DEFAULT_VENDOR_SETTINGS_KEY
CONTRACT_STATUS_DEFAULT = DEFAULT_CONTRACT_STATUS

LIFECYCLE_STATES = ["draft", "submitted", "in_review", "approved", "active", "suspended", "retired"]
RISK_TIERS = ["low", "medium", "high", "critical"]
PROJECT_STATUSES = ["draft", "active", "blocked", "complete", "cancelled"]
PROJECT_TYPES_FALLBACK = ["rfp", "poc", "renewal", "implementation", "other"]
PROJECT_DEMO_TYPES = ["live", "recorded", "workshop", "sandbox"]
PROJECT_DEMO_OUTCOMES = ["unknown", "selected", "not_selected", "follow_up"]
OFFERING_TYPES_FALLBACK = ["SaaS", "Cloud", "PaaS", "Security", "Data", "Integration", "Other"]
OFFERING_LOB_FALLBACK = ["Enterprise", "Finance", "HR", "IT", "Operations", "Sales", "Security"]
OFFERING_SERVICE_TYPE_FALLBACK = [
    "Application",
    "Infrastructure",
    "Integration",
    "Managed Service",
    "Platform",
    "Security",
    "Support",
    "Other",
]
OFFERING_SECTIONS = [
    ("summary", "Summary"),
    ("profile", "Profile"),
    ("financials", "Financials"),
    ("dataflow", "Data Flow"),
    ("ownership", "Ownership"),
    ("delivery", "Delivery"),
    ("tickets", "Tickets"),
    ("notes", "Notes"),
    ("documents", "Documents"),
]
OFFERING_TICKET_STATUSES = ["open", "in_progress", "blocked", "resolved", "closed"]
OFFERING_TICKET_PRIORITIES = ["low", "medium", "high", "critical"]
OFFERING_NOTE_TYPES = ["general", "issue", "implementation", "cost", "data_flow", "misc", "risk", "decision"]
OFFERING_DATA_METHOD_OPTIONS = ["api", "file_transfer", "cloud_to_cloud", "event_stream", "manual", "other"]
OFFERING_INVOICE_STATUSES = ["received", "approved", "paid", "disputed", "void"]
CONTRACT_STATUS_OPTIONS = ["draft", "pending", "active", "retired", "expired"]
CONTRACT_CANCEL_REASON_OPTIONS = [
    "business_change",
    "cost_overrun",
    "duplicate_capability",
    "security_risk",
    "compliance_gap",
    "vendor_performance",
    "other",
]
OWNER_REMOVE_REASON_OPTIONS = [
    "role_change",
    "ownership_transition",
    "org_change",
    "duplicate_assignment",
    "inactive_user",
    "access_cleanup",
    "other",
]
OWNER_REASSIGN_REASON_OPTIONS = [
    "employee_inactive",
    "employee_departed",
    "org_change",
    "role_transition",
    "access_cleanup",
    "other",
]
VENDOR_PROFILE_CHANGE_REASON_OPTIONS = [
    "business_update",
    "governance_correction",
    "org_restructure",
    "risk_reassessment",
    "source_alignment",
    "other",
]
CONTRACT_CHANGE_REASON_OPTIONS = [
    "new_agreement",
    "renewal_update",
    "terms_adjustment",
    "cost_alignment",
    "compliance_update",
    "other",
]
CONTRACT_MAPPING_REASON_OPTIONS = [
    "portfolio_alignment",
    "ownership_correction",
    "contract_split_or_merge",
    "reporting_alignment",
    "other",
]
DEMO_MAPPING_REASON_OPTIONS = [
    "portfolio_alignment",
    "ownership_correction",
    "evaluation_scope_change",
    "reporting_alignment",
    "other",
]
PROJECT_UPDATE_REASON_OPTIONS = [
    "scope_change",
    "timeline_change",
    "ownership_change",
    "status_correction",
    "vendor_alignment",
    "other",
]
PROJECT_OWNER_CHANGE_REASON_OPTIONS = [
    "ownership_transition",
    "role_change",
    "org_change",
    "coverage_backup",
    "other",
]
PROJECT_ASSOCIATION_REASON_OPTIONS = [
    "new_scope",
    "scope_correction",
    "dependency_alignment",
    "consolidation",
    "other",
]
PROJECT_ASSOCIATION_AUTO_REASON = "auto_attach_from_vendor_selection"
PROJECT_DEMO_REAUDIT_REASON_OPTIONS = [
    "audit_correction",
    "data_quality_fix",
    "status_update",
    "evidence_update",
    "other",
]
OWNER_ADD_REASON_OPTIONS = [
    "new_assignment",
    "coverage_backup",
    "role_change",
    "org_change",
    "other",
]
OWNER_ROLE_UPDATE_REASON_OPTIONS = [
    "role_change",
    "scope_change",
    "org_change",
    "ownership_clarification",
    "other",
]
ORG_ASSIGNMENT_REASON_OPTIONS = [
    "new_assignment",
    "org_change",
    "scope_change",
    "ownership_alignment",
    "other",
]
CONTACT_ADD_REASON_OPTIONS = [
    "new_contact",
    "coverage_backup",
    "org_change",
    "directory_sync",
    "other",
]
CONTACT_REMOVE_REASON_OPTIONS = [
    "contact_departed",
    "role_change",
    "duplicate_contact",
    "coverage_transfer",
    "other",
]
OFFERING_UPDATE_REASON_OPTIONS = [
    "portfolio_update",
    "service_change",
    "lifecycle_change",
    "criticality_update",
    "other",
]
OFFERING_PROFILE_REASON_OPTIONS = [
    "operating_model_update",
    "cost_baseline_update",
    "integration_update",
    "control_update",
    "other",
]
OFFERING_DATAFLOW_CHANGE_REASON_OPTIONS = [
    "new_feed",
    "feed_update",
    "integration_change",
    "compliance_update",
    "other",
]
OFFERING_DATAFLOW_REMOVE_REASON_OPTIONS = [
    "feed_decommissioned",
    "duplicate_feed",
    "vendor_change",
    "compliance_or_security",
    "other",
]
OFFERING_INVOICE_ADD_REASON_OPTIONS = [
    "monthly_billing",
    "true_up",
    "credit_or_adjustment",
    "backfill",
    "other",
]
OFFERING_INVOICE_REMOVE_REASON_OPTIONS = [
    "duplicate_invoice",
    "entry_error",
    "voided_by_vendor",
    "merge_cleanup",
    "other",
]
OFFERING_TICKET_UPDATE_REASON_OPTIONS = [
    "status_progression",
    "resolution_recorded",
    "reopened_issue",
    "data_correction",
    "other",
]
IMPORT_MERGE_REASON_OPTIONS = [
    "source_correction",
    "scheduled_sync",
    "bulk_cleanup",
    "data_quality_fix",
    "other",
]

VENDOR_SECTIONS = [
    ("summary", "Summary"),
    ("ownership", "Ownership"),
    ("projects", "Projects"),
    ("offerings", "Offerings"),
    ("contracts", "Contracts"),
    ("demos", "Demos"),
    ("lineage", "Lineage/Audit"),
    ("changes", "Changes"),
]
