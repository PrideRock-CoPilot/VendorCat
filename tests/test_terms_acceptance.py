from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.core import terms as terms_module
from vendor_catalog_app.web.core.runtime import get_config, get_repo


def test_terms_acceptance_required_and_reaccept_on_update(
    monkeypatch: pytest.MonkeyPatch,
    isolated_local_db: Path,
) -> None:
    monkeypatch.setenv("TVENDOR_TERMS_ENFORCEMENT_ENABLED", "true")
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)

    gated = client.get("/dashboard?splash=1", follow_redirects=False)
    assert gated.status_code == 303
    location = str(gated.headers.get("location", ""))
    assert location.startswith("/access/terms?next=")

    terms_page = client.get(location, follow_redirects=True)
    assert terms_page.status_code == 200
    assert "Internal Proof-of-Concept Use Notice" in terms_page.text

    version_match = re.search(r'name="terms_version" value="([^"]+)"', terms_page.text)
    assert version_match is not None
    terms_version = version_match.group(1)

    accept = client.post(
        "/access/terms/accept",
        data={
            "next": "/dashboard?splash=1",
            "terms_version": terms_version,
            "scrolled_to_end": "true",
            "agree_terms": "true",
        },
        follow_redirects=False,
    )
    assert accept.status_code == 303
    assert str(accept.headers.get("location", "")) == "/dashboard?splash=1"

    after_accept = client.get("/dashboard?splash=1", follow_redirects=False)
    assert after_accept.status_code == 200
    assert "Opening your workspace" in after_accept.text

    monkeypatch.setattr(
        terms_module,
        "TERMS_DOCUMENT_TEXT",
        terms_module.TERMS_DOCUMENT_TEXT + "\n\nRevision marker for reacceptance test.",
    )
    needs_reaccept = client.get("/dashboard?splash=1", follow_redirects=False)
    assert needs_reaccept.status_code == 303
    assert str(needs_reaccept.headers.get("location", "")).startswith("/access/terms?next=")


def test_terms_view_and_version_info_pages_render(
    monkeypatch: pytest.MonkeyPatch,
    isolated_local_db: Path,
) -> None:
    monkeypatch.setenv("TVENDOR_TERMS_ENFORCEMENT_ENABLED", "true")
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)

    terms_view = client.get("/access/terms/view")
    assert terms_view.status_code == 200
    assert "Internal Proof-of-Concept Use Notice" in terms_view.text
    assert "Accept And Continue" not in terms_view.text

    version_info = client.get("/version-info")
    assert version_info.status_code == 200
    assert "Version Information" in version_info.text
    assert "User Agreement Version" in version_info.text


def test_admin_can_update_terms_document_and_force_reacceptance(
    monkeypatch: pytest.MonkeyPatch,
    isolated_local_db: Path,
) -> None:
    monkeypatch.setenv("TVENDOR_TERMS_ENFORCEMENT_ENABLED", "true")
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    client = TestClient(app)

    first_gate = client.get("/dashboard?splash=1", follow_redirects=False)
    assert first_gate.status_code == 303
    first_terms_url = str(first_gate.headers.get("location", ""))
    assert first_terms_url.startswith("/access/terms?next=")

    first_terms_page = client.get(first_terms_url, follow_redirects=True)
    first_version_match = re.search(r'name="terms_version" value="([^"]+)"', first_terms_page.text)
    assert first_version_match is not None
    first_version = first_version_match.group(1)

    accept = client.post(
        "/access/terms/accept",
        data={
            "next": "/dashboard?splash=1",
            "terms_version": first_version,
            "scrolled_to_end": "true",
            "agree_terms": "true",
        },
        follow_redirects=False,
    )
    assert accept.status_code == 303
    assert str(accept.headers.get("location", "")) == "/dashboard?splash=1"

    save_terms = client.post(
        "/admin/terms/save",
        data={
            "title": "Vendor Catalog User Agreement",
            "effective_date": "February 19, 2026",
            "document_text": (
                "POC access is restricted to approved internal users.\n\n"
                "Do not upload regulated production data.\n\n"
                "Continued usage requires acceptance of each new version."
            ),
        },
        follow_redirects=False,
    )
    assert save_terms.status_code == 303
    assert str(save_terms.headers.get("location", "")) == "/admin/terms"

    second_gate = client.get("/dashboard?splash=1", follow_redirects=False)
    assert second_gate.status_code == 303
    second_terms_url = str(second_gate.headers.get("location", ""))
    assert second_terms_url.startswith("/access/terms?next=")

    second_terms_page = client.get(second_terms_url, follow_redirects=True)
    assert "Vendor Catalog User Agreement" in second_terms_page.text
    assert "February 19, 2026" in second_terms_page.text
    second_version_match = re.search(r'name="terms_version" value="([^"]+)"', second_terms_page.text)
    assert second_version_match is not None
    assert second_version_match.group(1) != first_version
