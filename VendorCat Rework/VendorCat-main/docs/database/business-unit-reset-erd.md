# Business Unit Canonical ERD

This ERD defines the canonical Business Unit model and the import governance path.

```mermaid
erDiagram
    vendor ||--o{ vendor_business_unit_assignment : assigned_to
    offering ||--o{ offering_business_unit_assignment : assigned_to
    vendor ||--o{ offering : provides

    lkp_business_unit ||--o{ vendor_business_unit_assignment : lookup
    lkp_business_unit ||--o{ offering_business_unit_assignment : lookup

    vendor ||--o{ vendor_contact : has
    offering ||--o{ offering_contact : has
    lkp_contact_type ||--o{ vendor_contact : typed_by
    lkp_contact_type ||--o{ offering_contact : typed_by

    custom_attribute_definition ||--o{ custom_attribute_value : defines

    app_import_job ||--o{ app_import_stage_row : stages
    app_import_job ||--o{ app_import_lookup_candidate : proposes
    app_lookup_option ||--o{ app_import_lookup_candidate : approved_into

    vendor {
      string vendor_id PK
      string legal_name
      string display_name
      string lifecycle_state_id
      string risk_tier_id
      string primary_business_unit_id
      string primary_owner_organization_id
    }

    offering {
      string offering_id PK
      string vendor_id FK
      string offering_name
      string lifecycle_state_id
      string primary_business_unit_id
      string primary_service_type_id
    }

    vendor_business_unit_assignment {
      string assignment_id PK
      string vendor_id FK
      string business_unit_id FK
      string source_system
      string source_key
      datetime effective_start_at
      datetime effective_end_at
      bool is_primary
      bool active_flag
    }

    offering_business_unit_assignment {
      string assignment_id PK
      string offering_id FK
      string business_unit_id FK
      string source_system
      string source_key
      datetime effective_start_at
      datetime effective_end_at
      bool is_primary
      bool active_flag
    }

    app_import_lookup_candidate {
      string candidate_id PK
      string import_job_id FK
      string lookup_type
      string option_code
      string option_label
      string status
      string reviewed_by
      datetime reviewed_at
    }
```

## Notes

- `vendor_business_unit_assignment` and `offering_business_unit_assignment` are the BU crosswalk tables and retain source traceability via `source_system` + `source_key`.
- Owner Organization remains a separate governed dimension from Business Unit.
- Import writes flow through staging and lookup-candidate approval before apply.
