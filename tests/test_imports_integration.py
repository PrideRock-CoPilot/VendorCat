from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.core.runtime import get_config, get_repo


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, isolated_local_db: Path) -> TestClient:
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()
    return TestClient(app)


def test_imports_bulk_insert_vendors_creates_multiple_records(client: TestClient) -> None:
    csv_payload = (
        "vendor_id,legal_name,display_name,owner_org_id,lifecycle_state,risk_tier,support_contact_name,"
        "support_contact_type,support_email,support_phone\n"
        ",Bulk Import Vendor One LLC,Bulk Import Vendor One,IT-ENT,draft,low,Owner One,business,"
        "owner.one@example.com,555-0101\n"
        ",Bulk Import Vendor Two LLC,Bulk Import Vendor Two,FIN-OPS,draft,medium,Owner Two,support,"
        "owner.two@example.com,555-0102\n"
    )

    preview_response = client.post(
        "/imports/preview",
        data={"layout": "vendors"},
        files={"file": ("vendors.csv", csv_payload, "text/csv")},
        follow_redirects=True,
    )
    assert preview_response.status_code == 200
    assert "Bulk Import Vendor One" in preview_response.text
    assert "Bulk Import Vendor Two" in preview_response.text

    token_match = re.search(r'name="preview_token" value="([^"]+)"', preview_response.text)
    assert token_match is not None
    preview_token = token_match.group(1)

    apply_response = client.post(
        "/imports/apply",
        data={
            "preview_token": preview_token,
            "reason": "bulk insert test",
            "bulk_default_action": "new",
        },
        follow_redirects=True,
    )
    assert apply_response.status_code == 200
    assert "Import complete." in apply_response.text
    assert "created=2" in apply_response.text
    assert "failed=0" in apply_response.text
    staging_match = re.search(r"Staging job:\s*<strong>(imjob-[^<]+)</strong>", apply_response.text)
    assert staging_match is not None

    vendors_page = client.get("/vendors?search=Bulk+Import+Vendor")
    assert vendors_page.status_code == 200
    assert "Bulk Import Vendor One" in vendors_page.text
    assert "Bulk Import Vendor Two" in vendors_page.text


def test_imports_json_auto_detect_and_stage_job_status(
    client: TestClient,
    isolated_local_db: Path,
) -> None:
    json_payload = (
        '{"records":['
        '{"legal_name":"Json Vendor One LLC","display_name":"Json Vendor One","owner_org_id":"IT","lifecycle_state":"draft"},'
        '{"legal_name":"Json Vendor Two LLC","display_name":"Json Vendor Two","owner_org_id":"FIN","lifecycle_state":"draft"}'
        "]}"
    )

    preview_response = client.post(
        "/imports/preview",
        data={"layout": "vendors", "format_hint": "auto", "flow_mode": "wizard"},
        files={"file": ("vendors.json", json_payload, "application/json")},
        follow_redirects=True,
    )
    assert preview_response.status_code == 200
    assert "Json Vendor One" in preview_response.text
    assert "detected=json" in preview_response.text or "parser=json" in preview_response.text

    token_match = re.search(r'name="preview_token" value="([^"]+)"', preview_response.text)
    assert token_match is not None
    preview_token = token_match.group(1)

    apply_response = client.post(
        "/imports/apply",
        data={
            "preview_token": preview_token,
            "reason": "json ingest test",
            "bulk_default_action": "new",
        },
        follow_redirects=True,
    )
    assert apply_response.status_code == 200
    assert "Import complete." in apply_response.text

    job_match = re.search(r"Staging job:\s*<strong>(imjob-[^<]+)</strong>", apply_response.text)
    assert job_match is not None
    import_job_id = job_match.group(1)

    with sqlite3.connect(str(isolated_local_db)) as conn:
        row = conn.execute(
            "SELECT status, created_count, failed_count FROM app_import_job WHERE import_job_id = ?",
            (import_job_id,),
        ).fetchone()
        assert row is not None
        assert str(row[0]) == "applied"
        assert int(row[1]) == 2
        assert int(row[2]) == 0


