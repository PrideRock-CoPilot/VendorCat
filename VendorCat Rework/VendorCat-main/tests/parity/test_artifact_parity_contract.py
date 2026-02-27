from __future__ import annotations

from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parent
VENDOR_ROOT = Path(__file__).resolve().parents[2] / "app" / "vendor_catalog_app"


def _manifest_lines(path: Path) -> set[str]:
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def _actual_files(root: Path, *, suffix: str | None = None) -> set[str]:
    out: set[str] = set()
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if suffix and file_path.suffix.lower() != suffix.lower():
            continue
        out.add(file_path.relative_to(root).as_posix())
    return out


def test_templates_manifest_matches_exactly() -> None:
    expected = _manifest_lines(PARITY_DIR / "old_templates_manifest.txt")
    actual = _actual_files(VENDOR_ROOT / "web" / "templates", suffix=".html")

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        details: list[str] = ["Template parity mismatch against old manifest."]
        if missing:
            details.append(f"Missing ({len(missing)}):")
            details.extend([f"  {item}" for item in missing])
        if extra:
            details.append(f"Extra ({len(extra)}):")
            details.extend([f"  {item}" for item in extra])
        raise AssertionError("\n".join(details))


def test_static_manifest_has_no_missing_files() -> None:
    expected = _manifest_lines(PARITY_DIR / "old_static_manifest.txt")
    actual = _actual_files(VENDOR_ROOT / "web" / "static")

    missing = sorted(expected - actual)
    if missing:
        details = ["Static parity mismatch: missing files.", f"Missing ({len(missing)}):"]
        details.extend([f"  {item}" for item in missing])
        raise AssertionError("\n".join(details))


def test_sql_manifest_has_no_missing_files() -> None:
    expected = _manifest_lines(PARITY_DIR / "old_sql_manifest.txt")
    actual = _actual_files(VENDOR_ROOT / "sql", suffix=".sql")

    missing = sorted(expected - actual)
    if missing:
        details = ["SQL parity mismatch: missing files.", f"Missing ({len(missing)}):"]
        details.extend([f"  {item}" for item in missing])
        raise AssertionError("\n".join(details))
