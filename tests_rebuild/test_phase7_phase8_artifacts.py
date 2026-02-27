from __future__ import annotations

from pathlib import Path


def test_databricks_smoke_workflow_exists_and_is_strict() -> None:
    workflow_path = Path(".github/workflows/ci.yml")
    assert workflow_path.exists()
    text = workflow_path.read_text(encoding="utf-8").lower()
    assert "continue-on-error" not in text
    assert "playwright-smoke" in text


def test_cutover_scripts_and_docs_exist() -> None:
    required_paths = [
        Path("scripts/runtime/cutover_preflight.ps1"),
        Path("scripts/runtime/cutover_execute.ps1"),
        Path("scripts/runtime/cutover_smoke.ps1"),
        Path("scripts/runtime/rollback_prepare.ps1"),
        Path("docs/rebuild/cutover_runbook.md"),
        Path("docs/rebuild/decommission_plan.md"),
        Path("docs/rebuild/archive_access.md"),
    ]
    for path in required_paths:
        assert path.exists(), f"Missing required artifact: {path}"


def test_cutover_scripts_log_run_ids() -> None:
    for path in [
        Path("scripts/runtime/cutover_preflight.ps1"),
        Path("scripts/runtime/cutover_execute.ps1"),
        Path("scripts/runtime/cutover_smoke.ps1"),
        Path("scripts/runtime/rollback_prepare.ps1"),
    ]:
        text = path.read_text(encoding="utf-8").lower()
        assert "run_id" in text
