# Prioritized UX Backlog

Audit basis:
- `docs/ux/screen-audit.md`
- `artifacts/ux_audit/click_audit_summary.json`

Priority scale:
- `P0`: high user friction or missing expected control
- `P1`: meaningful usability improvement
- `P2`: polish and consistency

Size:
- `S`: <= 1 day
- `M`: 2-4 days
- `L`: 5+ days

## P0 Items

## UX-001: Replace Raw ID Inputs In Contracts
- Priority: `P0`
- Size: `M`
- Area: `Contracts`
- Status: `Done (2026-02-12)`
- Problem:
  - Cancellation form uses raw `contract_id` text only.
- Change:
  - Add typeahead search for contract with auto-fill of related vendor/offering context.
- Acceptance:
  - User can search contract by number/id/name fragments.
  - Selected contract id is submitted without manual id copy/paste.

## UX-002: Replace Raw ID Inputs In Demos
- Priority: `P0`
- Size: `M`
- Area: `Demos`
- Status: `Done (2026-02-12)`
- Problem:
  - Demo form requires raw vendor/offering IDs.
- Change:
  - Add typeahead pickers for vendor and offering.
- Acceptance:
  - User can select vendor/offering from search list.
  - Manual id typing is optional, not required.

## UX-003: Add Revoke For User Roles And LOB Scopes
- Priority: `P0`
- Size: `M`
- Area: `Admin`
- Status: `Done (2026-02-12)`
- Problem:
  - User role/scope tables do not expose complete lifecycle actions in-row.
- Change:
  - Add `Revoke` action in user role grant rows and LOB scope grant rows.
- Acceptance:
  - Active grants can be revoked from table without SQL or external tools.
  - Audit trail captures revoke actor and timestamp.

## UX-004: Surface Primary Add Actions Without Hidden Details
- Priority: `P0`
- Size: `M`
- Area: `Vendor Summary`, `Vendor Ownership`, `Admin`
- Status: `Done (2026-02-12)`
- Problem:
  - Critical actions are hidden in `<details>` blocks.
- Change:
  - Show top 1-2 primary actions as always-visible buttons.
- Acceptance:
  - New user can find add/grant actions without expanding hidden sections.

## P1 Items

## UX-005: Split Reports Into Basic vs Advanced Filters
- Priority: `P1`
- Size: `M`
- Area: `Reports`
- Status: `Done (2026-02-12)`
- Problem:
  - One large filter form is visually heavy.
- Change:
  - Show a small default filter set and hide advanced options behind toggle.
- Acceptance:
  - First-time user can run a report with no confusion in under 30 seconds.

## UX-006: Add Breadcrumbs On Deep Pages
- Priority: `P1`
- Size: `S`
- Area: `Vendor`, `Offering`, `Project` detail pages
- Status: `Done (2026-02-13)`
- Problem:
  - Back navigation depends on `return_to` and can be unclear.
- Change:
  - Add breadcrumb line (for example `Vendor 360 / Vendor / Offering / Financials`).
- Acceptance:
  - Users can move up one level without losing context.

## UX-007: Add Bulk Mapping For Unassigned Records
- Priority: `P1`
- Size: `L`
- Area: `Vendor Offerings`
- Status: `Done (2026-02-13)`
- Problem:
  - Mapping unassigned contracts/demos row by row is slow at scale.
- Change:
  - Add multi-select + bulk map action.
- Acceptance:
  - User can map many rows to one offering in one submit.

## UX-008: Improve Import Preview Readability
- Priority: `P1`
- Size: `M`
- Area: `Imports`
- Status: `Done (2026-02-13)`
- Problem:
  - Large preview tables are hard to scan quickly.
- Change:
  - Add row status badges, sticky headers, and bulk action defaults.
- Acceptance:
  - Validation errors are visually clear within first screen view.

## UX-009: Add Quick Triage In Pending Approvals
- Priority: `P1`
- Size: `M`
- Area: `Pending Approvals`
- Status: `Done (2026-02-13)`
- Problem:
  - Triage requires opening each request.
- Change:
  - Add `Open Next Pending` and optional inline quick decision shortcuts.
- Acceptance:
  - Approver can process queue faster with fewer context switches.

## P2 Items

## UX-010: Improve Chip Remove Accessibility Text
- Priority: `P2`
- Size: `S`
- Area: `Project New`
- Status: `Done (2026-02-13)`
- Problem:
  - Chip remove control appears as `x` only.
- Change:
  - Add aria-label and visible tooltip text (`Remove Vendor`, `Remove Offering`).
- Acceptance:
  - Remove controls are obvious to keyboard and assistive users.

## UX-011: Add Empty-State CTA Blocks
- Priority: `P2`
- Size: `S`
- Area: `Vendor list`, `Projects`, `Offerings`, `Approvals`
- Status: `Done (2026-02-13)`
- Problem:
  - Some empty states do not suggest next steps.
- Change:
  - Add one-line guidance + direct action link.
- Acceptance:
  - Empty pages always suggest the next action.

## UX-012: Add Sticky Section Nav On Long Detail Pages
- Priority: `P2`
- Size: `M`
- Area: `Offering Detail`, `Project Detail`
- Status: `Done (2026-02-13)`
- Problem:
  - Long scroll pages make section jumping harder.
- Change:
  - Keep section nav visible as user scrolls.
- Acceptance:
  - User can switch sections without scrolling back to top.

## Suggested Delivery Order

1. `UX-001`, `UX-002`, `UX-003`, `UX-004`
1. `UX-005`, `UX-006`, `UX-009`
1. `UX-007`, `UX-008`, `UX-010`, `UX-011`, `UX-012`
