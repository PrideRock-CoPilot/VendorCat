# Legacy To Canonical Field Mapping (LOB -> Business Unit)

## Core Mapping Principles

- Legacy `LOB` becomes canonical `Business Unit`.
- Runtime imports stage first, then apply.
- Unknown governed values never write directly; they go to lookup-candidate review.

## Field Mapping Table

| Legacy Source Field | Canonical Target |
|---|---|
| `Supplier_ID` | `vendor.vendor_id` |
| `Supplier_Name` | `vendor.legal_name` |
| `Vendor_Category` | `vendor.vendor_category_id` (lookup-resolved) |
| `Compliance Category` | `vendor.compliance_category_id` (lookup-resolved) |
| `GL Category` | `vendor.gl_category_id` (lookup-resolved) |
| `Delegated Vendor` | `vendor.delegated_vendor_flag` |
| `Health Care Vendor` | `vendor.health_care_vendor_flag` |
| `LOB` or BU flag column | `vendor_business_unit_assignment.business_unit_id` |
| `Offering LOB` | `offering_business_unit_assignment.business_unit_id` |
| Contact columns (`Contact_1_*`, etc.) | `vendor_contact` / `offering_contact` rows |
| `Notes` | `app_note` (`note_type=import_note`) |

## BU Crosswalk Rules

1. Resolve incoming BU label/code to `lkp_business_unit`.
2. Insert assignment row with source traceability:
   - `source_system`
   - `source_key`
3. Enforce unique active assignment per entity + BU.
4. Preserve one primary BU per entity context where required.

## Reject Rules

- Reject payload keys named `lob` (explicit validation error).
- Reject free-form governed values at apply time.
- Route unknown lookup values to `app_import_lookup_candidate` for approval workflow.
