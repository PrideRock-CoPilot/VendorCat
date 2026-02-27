from __future__ import annotations

from pathlib import Path

FORBIDDEN_IMPORT_PATTERNS = (
    "from app.vendor_catalog_app",
    "import app.vendor_catalog_app",
)

LEGACY_OVERSIZE_BASELINE = {
    "offerings/views.py": 1945,
    "vendors/admin.py": 522,
    "vendors/models.py": 524,
    "vendors/serializers.py": 597,
    "vendors/views.py": 2010,
    "vendors/migrations/0004_contractevent_offeringnote_offeringticket_vendordemo_and_more.py": 559,
}


def test_no_legacy_runtime_imports_in_rebuild_src() -> None:
    src_root = Path(__file__).resolve().parents[2] / "src"
    python_files = list(src_root.rglob("*.py"))
    violations: list[str] = []

    for file_path in python_files:
        text = file_path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_IMPORT_PATTERNS:
            if pattern in text:
                violations.append(f"{file_path}: {pattern}")

    assert not violations, "\n".join(violations)


def test_rebuild_file_size_budget() -> None:
    src_root = Path(__file__).resolve().parents[2] / "src" / "apps"
    python_files = list(src_root.rglob("*.py"))
    oversized_new: list[str] = []
    oversized_growth: list[str] = []

    max_lines = 500
    for file_path in python_files:
        line_count = sum(1 for _ in file_path.open("r", encoding="utf-8"))
        relative_path = file_path.relative_to(src_root).as_posix()
        baseline_limit = LEGACY_OVERSIZE_BASELINE.get(relative_path)

        if line_count <= max_lines:
            continue

        if baseline_limit is None:
            oversized_new.append(f"{file_path} has {line_count} lines")
            continue

        if line_count > baseline_limit:
            oversized_growth.append(
                f"{file_path} grew from baseline {baseline_limit} to {line_count} lines"
            )

    assert not oversized_new, "\n".join(oversized_new)
    assert not oversized_growth, "\n".join(oversized_growth)


def test_rebuild_ci_has_no_continue_on_error() -> None:
    workflow_path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "rebuild-ci.yml"
    text = workflow_path.read_text(encoding="utf-8").lower()
    assert "continue-on-error" not in text
