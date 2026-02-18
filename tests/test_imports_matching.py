from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.routers.imports.matching import build_preview_rows


class _FakeRepo:
    def __init__(self) -> None:
        self._profiles = {
            "vnd-domain-1": {"vendor_id": "vnd-domain-1", "display_name": "Domain Match Vendor", "legal_name": "Domain Match Vendor LLC"},
            "vnd-phone-1": {"vendor_id": "vnd-phone-1", "display_name": "Phone Match Vendor", "legal_name": "Phone Match Vendor LLC"},
        }

    def get_vendor_profile(self, vendor_id: str):
        row = self._profiles.get(str(vendor_id or "").strip())
        if not row:
            return pd.DataFrame(columns=["vendor_id", "display_name", "legal_name"])
        return pd.DataFrame([row])

    def search_vendors_typeahead(self, *, q: str = "", limit: int = 10):
        _ = (q, limit)
        return pd.DataFrame(columns=["vendor_id", "display_name", "legal_name"])

    def list_vendor_contacts_index(self, limit: int = 250000):
        _ = limit
        return pd.DataFrame(
            [
                {
                    "vendor_id": "vnd-domain-1",
                    "email": "ops@domainmatch.example",
                    "phone": "1-800-555-9123",
                },
                {
                    "vendor_id": "vnd-phone-1",
                    "email": "contact@phonematch.example",
                    "phone": "212-999-4401",
                },
            ]
        )

    def get_offerings_by_ids(self, ids: list[str]):
        _ = ids
        return pd.DataFrame(columns=["offering_id", "vendor_id", "offering_name"])

    def search_offerings_typeahead(self, *, vendor_id: str | None = None, q: str = "", limit: int = 10):
        _ = (vendor_id, q, limit)
        return pd.DataFrame(columns=["offering_id", "vendor_id", "offering_name"])

    def get_project_by_id(self, project_id: str):
        _ = project_id
        return None

    def search_projects_typeahead(self, *, q: str = "", limit: int = 10):
        _ = (q, limit)
        return pd.DataFrame(columns=["project_id", "project_name", "vendor_id"])


def test_vendor_matching_uses_email_domain() -> None:
    repo = _FakeRepo()
    rows = [
        {
            "vendor_id": "",
            "legal_name": "Some New Name",
            "display_name": "Some New Name",
            "owner_org_id": "IT",
            "lifecycle_state": "draft",
            "risk_tier": "medium",
            "support_contact_name": "Ops",
            "support_contact_type": "business",
            "support_email": "newuser@domainmatch.example",
            "support_phone": "",
            "_line": "2",
        }
    ]
    preview = build_preview_rows(repo, "vendors", rows)
    assert len(preview) == 1
    row = preview[0]
    assert row["suggested_action"] == "merge"
    assert row["suggested_target_id"] == "vnd-domain-1"
    assert any("email domain" in str(note).lower() for note in row.get("notes", []))


def test_vendor_matching_uses_phone_suffix() -> None:
    repo = _FakeRepo()
    rows = [
        {
            "vendor_id": "",
            "legal_name": "Different Name",
            "display_name": "Different Name",
            "owner_org_id": "IT",
            "lifecycle_state": "draft",
            "risk_tier": "medium",
            "support_contact_name": "Ops",
            "support_contact_type": "business",
            "support_email": "",
            "support_phone": "+1 (646) 999-4401",
            "_line": "3",
        }
    ]
    preview = build_preview_rows(repo, "vendors", rows)
    assert len(preview) == 1
    row = preview[0]
    assert row["suggested_action"] == "merge"
    assert row["suggested_target_id"] == "vnd-phone-1"
    assert any("phone suffix" in str(note).lower() for note in row.get("notes", []))
