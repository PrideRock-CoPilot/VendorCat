from __future__ import annotations

from typing import Any

IMPORT_MAX_ROWS = 20000
IMPORT_PREVIEW_RENDER_LIMIT = 1200
IMPORT_RESULTS_RENDER_LIMIT = 800
ALLOWED_IMPORT_ACTIONS = {"new", "merge", "skip"}
IMPORT_SOURCE_SYSTEM_OPTIONS = (
    "peoplesoft",
    "zycus",
    "workday",
    "coupa",
    "spreadsheet_manual",
    "other",
)
IMPORT_FILE_FORMAT_OPTIONS = (
    {"key": "auto", "label": "Auto Detect"},
    {"key": "csv", "label": "CSV"},
    {"key": "tsv", "label": "TSV"},
    {"key": "json", "label": "JSON"},
    {"key": "xml", "label": "XML"},
    {"key": "delimited", "label": "Custom Delimited"},
)

IMPORT_STAGING_AREAS: dict[str, dict[str, Any]] = {
    "vendor": {
        "label": "Vendor",
        "stage_table": "app_import_stage_vendor",
        "fields": (
            ("vendor_id", "Vendor - ID"),
            ("legal_name", "Vendor - Legal Name"),
            ("display_name", "Vendor - Display Name"),
            ("owner_org_id", "Vendor - Owner Org"),
            ("lifecycle_state", "Vendor - Lifecycle State"),
            ("risk_tier", "Vendor - Risk Tier"),
        ),
    },
    "vendor_contact": {
        "label": "Vendor Contact",
        "stage_table": "app_import_stage_vendor_contact",
        "fields": (
            ("vendor_id", "Vendor Contact - Vendor ID"),
            ("full_name", "Vendor Contact - Name"),
            ("contact_type", "Vendor Contact - Type"),
            ("email", "Vendor Contact - Email"),
            ("phone", "Vendor Contact - Phone"),
        ),
    },
    "vendor_owner": {
        "label": "Vendor Owner",
        "stage_table": "app_import_stage_vendor_owner",
        "fields": (
            ("vendor_id", "Vendor Owner - Vendor ID"),
            ("owner_user_principal", "Vendor - Business Owner"),
            ("owner_role", "Vendor Owner - Role"),
        ),
    },
    "offering": {
        "label": "Offering",
        "stage_table": "app_import_stage_offering",
        "fields": (
            ("offering_id", "Offering - ID"),
            ("vendor_id", "Offering - Vendor ID"),
            ("offering_name", "Offering - Name"),
            ("offering_type", "Offering - Type"),
            ("lob", "Offering - LOB"),
            ("service_type", "Offering - Service Type"),
            ("lifecycle_state", "Offering - Lifecycle State"),
            ("criticality_tier", "Offering - Criticality Tier"),
        ),
    },
    "offering_owner": {
        "label": "Offering Owner",
        "stage_table": "app_import_stage_offering_owner",
        "fields": (
            ("offering_id", "Offering Owner - Offering ID"),
            ("owner_user_principal", "Offering - Business Owner"),
            ("owner_role", "Offering Owner - Role"),
        ),
    },
    "offering_contact": {
        "label": "Offering Contact",
        "stage_table": "app_import_stage_offering_contact",
        "fields": (
            ("offering_id", "Offering Contact - Offering ID"),
            ("full_name", "Offering Contact - Name"),
            ("contact_type", "Offering Contact - Type"),
            ("email", "Offering Contact - Email"),
            ("phone", "Offering Contact - Phone"),
        ),
    },
    "contract": {
        "label": "Contract",
        "stage_table": "app_import_stage_contract",
        "fields": (
            ("contract_id", "Contract - ID"),
            ("vendor_id", "Contract - Vendor ID"),
            ("offering_id", "Contract - Offering ID"),
            ("contract_number", "Contract - Number"),
            ("contract_status", "Contract - Status"),
            ("start_date", "Contract - Start Date"),
            ("end_date", "Contract - End Date"),
            ("annual_value", "Contract - Annual Value"),
        ),
    },
    "project": {
        "label": "Project",
        "stage_table": "app_import_stage_project",
        "fields": (
            ("project_id", "Project - ID"),
            ("vendor_id", "Project - Vendor ID"),
            ("project_name", "Project - Name"),
            ("project_type", "Project - Type"),
            ("status", "Project - Status"),
            ("start_date", "Project - Start Date"),
            ("target_date", "Project - Target Date"),
            ("owner_principal", "Project - Owner"),
            ("description", "Project - Description"),
        ),
    },
    "invoice": {
        "label": "Invoice",
        "stage_table": "app_import_stage_invoice",
        "fields": (
            ("invoice_id", "Invoice - ID"),
            ("invoice_number", "Invoice - Number"),
            ("invoice_date", "Invoice - Date"),
            ("amount", "Invoice - Amount"),
            ("currency_code", "Invoice - Currency"),
            ("invoice_status", "Invoice - Status"),
            ("notes", "Invoice - Notes"),
            ("vendor_id", "Invoice - Vendor ID"),
            ("vendor_name", "Invoice - Vendor Name"),
            ("offering_id", "Invoice - Offering ID"),
            ("offering_name", "Invoice - Offering Name"),
        ),
    },
    "payment": {
        "label": "Payment",
        "stage_table": "app_import_stage_payment",
        "fields": (
            ("payment_id", "Payment - ID"),
            ("payment_reference", "Payment - Reference"),
            ("payment_date", "Payment - Date"),
            ("amount", "Payment - Amount"),
            ("currency_code", "Payment - Currency"),
            ("payment_status", "Payment - Status"),
            ("notes", "Payment - Notes"),
            ("invoice_id", "Payment - Invoice ID"),
            ("invoice_number", "Payment - Invoice Number"),
            ("vendor_id", "Payment - Vendor ID"),
            ("vendor_name", "Payment - Vendor Name"),
            ("offering_id", "Payment - Offering ID"),
            ("offering_name", "Payment - Offering Name"),
        ),
    },
}

