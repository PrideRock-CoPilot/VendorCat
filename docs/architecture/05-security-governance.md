# Security And Governance

## Authentication
- No app login page.
- Authentication is Databricks SSO only.
- App identity context comes from Databricks credentials (`current_user()` and group membership).

## Authorization Roles
- `vendor_admin`: manage permissions, policies, and full data administration.
- `vendor_steward`: approve changes and resolve data quality issues.
- `vendor_editor`: create and edit vendor records through workflow.
- `vendor_viewer`: read-only access to approved limited views.
- `vendor_auditor`: read access to history and audit datasets.

## Default Access Behavior
- Users without explicit entitlement are restricted to limited read-only views.
- Write operations require role grant plus LOB scope mapping.
- Sensitive fields are masked unless role and purpose both permit access.

## Single-Schema Permission Model (`twvendor`)
- Grant schema `USAGE` to all permitted roles.
- Restrict direct table access for end users.
- Expose `rpt_` secure views for normal app reads.
- Keep `src_`, `hist_`, and `audit_` direct access limited to admins/auditors.

## Permission Tables
- `sec_user_role_map(user_principal, role_code, active_flag, granted_by, granted_at, revoked_at)`
- `sec_user_org_scope(user_principal, org_id, scope_level, active_flag)`
- `sec_role_permission(role_code, object_name, action_code, active_flag)`

## Row And Column Control
- Row filtering by LOB scope from `sec_user_org_scope`.
- Masking for tax ID, banking, and personal contact fields.
- Audit all access to restricted columns and admin permission changes.

## Audit And Compliance
- Store immutable change events in `audit_entity_change`.
- Store workflow actions in `audit_workflow_event`.
- Store privileged access and role updates in `audit_access_event`.
- Run quarterly entitlement recertification and exception review.
