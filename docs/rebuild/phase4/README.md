# Phase 4 Parity Plan

This phase covers parity behavior for vendor, offering, project, contract, demo, and documentation surfaces.

## Scope
- Vendor lifecycle parity (create/update/state transitions, owner org, risk tier)
- Offering lifecycle parity (create/update/state transitions, vendor linkage)
- Project lifecycle parity (create/update/state transitions, ownership)
- Contract/document parity (linkage, metadata, state transitions)
- Demo catalog parity (create/update/state transitions)

## Approach
- Implement API endpoints and UI flows in `src/apps/*` with permission enforcement.
- Add rebuild tests in `tests_rebuild/` for CRUD and parity flows.
- Extend schema and SQL adapters only as required for parity gaps.

## Exit Criteria
- Rebuild tests cover vendor, offering, project, contract, demo, and doc flows.
- Permission checks exist for all mutation endpoints.
- Status update in `docs/rebuild/IMPLEMENTATION_STATUS.md`.
