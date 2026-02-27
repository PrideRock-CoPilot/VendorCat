# Documentation Index

This repository now uses a single canonical runtime track: `src`.

## Core Docs
- `docs/CHANGELOG.md`: change history and consolidation tombstone
- `docs/rebuild/`: canonical implementation notes and phase artifacts
- `docs/audit/single-track-baseline/`: consolidation baseline evidence
- `docs/audit/single-track-decision.md`: selection scorecard and decision

## Runtime References
- App command: `python src/manage.py runserver 0.0.0.0:8010`
- Launcher: `launch_app.bat`
- CI: `.github/workflows/ci.yml`
- Tests: `tests_rebuild/`
- Scripts: `scripts/runtime/`

## Guardrails
- No non-canonical runtime references in CI/docs/tests/scripts.
- No imports from removed `vendor_catalog_app` paths.
