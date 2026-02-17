from __future__ import annotations

import pathlib
import subprocess
import textwrap

repo = pathlib.Path(r"D:/VendorCatalog")
body = textwrap.dedent(
    """## Overview
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
"""
)

body_file = repo / "pr3_body.md"
body_file.write_text(body, encoding="utf-8")

cmd = [
    "gh",
    "pr",
    "edit",
    "3",
    "--title",
    "RBAC Full Rollout + Help Center + Stability Fixes",
    "--body-file",
    str(body_file),
]
result = subprocess.run(cmd, cwd=repo, text=True, capture_output=True)
print(result.stdout)
print(result.stderr)
raise SystemExit(result.returncode)
