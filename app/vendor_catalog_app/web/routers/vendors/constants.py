from __future__ import annotations

from vendor_catalog_app.defaults import (
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
