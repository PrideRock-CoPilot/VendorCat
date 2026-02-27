# Repository Structure

## Canonical Layout
- `src/`: Django runtime (`manage.py`, `vendorcatalog_rebuild`, `apps/*`, templates, static, schema)
- `tests_rebuild/`: canonical automated tests (unit/integration/guards/e2e)
- `scripts/runtime/`: runtime, cutover, validation, performance scripts
- `docs/`: active documentation and audit decisions
- `.github/workflows/ci.yml`: single canonical CI pipeline
- `requirements-rebuild.txt`: canonical dependency manifest
- `mypy-rebuild.ini`: canonical type-check config

## Run Commands
- App: `python src/manage.py runserver 0.0.0.0:8010`
- Tests: `pytest -q tests_rebuild`
- Quality: `./scripts/runtime/run_quality_checks.ps1`

## Single-Track Policy
- Mainline hosts one runtime/toolchain truth only: `src`.
- Removed track history is available through git snapshot tag/branch.
