from __future__ import annotations

from typing import Any

IMPORT_MAX_ROWS = 20000
IMPORT_PREVIEW_RENDER_LIMIT = 1200
IMPORT_RESULTS_RENDER_LIMIT = 800
ALLOWED_IMPORT_ACTIONS = {"new", "merge", "skip"}

IMPORT_LAYOUTS: dict[str, dict[str, Any]] = {
    "vendors": {
        "label": "Vendors",
        "description": (
            "Create vendor profiles or merge updates into existing vendor records. "
            "Optional support contact fields improve auto-matching and vendor grouping."
        ),
        "fields": [
            "vendor_id",
            "legal_name",
            "display_name",
            "owner_org_id",
            "lifecycle_state",
            "risk_tier",
            "support_contact_name",
            "support_contact_type",
            "support_email",
            "support_phone",
        ],
        "sample_rows": [
            {
                "vendor_id": "",
                "legal_name": "Acme Cloud LLC",
                "display_name": "Acme Cloud",
                "owner_org_id": "IT",
                "lifecycle_state": "draft",
                "risk_tier": "medium",
                "support_contact_name": "Acme Support",
                "support_contact_type": "business",
                "support_email": "support@acmecloud.com",
                "support_phone": "1-800-555-0100",
            }
        ],
    },
    "offerings": {
        "label": "Offerings",
        "description": (
            "Create offerings or merge updates into existing offerings. "
            "If vendor_id is missing, vendor_name/support contact fields can auto-map offerings to vendors."
        ),
        "fields": [
            "offering_id",
            "vendor_id",
            "vendor_name",
            "vendor_contact_email",
            "vendor_support_phone",
            "offering_name",
            "offering_type",
            "lob",
            "service_type",
            "lifecycle_state",
            "criticality_tier",
        ],
        "sample_rows": [
            {
                "offering_id": "",
                "vendor_id": "",
                "vendor_name": "Acme Cloud",
                "vendor_contact_email": "support@acmecloud.com",
                "vendor_support_phone": "1-800-555-0100",
                "offering_name": "Enterprise Search",
                "offering_type": "software",
                "lob": "internal_platform",
                "service_type": "saas",
                "lifecycle_state": "draft",
                "criticality_tier": "tier2",
            }
        ],
    },
    "projects": {
        "label": "Projects",
        "description": "Create new projects or merge updates into existing projects.",
        "fields": [
            "project_id",
            "vendor_id",
            "project_name",
            "project_type",
            "status",
            "start_date",
            "target_date",
            "owner_principal",
            "description",
        ],
        "sample_rows": [
            {
                "project_id": "",
                "vendor_id": "vnd-123456",
                "project_name": "Q2 Renewal Program",
                "project_type": "renewal",
                "status": "draft",
                "start_date": "2026-03-01",
                "target_date": "2026-06-30",
                "owner_principal": "jane.doe@example.com",
                "description": "Renewal and right-sizing workstream.",
            }
        ],
    },
}
