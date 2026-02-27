from __future__ import annotations

import os
import time
from dataclasses import dataclass

from playwright.sync_api import BrowserContext, Page, expect, sync_playwright


@dataclass
class FlowState:
    vendor_id: str
    contact_name: str
    identifier_value: str
    offering_id: str
    contract_id: str


def _base_url() -> str:
    return os.getenv("E2E_BASE_URL", "http://127.0.0.1:8011").rstrip("/")


def _pick_first_nonempty_option(page: Page, selector: str) -> str:
    options = page.locator(f"{selector} option")
    count = options.count()
    for index in range(count):
        value = (options.nth(index).get_attribute("value") or "").strip()
        if value:
            page.locator(selector).select_option(value=value)
            return value
    raise RuntimeError(f"No selectable option found for {selector}")


def _post_json(context: BrowserContext, url: str, payload: dict) -> dict:
    response = context.request.post(url, data=payload)
    if response.status != 201:
        raise RuntimeError(f"POST {url} failed: status={response.status} body={response.text()}")
    return response.json()


def _get_json(context: BrowserContext, url: str) -> dict:
    response = context.request.get(url)
    if response.status != 200:
        raise RuntimeError(f"GET {url} failed: status={response.status} body={response.text()}")
    return response.json()


def run_flow() -> FlowState:
    stamp = str(int(time.time()))
    vendor_id = f"E2E-VND-{stamp}"
    vendor_display_name = f"E2E Vendor {stamp}"
    contact_name = f"E2E Contact {stamp}"
    identifier_value = f"{stamp}1234"
    offering_id = f"offering-{stamp}"
    contract_id = f"cont-{stamp}"

    base = _base_url()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            base_url=base,
            extra_http_headers={
                "X-Forwarded-Preferred-Username": "e2e.admin@example.com",
                "X-Forwarded-Email": "e2e.admin@example.com",
                "X-Forwarded-Name": "E2E Admin",
                "X-Forwarded-Groups": "vendor_admin",
            },
        )
        page = context.new_page()

        page.goto(f"{base}/vendor-360/new", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="Add New Vendor")).to_be_visible(timeout=20000)

        page.fill("#vendor_id", vendor_id)
        page.fill("#owner_org_id", "IT-ENT")
        page.fill("#legal_name", f"E2E Legal {stamp} LLC")
        page.fill("#display_name", vendor_display_name)
        page.select_option("#lifecycle_state", "active")
        page.select_option("#risk_tier", "low")
        page.get_by_role("button", name="+ Create Vendor").click()

        page.wait_for_url(f"**/vendor-360/{vendor_id}", timeout=20000)
        expect(page.get_by_text(vendor_id, exact=True).first).to_be_visible(timeout=20000)

        page.goto(f"{base}/vendor-360/{vendor_id}/contacts/new", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="Add New Contact")).to_be_visible(timeout=20000)

        page.fill("#id_full_name", contact_name)
        if page.locator("#id_contact_type").count():
            try:
                page.select_option("#id_contact_type", "primary")
            except Exception:
                _pick_first_nonempty_option(page, "#id_contact_type")
        if page.locator("#id_title").count():
            try:
                page.select_option("#id_title", "Support Lead")
            except Exception:
                _pick_first_nonempty_option(page, "#id_title")
        page.fill("#id_email", f"e2e-{stamp}@example.com")
        page.fill("#id_phone", "555-1010")
        if page.locator("#id_is_primary").count() and not page.locator("#id_is_primary").is_checked():
            page.locator("#id_is_primary").check()
        page.get_by_role("button", name="Create Contact").click()

        page.wait_for_url(f"**/vendor-360/{vendor_id}/contacts", timeout=20000)
        contacts_payload = _get_json(context, f"{base}/vendor-360/api/{vendor_id}/contacts")
        created_contact_names = {entry.get("full_name", "") for entry in contacts_payload.get("contacts", [])}
        if contact_name not in created_contact_names:
            raise RuntimeError("Created contact not returned by contacts API")

        page.goto(f"{base}/vendor-360/{vendor_id}/identifiers/new", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name="Add New Identifier")).to_be_visible(timeout=20000)

        identifier_type = _pick_first_nonempty_option(page, "#id_identifier_type")
        page.fill("#id_identifier_value", identifier_value)
        page.fill("#id_country_code", "US")
        if page.locator("#id_is_primary").count() and not page.locator("#id_is_primary").is_checked():
            page.locator("#id_is_primary").check()
        if page.locator("#id_notes").count():
            page.fill("#id_notes", f"Created by e2e flow; type={identifier_type}")
        page.get_by_role("button", name="Create Identifier").click()

        page.wait_for_url(f"**/vendor-360/{vendor_id}/identifiers", timeout=20000)
        identifiers_payload = _get_json(context, f"{base}/vendor-360/api/{vendor_id}/identifiers")
        created_identifier_values = {
            entry.get("identifier_value", "") for entry in identifiers_payload.get("identifiers", [])
        }
        if identifier_value not in created_identifier_values:
            raise RuntimeError("Created identifier not returned by identifiers API")

        offering_payload = {
            "offering_id": offering_id,
            "offering_name": f"E2E Offering {stamp}",
            "lifecycle_state": "active",
            "offering_type": "SaaS",
            "lob": "IT",
            "service_type": "Managed Service",
            "criticality_tier": "tier_3",
        }
        offering = _post_json(context, f"{base}/api/v1/vendors/{vendor_id}/offerings", offering_payload)

        contract_payload = {
            "contract_id": contract_id,
            "offering_id": offering["offering_id"],
            "contract_number": f"E2E-CN-{stamp}",
            "contract_status": "active",
            "start_date": "2026-01-01",
            "end_date": "2027-01-01",
            "annual_value": "120000.00",
            "cancelled_flag": False,
        }
        contract = _post_json(context, f"{base}/api/v1/vendors/{vendor_id}/contracts", contract_payload)

        page.goto(f"{base}/contracts/{contract['contract_id']}", wait_until="domcontentloaded")
        expect(page.get_by_role("heading", name=contract["contract_id"])) .to_be_visible(timeout=20000)
        expect(page.get_by_text(vendor_display_name).first).to_be_visible(timeout=20000)

        page.goto(f"{base}/offerings/{offering['offering_id']}", wait_until="domcontentloaded")
        expect(page.get_by_text(offering["offering_name"])).to_be_visible(timeout=20000)

        browser.close()

    return FlowState(
        vendor_id=vendor_id,
        contact_name=contact_name,
        identifier_value=identifier_value,
        offering_id=offering_id,
        contract_id=contract_id,
    )


def main() -> None:
    result = run_flow()
    print("E2E full-create flow passed")
    print(f"vendor_id={result.vendor_id}")
    print(f"offering_id={result.offering_id}")
    print(f"contract_id={result.contract_id}")


if __name__ == "__main__":
    main()