IMPORT_STAGE_TABLE_COLUMN_EXCLUDE = {
    "import_stage_area_row_id",
    "import_job_id",
    "row_index",
    "line_number",
    "area_payload_json",
    "created_at",
}

IMPORT_LAYOUT_FIELD_TARGET_KEYS: dict[str, dict[str, str]] = {
    "vendors": {
        "vendor_id": "vendor.vendor_id",
        "legal_name": "vendor.legal_name",
        "display_name": "vendor.display_name",
        "owner_org_id": "vendor.owner_org_id",
        "lifecycle_state": "vendor.lifecycle_state",
        "risk_tier": "vendor.risk_tier",
        "support_contact_name": "vendor_contact.full_name",
        "support_contact_type": "vendor_contact.contact_type",
        "support_email": "vendor_contact.email",
        "support_phone": "vendor_contact.phone",
    },
    "offerings": {
        "offering_id": "offering.offering_id",
        "vendor_id": "offering.vendor_id",
        "vendor_name": "vendor.display_name",
        "vendor_contact_email": "vendor_contact.email",
        "vendor_support_phone": "vendor_contact.phone",
        "offering_name": "offering.offering_name",
        "offering_type": "offering.offering_type",
        "lob": "offering.lob",
        "service_type": "offering.service_type",
        "lifecycle_state": "offering.lifecycle_state",
        "criticality_tier": "offering.criticality_tier",
    },
    "projects": {
        "project_id": "project.project_id",
        "vendor_id": "project.vendor_id",
        "project_name": "project.project_name",
        "project_type": "project.project_type",
        "status": "project.status",
        "start_date": "project.start_date",
        "target_date": "project.target_date",
        "owner_principal": "project.owner_principal",
        "description": "project.description",
    },
    "invoices": {
        "invoice_id": "invoice.invoice_id",
        "invoice_number": "invoice.invoice_number",
        "invoice_date": "invoice.invoice_date",
        "amount": "invoice.amount",
        "currency_code": "invoice.currency_code",
        "invoice_status": "invoice.invoice_status",
        "notes": "invoice.notes",
        "vendor_id": "invoice.vendor_id",
        "vendor_name": "invoice.vendor_name",
        "offering_id": "invoice.offering_id",
        "offering_name": "invoice.offering_name",
    },
    "payments": {
        "payment_id": "payment.payment_id",
        "payment_reference": "payment.payment_reference",
        "payment_date": "payment.payment_date",
        "amount": "payment.amount",
        "currency_code": "payment.currency_code",
        "payment_status": "payment.payment_status",
        "notes": "payment.notes",
        "invoice_id": "payment.invoice_id",
        "invoice_number": "payment.invoice_number",
        "vendor_id": "payment.vendor_id",
        "vendor_name": "payment.vendor_name",
        "offering_id": "payment.offering_id",
        "offering_name": "payment.offering_name",
    },
}


def _dynamic_import_field_label(*, area_label: str, field_key: str) -> str:
    cleaned = str(field_key or "").strip().replace("_", " ")
    cleaned = " ".join([part for part in cleaned.split(" ") if part])
    if not cleaned:
        cleaned = str(field_key or "").strip()
    return f"{area_label} - {cleaned.title()}"


