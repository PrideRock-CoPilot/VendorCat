from __future__ import annotations

import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
RUNTIME_ROOT = APP_ROOT / "vendor_catalog_app"

LEGACY_LOB_PATTERN = re.compile(r"\bline\s+of\s+business\b|\blob\b|\blob_", re.IGNORECASE)
LEGACY_LOB_ALLOWLIST = {
    # Explicit validation guards that reject legacy payload keys.
    "vendor_catalog_app\\web\\http\\middleware.py",
    "vendor_catalog_app\\backend\\repository_mixins\\domains\\workflow\\requests.py",
}


def _runtime_files() -> list[Path]:
    roots = [
        RUNTIME_ROOT / "backend",
        RUNTIME_ROOT / "web",
        RUNTIME_ROOT / "sql",
    ]
    files: list[Path] = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".py", ".html", ".sql", ".js", ".css"}:
                continue
            files.append(path)
    return files


def test_runtime_has_no_legacy_lob_terms() -> None:
    offenders: list[str] = []
    for path in _runtime_files():
        relative = str(path.relative_to(APP_ROOT))
        if relative in LEGACY_LOB_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        if LEGACY_LOB_PATTERN.search(text):
            offenders.append(relative)
    assert not offenders, f"Found legacy LOB references in runtime files: {offenders}"


GOVERNED_SELECTS: list[tuple[Path, str]] = [
    (RUNTIME_ROOT / "web" / "templates" / "vendor_new.html", "owner_org_choice"),
    (RUNTIME_ROOT / "web" / "templates" / "vendor_new.html", "lifecycle_state"),
    (RUNTIME_ROOT / "web" / "templates" / "vendor_new.html", "risk_tier"),
    (RUNTIME_ROOT / "web" / "templates" / "offering_new.html", "offering_type"),
    (RUNTIME_ROOT / "web" / "templates" / "offering_new.html", "business_unit"),
    (RUNTIME_ROOT / "web" / "templates" / "offering_new.html", "service_type"),
    (RUNTIME_ROOT / "web" / "templates" / "offering_new.html", "lifecycle_state"),
    (RUNTIME_ROOT / "web" / "templates" / "offering_detail.html", "offering_type"),
    (RUNTIME_ROOT / "web" / "templates" / "offering_detail.html", "business_unit"),
    (RUNTIME_ROOT / "web" / "templates" / "offering_detail.html", "service_type"),
]


def _select_blocks(template_text: str, select_name: str) -> list[str]:
    pattern = re.compile(
        rf"<select[^>]*name=\"{re.escape(select_name)}\"[^>]*>(.*?)</select>",
        re.IGNORECASE | re.DOTALL,
    )
    return [str(match.group(1) or "") for match in pattern.finditer(template_text)]


def test_governed_dropdowns_are_lookup_backed_in_templates() -> None:
    missing_loops: list[str] = []
    for template_path, select_name in GOVERNED_SELECTS:
        text = template_path.read_text(encoding="utf-8")
        blocks = _select_blocks(text, select_name)
        if not blocks:
            missing_loops.append(f"{template_path.relative_to(APP_ROOT)}:{select_name}:missing-select")
            continue
        for block in blocks:
            if "{% for " not in block:
                missing_loops.append(f"{template_path.relative_to(APP_ROOT)}:{select_name}:no-lookup-loop")
    assert not missing_loops, f"Governed dropdowns must be lookup-backed: {missing_loops}"


def test_governed_templates_do_not_offer_freeform_business_unit_add() -> None:
    template = (RUNTIME_ROOT / "web" / "templates" / "vendor_new.html").read_text(encoding="utf-8")
    assert "+ Add new business unit" not in template
    assert "new_owner_org_id" not in template
