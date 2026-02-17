# Screen-By-Screen UX Audit

Audit date: February 12, 2026

Evidence:
- `artifacts/ux_audit/click_audit_summary.json`
- `artifacts/ux_audit/*.png`

## 1. Click Audit Results

| Flow | Clicks | Target | Pass |
|---|---:|---:|---|
| Create vendor with new line of business | 3 | <= 6 | Yes |
| Create offering with LOB/service type | 4 | <= 6 | Yes |
| Add invoice | 2 | <= 3 | Yes |
| Create project with owner and links | 5 | <= 6 | Yes |
| Run report | 1 | <= 3 | Yes |
| Grant group role | 2 | <= 3 | Yes |
| Change group role | 2 | <= 3 | Yes |
| Revoke group role | 1 | <= 3 | Yes |
| Record contract cancellation | 1 | <= 3 | Yes |
| Save demo outcome | 1 | <= 3 | Yes |

Summary:
- All audited core flows are within click budget.
- Main UX risk is not click count. Main risk is discoverability and field clarity.

## 2. Screen Findings

## Dashboard
- What works:
  - Clear landing page with strong high-level metrics.
- Improve:
  - Add fast action buttons (`New Vendor`, `New Project`) near top.

## Vendor 360 List
- What works:
  - Strong filtering and sortable list.
  - Row click behavior is fast.
- Improve:
  - Add clearer empty-state helper text when no vendors exist.
  - Expose one-click quick actions on row hover (`Open`, `Offerings`).

## New Vendor
- What works:
  - New line-of-business path works in empty environments.
  - Good validation for required fields.
- Improve:
  - Add short inline examples for LOB format.
  - Clarify `Line of Business` business meaning with one sentence.

## Vendor Summary
- What works:
  - Key metrics are visible.
  - Section navigation is present.
- Improve:
  - Important add actions are hidden in `<details>` blocks.
  - Surface `Add Document` and `Add Owner` as visible primary buttons.

## Vendor Ownership
- What works:
  - Owner/user search typeahead is available.
- Improve:
  - Add/remove actions are split across blocks and hidden toggles.
  - Show concise helper text near each add form.

## Vendor Offerings
- What works:
  - Good overview table and unassigned map flows.
- Improve:
  - Mapping forms become dense with many rows.
  - Add bulk mapping mode for unassigned contracts/demos.

## Offering Detail
- What works:
  - Strong section navigation and financial view.
  - Invoice workflow is quick.
- Improve:
  - Very long page depth in some sections.
  - Add sticky section nav on long pages.

## Projects List / New Project
- What works:
  - Owner search and multi-link picker are effective.
  - Vendor/offering link flow is efficient.
- Improve:
  - Add clearer chip remove affordance text (not just `x`).
  - Add guidance when no offerings found for selected vendor.

## Project Detail
- What works:
  - Sectioned layout is clear.
  - Quick actions are useful.
- Improve:
  - Add breadcrumb trail for deep project subpages.
  - Standardize return behavior to avoid context loss.

## Contracts
- What works:
  - Fast entry flow for cancellation.
- Improve:
  - Inputs are raw IDs only.
  - Add typeahead pickers for contract, vendor, offering references.

## Demos
- What works:
  - Fast form and list on one page.
- Improve:
  - Inputs are raw IDs only.
  - Add vendor/offering search pickers and optional project picker.

## Reports
- What works:
  - Full flexibility for filters and output modes.
  - Download/export options are visible.
- Improve:
  - Form is dense and can overwhelm new users.
  - Add `Basic Filters` and `Advanced Filters` split.

## Imports
- What works:
  - Clear upload -> preview -> apply model.
  - Template downloads are useful.
- Improve:
  - Preview table can become hard to scan.
  - Add row status color badges and bulk action controls.

## Admin
- What works:
  - Role/group controls are present and functional.
  - Group role lifecycle is good.
- Improve:
  - Major actions hidden in `<details>`.
  - Add explicit revoke for user roles and LOB scopes in tables.
  - Convert free-text principals to searchable inputs where possible.

## Pending Approvals
- What works:
  - Strong filtering and structured review page.
- Improve:
  - No quick triage action on list rows.
  - Add `Open Next Pending` and queue shortcuts.

## 3. Main UX Theme

The product is now functionally strong and click-efficient.
The next gains come from reducing cognitive load:

1. Show important actions without hidden expanders.
1. Replace raw IDs with search pickers where possible.
1. Split complex forms into basic and advanced views.
