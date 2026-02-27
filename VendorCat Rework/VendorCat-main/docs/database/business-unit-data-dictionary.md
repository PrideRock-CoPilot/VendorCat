# Business Unit Data Dictionary And Controlled Vocabulary

## Controlled Lookup Domains

| Domain | Lookup Type | Required For | Notes |
|---|---|---|---|
| Business Unit | `offering_business_unit` / `owner_organization` | Vendor + Offering ownership/assignment | Governed list, no free-form creation in runtime forms |
| Vendor Category | `vendor_category` | Vendor | Governed |
| Compliance Category | `compliance_category` | Vendor | Governed |
| GL Category | `gl_category` | Vendor | Governed |
| Lifecycle State | `lifecycle_state` | Vendor + Offering + Project | Governed |
| Risk Tier | `risk_tier` | Vendor | Governed |
| Offering Type | `offering_type` | Offering | Governed |
| Service Type | `offering_service_type` | Offering | Governed |
| Contact Type | `contact_type` | Vendor/Offering contacts | Governed |
| Owner Role | `owner_role` | Vendor/Offering owner assignments | Governed |

## Canonical Entity Fields

### `vendor`

| Field | Type | Description |
|---|---|---|
| `vendor_id` | string | Stable vendor identifier |
| `legal_name` | string | Legal entity name |
| `display_name` | string | Display label |
| `lifecycle_state_id` | string | FK to lifecycle lookup |
| `risk_tier_id` | string | FK to risk lookup |
| `primary_business_unit_id` | string | Primary BU FK |
| `primary_owner_organization_id` | string | Primary owner organization FK |
| `vendor_category_id` | string | FK to vendor category lookup |
| `compliance_category_id` | string | FK to compliance category lookup |
| `gl_category_id` | string | FK to GL category lookup |
| `delegated_vendor_flag` | boolean | Delegated vendor indicator |
| `health_care_vendor_flag` | boolean | Healthcare vendor indicator |

### `offering`

| Field | Type | Description |
|---|---|---|
| `offering_id` | string | Stable offering identifier |
| `vendor_id` | string | FK to vendor |
| `offering_name` | string | Offering name |
| `lifecycle_state_id` | string | FK to lifecycle lookup |
| `primary_business_unit_id` | string | Primary BU FK |
| `primary_service_type_id` | string | FK to service type lookup |

### Assignment Crosswalks

| Table | Key Fields | Purpose |
|---|---|---|
| `vendor_business_unit_assignment` | `vendor_id`, `business_unit_id`, `active_flag` | Vendor-to-BU many-to-many mapping |
| `offering_business_unit_assignment` | `offering_id`, `business_unit_id`, `active_flag` | Offering-to-BU many-to-many mapping |

## API Contract Guidance

- API contracts should expose Business Unit semantics only.
- Incoming payload key `lob` is invalid and must be rejected.
- Multi-select contracts should use `business_unit_ids: string[]`.
- Governed fields must resolve to lookup-managed options.
