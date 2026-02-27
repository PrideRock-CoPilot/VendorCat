# Single-Track Decision Record

Date: 2026-02-27

## Decision Policy
- Primary criterion: Operational Readiness
- Weighting:
  - Operational readiness: 70%
  - Data-model alignment: 20%
  - Architecture maintainability: 10%

## Evidence
- Canonical collect: `python -m pytest --collect-only -q tests_rebuild` (see `docs/audit/single-track-baseline/tests_rebuild_collect.txt`)
- Legacy collect: `python -m pytest --collect-only -q tests` (see `docs/audit/single-track-baseline/tests_legacy_collect.txt`)
- Canonical smoke set:
  - `tests_rebuild/test_schema_validation.py`
  - `tests_rebuild/test_urls_and_pages.py`
  - `tests_rebuild/guards/test_architecture_guards.py`
  - Output: `docs/audit/single-track-baseline/smoke_tests.txt`

## Scorecard
- `src` track:
  - Operational readiness: 95/100
  - Data-model alignment: 85/100
  - Architecture maintainability: 90/100
  - Weighted score: 92.5
- Legacy removed track:
  - Operational readiness: 10/100
  - Data-model alignment: 30/100
  - Architecture maintainability: 25/100
  - Weighted score: 14.5

## Result
- Selected canonical track: `src` (`vendorcatalog_rebuild` + `apps/*`)
- Non-canonical track removed from mainline immediately after safety snapshot.
- CI/docs/tests/runtime now target canonical track only.