def test_imports_wizard_applies_child_stage_rows_for_contacts_and_contracts(
    client: TestClient,
    isolated_local_db: Path,
) -> None:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "imports_dummy" / "wizard" / "vendors_contracts_contacts.json"
    json_payload = fixture_path.read_text(encoding="utf-8")
    source_field_keys = [
        "vendor.legal_name",
        "vendor.display_name",
        "vendor.owner_org_id",
        "vendor.lifecycle_state",
        "vendor.risk_tier",
        "contacts_1.name",
        "contacts_1.email",
        "contacts_1.phone",
        "contacts_2.name",
        "contacts_2.email",
        "contacts_2.phone",
        "contracts_1.contract_number",
        "contracts_1.status",
        "contracts_1.start_date",
        "contracts_1.end_date",
        "contracts_1.annual_value",
    ]
    source_target_keys = [
        "vendor.legal_name",
        "vendor.display_name",
        "vendor.owner_org_id",
        "vendor.lifecycle_state",
        "vendor.risk_tier",
        "vendor_contact.full_name",
        "vendor_contact.email",
        "vendor_contact.phone",
        "vendor_contact.full_name",
        "vendor_contact.email",
        "vendor_contact.phone",
        "contract.contract_number",
        "contract.contract_status",
        "contract.start_date",
        "contract.end_date",
        "contract.annual_value",
    ]

    with sqlite3.connect(str(isolated_local_db)) as conn:
        vendors_before = int(conn.execute("SELECT COUNT(*) FROM core_vendor").fetchone()[0])
        contacts_before = int(conn.execute("SELECT COUNT(*) FROM core_vendor_contact").fetchone()[0])
        contracts_before = int(conn.execute("SELECT COUNT(*) FROM core_contract").fetchone()[0])

    preview_response = client.post(
        "/imports/preview",
        data={
            "layout": "vendors",
            "flow_mode": "wizard",
            "format_hint": "json",
            "json_record_path": "records",
            "source_field_keys": source_field_keys,
            "source_target_keys": source_target_keys,
        },
        files={"file": ("vendors_contracts_contacts.json", json_payload.encode("utf-8"), "application/json")},
        follow_redirects=True,
    )
    assert preview_response.status_code == 200
    assert "Preview And Mapping" in preview_response.text

    token_match = re.search(r'name="preview_token" value="([^"]+)"', preview_response.text)
    assert token_match is not None
    preview_token = token_match.group(1)

    apply_response = client.post(
        "/imports/apply",
        data={
            "preview_token": preview_token,
            "reason": "wizard child stage apply",
            "bulk_default_action": "new",
        },
        follow_redirects=True,
    )
    assert apply_response.status_code == 200
    assert "Import complete." in apply_response.text
    assert "child writes" in apply_response.text or "Applied child entity writes" in apply_response.text

    with sqlite3.connect(str(isolated_local_db)) as conn:
        vendors_after = int(conn.execute("SELECT COUNT(*) FROM core_vendor").fetchone()[0])
        contacts_after = int(conn.execute("SELECT COUNT(*) FROM core_vendor_contact").fetchone()[0])
        contracts_after = int(conn.execute("SELECT COUNT(*) FROM core_contract").fetchone()[0])

    assert vendors_after - vendors_before == 2
    assert contacts_after - contacts_before == 3
    assert contracts_after - contracts_before == 2


def test_imports_bundle_applies_suppliers_invoices_and_payments(
    client: TestClient,
    isolated_local_db: Path,
) -> None:
    bundle_dir = Path(__file__).resolve().parent / "fixtures" / "imports_dummy" / "bundle"
    supplier_xml = (bundle_dir / "zycus_AH_SUPPLIER.xml").read_text(encoding="utf-8")
    invoice_xml = (bundle_dir / "zycus_AH_INVOICE.xml").read_text(encoding="utf-8")
    payment_xml = (bundle_dir / "zycus_AH_PAYMENT.xml").read_text(encoding="utf-8")

    with sqlite3.connect(str(isolated_local_db)) as conn:
        vendors_before = int(conn.execute("SELECT COUNT(*) FROM core_vendor").fetchone()[0])
        invoices_before = int(conn.execute("SELECT COUNT(*) FROM app_offering_invoice").fetchone()[0])
        payments_before = int(conn.execute("SELECT COUNT(*) FROM app_offering_payment").fetchone()[0])

    preview_response = client.post(
        "/imports/preview",
        data={"layout": "vendors", "flow_mode": "wizard", "format_hint": "auto"},
        files=[
            ("files", ("zycus_AH_SUPPLIER.xml", supplier_xml.encode("utf-8"), "application/xml")),
            ("files", ("zycus_AH_INVOICE.xml", invoice_xml.encode("utf-8"), "application/xml")),
            ("files", ("zycus_AH_PAYMENT.xml", payment_xml.encode("utf-8"), "application/xml")),
        ],
        follow_redirects=True,
    )
    assert preview_response.status_code == 200
    assert "Bundle Files" in preview_response.text
    assert "blocked" in preview_response.text.lower()

    token_match = re.search(r'name="preview_token" value="([^"]+)"', preview_response.text)
    assert token_match is not None
    preview_token = token_match.group(1)

    apply_response = client.post(
        "/imports/apply",
        data={
            "preview_token": preview_token,
            "apply_mode": "apply_eligible",
            "reason": "bundle dependency apply",
        },
        follow_redirects=True,
    )
    assert apply_response.status_code == 200
    assert "Import Results" in apply_response.text or "Bundle Files" in apply_response.text

    with sqlite3.connect(str(isolated_local_db)) as conn:
        vendors_after = int(conn.execute("SELECT COUNT(*) FROM core_vendor").fetchone()[0])
        invoices_after = int(conn.execute("SELECT COUNT(*) FROM app_offering_invoice").fetchone()[0])
        payments_after = int(conn.execute("SELECT COUNT(*) FROM app_offering_payment").fetchone()[0])

    assert vendors_after - vendors_before >= 2
    assert invoices_after - invoices_before >= 2
    assert payments_after - payments_before >= 2
