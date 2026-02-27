# Vendor Catalog User Guide

This guide is written in simple steps.
Use it when you are doing real work in the app.

## 1. Before You Start

1. Open `http://localhost:8000/dashboard`.
1. Check the top bar.
1. Make sure your role is shown.

If you do not see the page you need, you may not have the right role yet.

## 2. Quick Map Of The App

1. `Dashboard` shows high-level numbers.
1. `Vendor 360` is where you add and manage vendors.
1. `Projects` is where you manage projects.
1. `Contracts` and `Demos` track contract and demo events.
1. `Reports` lets you view and export data.
1. `Admin` is for role and settings management.

## 3. Task: Add A New Vendor

1. Click `Vendor 360`.
1. Click `+ New Vendor`.
1. Fill `Legal Name`.
1. Fill `Display Name` if needed.
1. Pick `Line of Business (LOB)`.
1. If no LOB exists, pick `+ Add new line of business` and type a new LOB value.
1. Click `Create Vendor`.

Done:
- You should land on the new vendor page.
- You should see a success message with the new vendor id.

## 4. Task: Add An Offering To A Vendor

1. Open the vendor.
1. Go to `Offerings`.
1. Click `+ New Offering`.
1. Fill `Offering Name`.
1. Pick `LOB`.
1. Pick `Service Type`.
1. Click `Create Offering`.

Tip:
- Fill `LOB` and `Service Type` every time.
- These values drive summary cards and reporting.

## 5. Task: Log An Invoice (Actual Spend)

1. Open the offering.
1. Open section `Financials`.
1. In `Add Invoice`, fill date and amount.
1. Add invoice number if you have one.
1. Click `Add Invoice`.

Done:
- The invoice appears in `Invoice Ledger`.
- Budget vs actual values update.

## 6. Task: Create A Project And Link Items

1. Click `Projects`.
1. Click `Create Project`.
1. Fill `Project Name`.
1. In `Owner Principal`, type email, first name, or last name.
1. Click a user from the search list.
1. Add linked vendors and offerings if needed.
1. Click `Create Project`.

## 7. Task: Manage Roles By Group

1. Click `Admin`.
1. Go to `Group Role Grants`.
1. To grant:
   Click `Grant Group Role`, fill group, pick role, click `Grant Group Role`.
1. To change:
   Pick a new role in the row dropdown and click `Change`.
1. To remove:
   Click `Revoke` in the row.

## 8. Common Errors And Fixes

1. Error: `Validation failed` when creating vendor.
   Fix:
   Fill `Legal Name` and make sure a line of business is selected or typed.
1. Error: You cannot edit.
   Fix:
   Check role grants in `Admin`.
   Check if app is in locked mode.
1. Error: Owner/user search returns nothing.
   Fix:
   Confirm user directory sync and identity headers are set in your environment.

## 9. Click Rule (Simple)

There is no hard law that everything must be exactly 3 clicks.
The better rule is:

1. Easy tasks should be about 3 clicks after opening the page.
1. Normal create tasks should be about 4 to 6 clicks.
1. If a task takes more than 7 clicks, redesign it.

Full click budget and current flow counts:
- `docs/ux/click-budget.md`

## 10. Topics That Need Bigger Docs

1. Roles and approval rules by role type.
1. Databricks identity headers and group mapping.
1. Imports file format and data mapping rules.
1. Financial alert thresholds and governance rules.
1. Production deployment and secret handling.
