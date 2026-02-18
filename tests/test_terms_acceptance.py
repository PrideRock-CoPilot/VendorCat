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
