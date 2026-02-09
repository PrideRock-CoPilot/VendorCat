# Application Architecture

## Platform
- Build with Databricks Apps.
- Use serverless SQL warehouse for app query workloads.
- Use Unity Catalog secured views and controlled write tables in `twvendor`.

## Authentication And Session
- No custom login page.
- Users access through Databricks SSO.
- App resolves identity and permissions from Databricks user context.

## Interface Requirements
- Clean modern UI with task-focused pages and consistent navigation.
- Fast global search for vendor, offering, contract, and owner.
- Timeline view for changes, approvals, and audit history.

## Modules
- Vendor 360: profile, ownership, contacts, offerings/applications.
- Onboarding and Edit Requests: create, validate, submit, and track changes.
- Demo Evaluation: score vendors, capture non-selection reasons and notes.
- Contract Lifecycle: contract status, cancellation reasons, and notes.
- Projects Workspace: standalone project lifecycle, linked vendors/offerings, demos, docs, and notes.
- Reports Workspace: custom filtered reports, CSV extracts, and queued email extract requests.
- Admin Permissions: assign role and org scope mappings.
- Audit Explorer: read-only timeline for entity and access events.

## Role-Based Experience
- `vendor_admin`: full admin and permission management screens.
- `vendor_editor` and `vendor_steward`: edit-capable workflows in allowed scope.
- `vendor_viewer`: read-only limited screens with masked sensitive fields.
- `vendor_auditor`: read-only plus full historical and audit visibility.

## Write Path And Integrity
- All edits are request-driven and validated.
- Approved edits update `core_`, append `hist_`, and append `audit_`.
- Direct user updates to `src_` are blocked.
