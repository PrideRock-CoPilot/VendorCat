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
LOOKUP_TYPE_OFFERING_LOB = "offering_lob"
LOOKUP_TYPE_OFFERING_SERVICE_TYPE = "offering_service_type"
LOOKUP_TYPE_WORKFLOW_STATUS = "workflow_status"

SUPPORTED_LOOKUP_TYPES = {
    LOOKUP_TYPE_DOC_SOURCE,
    LOOKUP_TYPE_DOC_TAG,
    LOOKUP_TYPE_OWNER_ROLE,
    LOOKUP_TYPE_ASSIGNMENT_TYPE,
    LOOKUP_TYPE_CONTACT_TYPE,
    LOOKUP_TYPE_PROJECT_TYPE,
    LOOKUP_TYPE_OFFERING_TYPE,
    LOOKUP_TYPE_OFFERING_LOB,
    LOOKUP_TYPE_OFFERING_SERVICE_TYPE,
    LOOKUP_TYPE_WORKFLOW_STATUS,
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

DEFAULT_OFFERING_LOB_CHOICES = [
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
