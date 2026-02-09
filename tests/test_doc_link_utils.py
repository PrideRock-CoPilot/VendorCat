from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.utils.doc_links import suggest_doc_title, suggest_doc_type


def test_suggest_doc_type_matches_known_hosts() -> None:
    assert suggest_doc_type("https://contoso.sharepoint.com/sites/x/doc.pdf") == "sharepoint"
    assert suggest_doc_type("https://onedrive.live.com/?id=123") == "onedrive"
    assert suggest_doc_type("https://example.atlassian.net/wiki/spaces/ABC/pages/1") == "confluence"
    assert suggest_doc_type("https://docs.google.com/document/d/123/edit") == "google_drive"
    assert suggest_doc_type("https://app.box.com/file/123") == "box"
    assert suggest_doc_type("https://dropbox.com/s/abc") == "dropbox"
    assert suggest_doc_type("https://github.com/org/repo/blob/main/README.md") == "github"
    assert suggest_doc_type("https://intranet.example.com/policies") == "other"


def test_suggest_doc_title_uses_host_and_last_path_segment() -> None:
    title = suggest_doc_title("https://contoso.sharepoint.com/sites/procurement/Contract_2026.pdf")
    assert title.startswith("contoso.sharepoint.com - ")
    assert "Contract_2026.pdf" in title
    assert len(title) <= 120

