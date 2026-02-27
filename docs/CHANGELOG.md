# Changelog

## 2026-02-27 | Single-track consolidation
- Canonical track finalized as `src` + `tests_rebuild`.
- Removed non-canonical legacy runtime tree from mainline.
- Removed legacy root `tests/` suite and dual-track workflows.
- Standardized launch/runtime scripts to canonical paths (`launch_app*.bat`, `scripts/runtime/*`).
- Replaced CI with strict canonical pipeline and Playwright Chromium smoke job.
- Added canonical dependency and type-check manifests:
  - `requirements-rebuild.txt`
  - `mypy-rebuild.ini`
- Added consolidation audit artifacts:
  - `docs/audit/single-track-baseline/*`
  - `docs/audit/single-track-decision.md`

## 2026-02-27 | Consolidation safety snapshot
- Pre-removal snapshot commit: `f6eb514`
- Backup branch: `backup/safety-20260227-074709`
- Backup tag: `safety-pre-single-track-20260227-074709`

## Tombstone
- Historical legacy-track details remain available through git history at the safety snapshot above.
