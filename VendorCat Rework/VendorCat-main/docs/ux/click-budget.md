# Click Budget And Task Depth

This page defines a practical click rule for Vendor Catalog.

## 1. The Rule

There is no strict "3-click law" in UX.
People care more about speed and clarity than exact click count.

Use this rule instead:

1. Simple lookup task: target `<= 3` clicks.
1. Normal create/update task: target `<= 6` clicks.
1. Complex admin task: target `<= 8` clicks.
1. Any frequent task over the target should be redesigned.

## 2. How To Count Clicks

1. Start counting after the page is loaded.
1. Count button clicks, tab clicks, dropdown choices, and row action clicks.
1. Do not count typing.
1. Do not count browser back/forward.

## 3. Current Core Flows

These counts are from current production-like flow checks.

1. Create vendor with existing line of business: `3` clicks.
1. Create vendor with new line of business: `4` clicks.
1. Create offering from a vendor: `3` clicks.
1. Add invoice in offering financials: `3` clicks.
1. Create project with owner + links: `6` clicks.
1. Grant group role: `3` clicks.
1. Change group role in table: `2` clicks.
1. Revoke group role in table: `1` click.

## 4. Alert Thresholds

Add a UX backlog item when any of the below is true:

1. A daily task takes more than `6` clicks.
1. A task needs more than one page reload to complete.
1. A task requires hidden controls to be discovered first.
1. A new user cannot finish a task on first try.

## 5. Design Moves To Reduce Clicks

1. Keep primary actions visible without opening accordions.
1. Use search-as-you-type for large lists.
1. Keep related actions on the same page when safe.
1. Pre-fill common defaults.
1. Do not split one simple action across many pages.

## 6. Validation Cadence

1. Re-check click counts after every major UI change.
1. Re-check before each release candidate.
1. Track pass/fail in UI validation artifacts.

Related docs:
- `docs/ux/screen-audit.md`
- `docs/ux/prioritized-backlog.md`
