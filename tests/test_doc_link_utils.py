from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.utils.doc_links import (
    extract_doc_fqdn,
    normalize_doc_fqdn,
    normalize_doc_tags,
    suggest_doc_title,
    suggest_doc_type,
)


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


def test_extract_and_normalize_fqdn() -> None:
    assert extract_doc_fqdn("https://contoso.sharepoint.com/sites/vendors/Contract.pdf") == "contoso.sharepoint.com"
    assert extract_doc_fqdn("contoso.sharepoint.com/sites/vendors/Contract.pdf") == "contoso.sharepoint.com"
    assert normalize_doc_fqdn("Contoso.SharePoint.com") == "contoso.sharepoint.com"


def test_normalize_doc_tags_includes_detected_type_and_fqdn() -> None:
    tags = normalize_doc_tags(["contract", "renewal"], doc_type="sharepoint", fqdn="contoso.sharepoint.com")
    assert "contract" in tags
    assert "renewal" in tags
    assert "sharepoint" in tags
    assert "fqdn:contoso.sharepoint.com" in tags


def test_normalize_doc_tags_keeps_custom_and_derives_folder_tag() -> None:
    tags = normalize_doc_tags(
        ["Custom Tag", "cross-team"],
        doc_type="other",
        fqdn="contoso.sharepoint.com",
        doc_url="contoso.sharepoint.com/sites/vendor-library/folders/nda/",
    )
    assert "custom_tag" in tags
    assert "cross-team" in tags
    assert "folder" in tags
