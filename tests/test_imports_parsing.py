from __future__ import annotations

import pytest
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.routers.imports.parsing import parse_layout_rows


def test_parse_layout_rows_json_auto_detect_records_path() -> None:
    raw_bytes = (
        b'{"records":[{"legal_name":"JSON Vendor","owner_org_id":"IT","display_name":"Json Vendor Display"}]}'
    )
    parsed = parse_layout_rows(
        "vendors",
        raw_bytes,
        file_name="vendors.json",
        format_hint="auto",
    )
    rows = list(parsed.get("rows") or [])
    assert str(parsed.get("detected_format")) == "json"
    assert str(parsed.get("effective_format")) == "json"
    assert len(rows) == 1
    assert rows[0]["legal_name"] == "JSON Vendor"
    assert rows[0]["owner_org_id"] == "IT"


def test_parse_layout_rows_xml_with_auto_record_detection() -> None:
    raw_bytes = (
        b"<vendors>"
        b"<vendor><legal_name>XML Vendor One</legal_name><owner_org_id>IT</owner_org_id></vendor>"
        b"<vendor><legal_name>XML Vendor Two</legal_name><owner_org_id>FIN</owner_org_id></vendor>"
        b"</vendors>"
    )
    parsed = parse_layout_rows(
        "vendors",
        raw_bytes,
        file_name="vendors.xml",
        format_hint="auto",
    )
    rows = list(parsed.get("rows") or [])
    assert str(parsed.get("detected_format")) == "xml"
    assert str(parsed.get("effective_format")) == "xml"
    assert len(rows) == 2
    assert rows[0]["legal_name"] == "XML Vendor One"
    assert rows[1]["legal_name"] == "XML Vendor Two"


def test_parse_layout_rows_xml_nested_record_path_detection_and_override() -> None:
    raw_bytes = (
        b"<root>"
        b"<vendor_set>"
        b"<vendor><legal_name>Nested Vendor One</legal_name><owner_org_id>IT</owner_org_id></vendor>"
        b"<vendor><legal_name>Nested Vendor Two</legal_name><owner_org_id>FIN</owner_org_id></vendor>"
        b"</vendor_set>"
        b"</root>"
    )
    parsed_auto = parse_layout_rows(
        "vendors",
        raw_bytes,
        file_name="nested_vendors.xml",
        format_hint="xml",
    )
    assert len(list(parsed_auto.get("rows") or [])) == 2
    assert str(parsed_auto.get("parser_options", {}).get("xml_record_path") or "").strip() != ""
    assert str(parsed_auto.get("resolved_record_selector") or "").strip().startswith("xml:")

    parsed_explicit = parse_layout_rows(
        "vendors",
        raw_bytes,
        file_name="nested_vendors.xml",
        format_hint="xml",
        xml_record_path="root.vendor_set.vendor",
    )
    rows = list(parsed_explicit.get("rows") or [])
    assert len(rows) == 2
    assert rows[0]["legal_name"] == "Nested Vendor One"
    assert rows[1]["legal_name"] == "Nested Vendor Two"


def test_parse_layout_rows_xml_supports_detected_tag_mapping_override() -> None:
    raw_bytes = (
        b"<vendors>"
        b"<vendor>"
        b"<company_legal_title>Mapped XML Vendor</company_legal_title>"
        b"<company_display>Mapped XML</company_display>"
        b"<contact><email>ops@mapped.example</email></contact>"
        b"</vendor>"
        b"</vendors>"
    )
    parsed = parse_layout_rows(
        "vendors",
        raw_bytes,
        file_name="vendors.xml",
        format_hint="xml",
    )
    source_keys = [str(item.get("key") or "") for item in list(parsed.get("source_fields") or [])]
    assert "vendor.company_legal_title" in source_keys
    assert parsed["rows"][0]["legal_name"] == ""

    remapped = parse_layout_rows(
        "vendors",
        raw_bytes,
        file_name="vendors.xml",
        format_hint="xml",
        field_mapping={
            "legal_name": "vendor.company_legal_title",
            "display_name": "vendor.company_display",
            "support_email": "vendor.contact.email",
        },
    )
    assert remapped["rows"][0]["legal_name"] == "Mapped XML Vendor"
    assert remapped["rows"][0]["display_name"] == "Mapped XML"
    assert remapped["rows"][0]["support_email"] == "ops@mapped.example"


def test_parse_layout_rows_strict_quick_layout_rejects_missing_columns() -> None:
    raw_bytes = b"legal_name,owner_org_id\nStrict Vendor,IT\n"
    with pytest.raises(ValueError) as excinfo:
        parse_layout_rows(
            "vendors",
            raw_bytes,
            file_name="vendors.csv",
            format_hint="auto",
            strict_layout=True,
        )
    assert "Approved layout mismatch" in str(excinfo.value)


def test_parse_layout_rows_json_repeating_contacts_emit_multiple_stage_rows() -> None:
    raw_bytes = (
        b'{"records":[{"vendor":{"legal_name":"Grouped Vendor","owner_org_id":"IT"},'
        b'"contacts":[{"name":"A One","email":"a.one@example.com"},{"name":"B Two","email":"b.two@example.com"}]}]}'
    )
    parsed = parse_layout_rows(
        "vendors",
        raw_bytes,
        file_name="vendors.json",
        format_hint="json",
        source_target_mapping={
            "vendor.legal_name": "vendor.legal_name",
            "vendor.owner_org_id": "vendor.owner_org_id",
            "contacts_1.name": "vendor_contact.full_name",
            "contacts_1.email": "vendor_contact.email",
            "contacts_2.name": "vendor_contact.full_name",
            "contacts_2.email": "vendor_contact.email",
        },
    )
    stage_rows = dict(parsed.get("stage_area_rows") or {})
    contact_rows = list(stage_rows.get("vendor_contact") or [])
    assert len(contact_rows) == 2
    names = sorted([str(dict(row.get("payload") or {}).get("full_name") or "") for row in contact_rows])
    assert names == ["A One", "B Two"]
    group_keys = sorted([str(row.get("source_group_key") or "") for row in contact_rows])
    assert group_keys == ["contacts_1", "contacts_2"]
