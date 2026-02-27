## Overview
This PR now includes the full RBAC rollout plus Help Center implementation and follow-up stability fixes. Scope has expanded beyond the original PR Bundle 2 demo.

## What Changed
- Full RBAC decorator rollout across remaining mutation endpoints
- Added/expanded permission mappings (including admin and help actions)
- Added Help Center feature set:
  - article index/detail routes
  - markdown rendering + sanitization
  - feedback + issue capture endpoints
  - seeded help content and supporting SQL
- Restored repository compatibility exports for runtime imports
- Fixed malformed decorator lines in router modules
- Added RBAC context fallback in decorator enforcement
- Updated help validator behavior and aligned help test expectations

## Security/Guardrails
- RBAC coverage gate is passing for detected mutation endpoints
- Missing permission checks identified during validation were fixed in admin/contracts endpoints

## Validation
- ✅ `D:/VendorCatalog/.venv/Scripts/python.exe -m pytest tests/test_help_center.py -q` (5 passed)
- ✅ `D:/VendorCatalog/.venv/Scripts/python.exe -m pytest tests/test_rbac_coverage.py -q` (2 passed)

## Notes
- This PR supersedes the original narrow description ("5 example endpoints").
- Branch: `feature/rbac-pattern-demo`
- Latest fix commit: `ab67e88`
