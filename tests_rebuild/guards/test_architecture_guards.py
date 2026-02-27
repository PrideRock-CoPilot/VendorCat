from __future__ import annotations

from pathlib import Path

FORBIDDEN_IMPORT_PATTERNS = (
    "from vendor_catalog_app",
    "import vendor_catalog_app",
    "from app.vendor_catalog_app",
    "import app.vendor_catalog_app",
)

FORBIDDEN_PATH_REFERENCES = (
    "VendorCat Rework/",
    "VendorCat Rework\\",
    "app/vendor_catalog_app",
    "app\\vendor_catalog_app",
    "launch_rebuild",
    "scripts/rebuild/",
    "scripts\\rebuild\\",
    ".github/workflows/rebuild-ci.yml",
    ".github/workflows/rebuild-databricks-smoke.yml",
    "pytest tests/",
    "pip install -r app/requirements.txt",
)

LEGACY_OVERSIZE_BASELINE = {
    "offerings/views.py": 1945,
    "vendors/admin.py": 522,
    "vendors/models.py": 524,
    "vendors/serializers.py": 597,
    "vendors/views.py": 2010,
    "vendors/migrations/0004_contractevent_offeringnote_offeringticket_vendordemo_and_more.py": 559,
}


def test_no_legacy_runtime_imports_in_src() -> None:
    src_root = Path(__file__).resolve().parents[2] / "src"
    python_files = list(src_root.rglob("*.py"))
    violations: list[str] = []

    for file_path in python_files:
        text = file_path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_IMPORT_PATTERNS:
            if pattern in text:
                violations.append(f"{file_path}: {pattern}")

    assert not violations, "\n".join(violations)


def test_file_size_budget() -> None:
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
            oversized_growth.append(f"{file_path} grew from baseline {baseline_limit} to {line_count} lines")

    assert not oversized_new, "\n".join(oversized_new)
    assert not oversized_growth, "\n".join(oversized_growth)


def test_ci_has_no_continue_on_error() -> None:
    workflow_path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
    text = workflow_path.read_text(encoding="utf-8").lower()
    assert "continue-on-error" not in text


def test_no_removed_track_references_in_root_artifacts() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    scan_roots = [
        repo_root / ".github",
        repo_root / "docs",
        repo_root / "scripts",
        repo_root / "tests_rebuild",
        repo_root / "README.md",
        repo_root / "REPOSITORY_STRUCTURE.md",
    ]

    violations: list[str] = []
    ignored_paths = {
        (repo_root / "tests_rebuild" / "guards" / "test_architecture_guards.py").resolve(),
    }
    ignored_dir_prefixes = [
        (repo_root / "docs" / "audit" / "single-track-baseline").resolve(),
    ]

    def _scan_file(file_path: Path) -> None:
        resolved = file_path.resolve()
        if resolved in ignored_paths:
            return
        for prefix in ignored_dir_prefixes:
            if str(resolved).startswith(str(prefix)):
                return
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for forbidden in FORBIDDEN_PATH_REFERENCES:
            if forbidden in text:
                violations.append(f"{file_path}: {forbidden}")

    for target in scan_roots:
        if target.is_file():
            _scan_file(target)
            continue
        for file_path in target.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in {".md", ".yml", ".yaml", ".py", ".ps1", ".bat", ".txt"}:
                continue
            _scan_file(file_path)

    assert not violations, "\n".join(violations)
