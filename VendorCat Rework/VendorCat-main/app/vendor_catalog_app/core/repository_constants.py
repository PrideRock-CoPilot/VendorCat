# pylint: disable=missing-module-docstring
"""Shared repository constants for Vendor Catalog."""

from __future__ import annotations

UNKNOWN_USER_PRINCIPAL = "unknown_user"
GLOBAL_CHANGE_VENDOR_ID = "__global__"
LOOKUP_TYPE_DOC_SOURCE = "doc_source"
LOOKUP_TYPE_DOC_TAG = "doc_tag"
LOOKUP_TYPE_OWNER_ROLE = "owner_role"
LOOKUP_TYPE_ASSIGNMENT_TYPE = "assignment_type"
LOOKUP_TYPE_CONTACT_TYPE = "contact_type"
LOOKUP_TYPE_PROJECT_TYPE = "project_type"
LOOKUP_TYPE_OFFERING_TYPE = "offering_type"
LOOKUP_TYPE_OFFERING_BUSINESS_UNIT = "offering_business_unit"
LOOKUP_TYPE_OFFERING_SERVICE_TYPE = "offering_service_type"
LOOKUP_TYPE_WORKFLOW_STATUS = "workflow_status"
LOOKUP_TYPE_OWNER_ORGANIZATION = "owner_organization"
LOOKUP_TYPE_VENDOR_CATEGORY = "vendor_category"
LOOKUP_TYPE_COMPLIANCE_CATEGORY = "compliance_category"
LOOKUP_TYPE_GL_CATEGORY = "gl_category"
LOOKUP_TYPE_RISK_TIER = "risk_tier"
LOOKUP_TYPE_LIFECYCLE_STATE = "lifecycle_state"

SUPPORTED_LOOKUP_TYPES = {
    LOOKUP_TYPE_DOC_SOURCE,
    LOOKUP_TYPE_DOC_TAG,
    LOOKUP_TYPE_OWNER_ROLE,
    LOOKUP_TYPE_ASSIGNMENT_TYPE,
    LOOKUP_TYPE_CONTACT_TYPE,
    LOOKUP_TYPE_PROJECT_TYPE,
    LOOKUP_TYPE_OFFERING_TYPE,
    LOOKUP_TYPE_OFFERING_BUSINESS_UNIT,
    LOOKUP_TYPE_OFFERING_SERVICE_TYPE,
    LOOKUP_TYPE_WORKFLOW_STATUS,
    LOOKUP_TYPE_OWNER_ORGANIZATION,
    LOOKUP_TYPE_VENDOR_CATEGORY,
    LOOKUP_TYPE_COMPLIANCE_CATEGORY,
    LOOKUP_TYPE_GL_CATEGORY,
    LOOKUP_TYPE_RISK_TIER,
    LOOKUP_TYPE_LIFECYCLE_STATE,
}

DEFAULT_DOC_SOURCE_OPTIONS = [
    "sharepoint",
    "onedrive",
    "confluence",
    "google_drive",
    "box",
    "dropbox",
    "github",
    "other",
]

DEFAULT_DOC_TAG_OPTIONS = [
    "contract",
    "msa",
    "nda",
    "sow",
    "invoice",
    "renewal",
    "security",
    "architecture",
    "runbook",
    "compliance",
    "rfp",
    "poc",
    "notes",
    "operations",
    "folder",
]

DEFAULT_OWNER_ROLE_OPTIONS = [
    "business_owner",
    "executive_owner",
    "service_owner",
    "technical_owner",
    "security_owner",
    "application_owner",
    "platform_owner",
    "legacy_owner",
]

DEFAULT_ASSIGNMENT_TYPE_OPTIONS = ["consumer", "primary", "secondary"]

DEFAULT_CONTACT_TYPE_OPTIONS = [
    "business",
    "account_manager",
    "support",
    "escalation",
    "security_specialist",
    "customer_success",
    "product_manager",
]

DEFAULT_PROJECT_TYPE_OPTIONS = ["rfp", "poc", "renewal", "implementation", "other"]
DEFAULT_WORKFLOW_STATUS_OPTIONS = ["submitted", "in_review", "approved", "rejected"]

DEFAULT_OFFERING_TYPE_CHOICES = [
    ("saas", "SaaS"),
    ("cloud", "Cloud"),
    ("paas", "PaaS"),
    ("security", "Security"),
    ("data", "Data"),
    ("integration", "Integration"),
    ("other", "Other"),
]

DEFAULT_OFFERING_BUSINESS_UNIT_CHOICES = [
    ("enterprise", "Enterprise"),
    ("finance", "Finance"),
    ("hr", "HR"),
    ("it", "IT"),
    ("operations", "Operations"),
    ("sales", "Sales"),
    ("security", "Security"),
]

DEFAULT_OFFERING_SERVICE_TYPE_CHOICES = [
    ("application", "Application"),
    ("infrastructure", "Infrastructure"),
    ("integration", "Integration"),
    ("managed_service", "Managed Service"),
    ("platform", "Platform"),
    ("security", "Security"),
    ("support", "Support"),
    ("other", "Other"),
]

DEFAULT_OWNER_ORGANIZATION_CHOICES = [
    ("it_ent", "IT-ENT"),
    ("it_sec", "IT-SEC"),
    ("sales_ops", "SALES-OPS"),
    ("fin_ap", "FIN-AP"),
    ("hr_ops", "HR-OPS"),
]

DEFAULT_VENDOR_CATEGORY_CHOICES = [
    ("software", "Software"),
    ("services", "Services"),
    ("infrastructure", "Infrastructure"),
    ("consulting", "Consulting"),
]

DEFAULT_COMPLIANCE_CATEGORY_CHOICES = [
    ("hipaa", "HIPAA"),
    ("sox", "SOX"),
    ("pci", "PCI"),
    ("none", "None"),
]

DEFAULT_GL_CATEGORY_CHOICES = [
    ("opex", "OpEx"),
    ("capex", "CapEx"),
    ("software", "Software"),
    ("professional_services", "Professional Services"),
]

DEFAULT_RISK_TIER_CHOICES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical"),
]

DEFAULT_LIFECYCLE_STATE_CHOICES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("in_review", "In Review"),
    ("approved", "Approved"),
    ("active", "Active"),
    ("suspended", "Suspended"),
    ("retired", "Retired"),
]