def import_dynamic_field_catalog(repo) -> dict[str, list[str]]:
    if repo is None or not hasattr(repo, "list_import_stage_table_columns"):
        return {}
    try:
        table_columns = repo.list_import_stage_table_columns()
    except Exception:
        return {}
    out: dict[str, list[str]] = {}
    for area_key, spec in IMPORT_STAGING_AREAS.items():
        table_name = str(spec.get("stage_table") or "").strip()
        if not table_name:
            continue
        columns = [str(item).strip().lower() for item in list(table_columns.get(table_name) or []) if str(item).strip()]
        dynamic_keys = [
            col
            for col in columns
            if col not in IMPORT_STAGE_TABLE_COLUMN_EXCLUDE
        ]
        if dynamic_keys:
            out[str(area_key)] = dynamic_keys
    return out


def import_target_field_options(*, dynamic_field_catalog: dict[str, list[str]] | None = None) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for area_key, spec in IMPORT_STAGING_AREAS.items():
        area_label = str(spec.get("label") or area_key.title())
        stage_table = str(spec.get("stage_table") or "")
        static_fields = [(str(field_key), str(field_label)) for field_key, field_label in list(spec.get("fields") or [])]
        field_rows: list[tuple[str, str]] = list(static_fields)
        seen_field_keys = {field_key for field_key, _ in static_fields}
        for dynamic_key in list((dynamic_field_catalog or {}).get(str(area_key), []) or []):
            key = str(dynamic_key or "").strip().lower()
            if not key or key in seen_field_keys:
                continue
            field_rows.append((key, _dynamic_import_field_label(area_label=area_label, field_key=key)))
            seen_field_keys.add(key)
        for field_key, field_label in field_rows:
            options.append(
                {
                    "key": f"{area_key}.{field_key}",
                    "label": str(field_label),
                    "area_key": area_key,
                    "area_label": area_label,
                    "stage_table": stage_table,
                    "field_key": str(field_key),
                }
            )
    return options


def import_target_field_groups(*, dynamic_field_catalog: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    options = import_target_field_options(dynamic_field_catalog=dynamic_field_catalog)
    for area_key, spec in IMPORT_STAGING_AREAS.items():
        group_options = [item for item in options if str(item.get("area_key") or "") == area_key]
        groups.append(
            {
                "area_key": area_key,
                "area_label": str(spec.get("label") or area_key.title()),
                "stage_table": str(spec.get("stage_table") or ""),
                "options": group_options,
            }
        )
    return groups

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
    "invoices": {
        "label": "Invoices",
        "description": (
            "Stage and apply offering invoices. If the vendor/offering is missing, "
            "rows remain blocked until dependencies exist."
        ),
        "fields": [
            "invoice_id",
            "invoice_number",
            "invoice_date",
            "amount",
            "currency_code",
            "invoice_status",
            "notes",
            "vendor_id",
            "vendor_name",
            "offering_id",
            "offering_name",
        ],
        "sample_rows": [
            {
                "invoice_id": "",
                "invoice_number": "INV-2026-0001",
                "invoice_date": "2026-02-01",
                "amount": "12500.00",
                "currency_code": "USD",
                "invoice_status": "received",
                "notes": "Initial monthly charge.",
                "vendor_id": "vnd-70231",
                "vendor_name": "Blue Ridge Procurement",
                "offering_id": "",
                "offering_name": "Procurement Platform",
            }
        ],
    },
    "payments": {
        "label": "Payments",
        "description": (
            "Stage and apply payment events. Payments depend on invoice availability and "
            "are reprocessed when matching invoices become available."
        ),
        "fields": [
            "payment_id",
            "payment_reference",
            "payment_date",
            "amount",
            "currency_code",
            "payment_status",
            "notes",
            "invoice_id",
            "invoice_number",
            "vendor_id",
            "vendor_name",
            "offering_id",
            "offering_name",
        ],
        "sample_rows": [
            {
                "payment_id": "",
                "payment_reference": "PMT-2026-101",
                "payment_date": "2026-02-15",
                "amount": "12500.00",
                "currency_code": "USD",
                "payment_status": "settled",
                "notes": "ACH settlement batch.",
                "invoice_id": "",
                "invoice_number": "INV-2026-0001",
                "vendor_id": "vnd-70231",
                "vendor_name": "Blue Ridge Procurement",
                "offering_id": "",
                "offering_name": "Procurement Platform",
            }
        ],
    },
}
