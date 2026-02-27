# Phase 0 Baseline Freeze

This folder captures the frozen baseline for the Django clean-slate rebuild branch.

## Scope
- Existing FastAPI implementation is reference-only in this branch.
- Rebuild work lives under `src/`.
- Baseline metrics are captured from repository state on 2026-02-20.

## Baseline Facts
- Local tests: 222 passed / 5 failed (imports integration + RBAC coverage)
- Coverage: 64.24%
- Ruff: 282 issues
- Mypy: 1561 issues
- Route inventory: 203 total routes, 110 mutation routes
- SQL inventory: 225 SQL files under runtime SQL catalog

## Artifacts
- `route_inventory.md`
- `test_inventory.md`
- `sql_inventory.md`
- `feature_checklist.md`
- `ux_screen_inventory.md`

## Current Execution Status
See `docs/rebuild/IMPLEMENTATION_STATUS.md` for active phase completion and pending work.
