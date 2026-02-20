# Imports Bundles Operations

This guide covers the multi-file Imports wizard for supplier, invoice, and payment feeds.

## Supported Upload Modes

1. Single file (`file`)
1. Multiple files (`files[]`)
1. ZIP bundle (`bundle_file`)

The wizard stages each parsed file as its own import job and keeps a bundle summary in one preview session.

## File Classification

The importer classifies bundle files by filename hints:

1. `supplier` or `vendor` -> `vendors`
1. `invoice` -> `invoices`
1. `payment` -> `payments`
1. `offering` -> `offerings`
1. `project` -> `projects`
1. fallback -> selected layout

## Dependency Rules

1. Vendors can apply immediately.
1. Invoices require vendor and offering resolution.
1. Payments require invoice resolution.
1. Rows with missing dependencies remain `blocked`.

## Apply Modes

1. `Stage Only`: keeps all staged rows, no core writes.
1. `Apply Eligible Now`: runs bundle apply in dependency order:
   1. vendors
   1. offerings
   1. projects
   1. invoices
   1. payments
1. `Reprocess Blocked`: retries blocked rows after upstream records exist.

## Idempotency Behavior

1. Existing invoices are matched by invoice keys before insert.
1. Existing payments are matched by payment/invoice keys before insert.
1. Duplicate payloads return merge-style status and do not insert duplicates.

## Notes

1. Bundle remap is intentionally disabled in this view; use single-file wizard remap for manual source-to-target remapping.
1. Payment writes depend on `app_offering_payment` table availability in the runtime schema.
