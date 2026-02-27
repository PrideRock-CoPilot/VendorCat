# Imports Dummy Files

This folder contains dummy ingestion files for manual testing of the Imports tab.

## Quick Upload (strict approved layouts)

Use these with `flow_mode=quick` (or Quick Upload UI):

- `quick/vendors_approved_template.csv`
- `quick/offerings_approved_template.tsv`
- `quick/projects_approved_template.csv`

These files match approved layout headers exactly and should pass strict layout checks.

## Advanced Wizard (mixed/extended layouts)

Use these with wizard mode:

- `wizard/vendors_with_contracts_extra.csv` (`csv`)
- `wizard/offerings_with_contracts_extra.tsv` (`tsv`)
- `wizard/vendors_contracts_contacts.json` (`json`)
- `wizard/vendors_contracts_contacts.xml` (`xml`)

These include additional contract/contact/governance fields that are not directly mapped in current app layouts.

## Extra Fields To Capture As Notes

Current app import layouts do not have direct targets for fields like:

- `contract_number`, `contract_status`, `contract_start_date`, `contract_end_date`
- `annual_contract_value`, `currency`
- `renewal_terms`, `termination_notice_days`, `auto_renew`
- `security_review_notes`, `onboarding_blockers`, `integration_dependencies`
- `data_classification`, `primary_data_steward`

Suggested handling for now:

1. Keep canonical fields mapped through normal import rows.
2. Preserve extra fields in stage payload.
3. Write a structured note (JSON text) to `app_note` or entity-specific note tables after import apply.
