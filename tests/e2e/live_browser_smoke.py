from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import Page, sync_playwright


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""


def _wait_for_http_ready(url: str, timeout_sec: int = 60) -> None:
    deadline = time.time() + float(timeout_sec)
    last_error = ""
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as resp:
                if 200 <= int(resp.status) < 500:
                    return
        except URLError as exc:
            last_error = str(exc)
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for server readiness at {url}. last_error={last_error}")


def _goto(page: Page, base_url: str, path: str, expect_text: str | None = None) -> None:
    response = page.goto(f"{base_url}{path}", wait_until="domcontentloaded", timeout=120000)
    if response is None or response.status >= 500:
        status = "none" if response is None else str(response.status)
        raise RuntimeError(f"GET {path} failed with status={status}")
    if expect_text:
        page.get_by_text(expect_text, exact=False).first.wait_for(timeout=120000)


def _select_option_best_effort(page: Page, selector: str, preferred_values: list[str]) -> None:
    locator = page.locator(selector)
    if locator.count() == 0:
        return
    for value in preferred_values:
        try:
            locator.select_option(value=value)
            return
        except Exception:
            continue
        try:
            locator.select_option(label=value)
            return
        except Exception:
            continue
    # fall back to first non-empty option
    options = locator.locator("option")
    for idx in range(options.count()):
        value = str(options.nth(idx).get_attribute("value") or "").strip()
        if value:
            locator.select_option(value=value)
            return


def _click_nav_links(page: Page, base_url: str) -> list[StepResult]:
    nav_targets = [
        ("Dashboard", "/dashboard"),
        ("Vendor 360", "/vendor-360"),
        ("Projects", "/projects"),
        ("Contracts", "/contracts"),
        ("Demos", "/demos"),
        ("Imports", "/imports"),
        ("Pending Approvals", "/workflows/pending-approvals"),
        ("Reports", "/reports"),
        ("Admin", "/admin"),
    ]
    results: list[StepResult] = []
    for label, expected_path in nav_targets:
        try:
            link = page.locator("nav.nav a", has_text=label).first
            if link.count() == 0:
                results.append(StepResult(name=f"nav:{label}", ok=False, detail="link not found"))
                continue
            link.click()
            page.wait_for_load_state("domcontentloaded")
            current = page.url
            if expected_path not in current:
                # Some links redirect (vendor-360 -> /vendors)
                if label == "Vendor 360" and "/vendors" in current or label == "Pending Approvals" and "/workflows" in current:
                    results.append(StepResult(name=f"nav:{label}", ok=True, detail=current))
                else:
                    results.append(StepResult(name=f"nav:{label}", ok=False, detail=current))
            else:
                results.append(StepResult(name=f"nav:{label}", ok=True, detail=current))
        except Exception as exc:
            results.append(StepResult(name=f"nav:{label}", ok=False, detail=str(exc)))
            _goto(page, base_url, "/dashboard", expect_text="Executive Overview")
    return results


def _run_browser_flows(base_url: str) -> list[StepResult]:
    results: list[StepResult] = []
    unique_suffix = str(int(time.time()))
    contract_number = f"E2E-{unique_suffix}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        net_events: list[str] = []

        def _record_net_event(event: str) -> None:
            net_events.append(event)
            if len(net_events) > 120:
                del net_events[:20]

        def _attach_page_events(active_page: Page) -> None:
            active_page.on("request", lambda req: _record_net_event(f">> {req.method} {req.url}"))
            active_page.on("response", lambda resp: _record_net_event(f"<< {resp.status} {resp.url}"))
            active_page.on(
                "dialog",
                lambda dialog: (dialog.dismiss(), _record_net_event(f"!! dialog:{dialog.type} {dialog.message}")),
            )

        _attach_page_events(page)

        def run_step(name: str, fn: Callable[[], str | None]) -> None:
            try:
                detail = fn() or ""
                results.append(StepResult(name=name, ok=True, detail=detail))
            except Exception as exc:
                net_tail = " | ".join(net_events[-10:])
                detail = str(exc)
                if net_tail:
                    detail = f"{detail} | net_tail={net_tail}"
                results.append(StepResult(name=name, ok=False, detail=detail))

        run_step(
            "dashboard_load",
            lambda: (_goto(page, base_url, "/dashboard", expect_text="Executive Overview"), "ok")[1],
        )
        results.extend(_click_nav_links(page, base_url))

        vendor_state: dict[str, str] = {}

        def create_vendor() -> str:
            nonlocal browser, context, page
            _goto(page, base_url, "/vendors/new?return_to=%2Fvendors", expect_text="New Vendor")
            page.fill("input[name='legal_name']", f"E2E Vendor {unique_suffix} LLC")
            page.fill("input[name='display_name']", f"E2E Vendor {unique_suffix}")
            _select_option_best_effort(page, "select[name='lifecycle_state']", ["draft", "active"])
            if page.locator("select[name='owner_org_choice']").count():
                owner_select = page.locator("select[name='owner_org_choice']")
                options = owner_select.locator("option")
                selected = False
                for idx in range(options.count()):
                    value = str(options.nth(idx).get_attribute("value") or "").strip()
                    if value and value not in {"", "__new__"}:
                        owner_select.select_option(value=value)
                        selected = True
                        break
                if not selected:
                    owner_select.select_option(value="__new__")
                    page.fill("input[name='new_owner_org_id']", f"E2E-ORG-{unique_suffix}")
            elif page.locator("input[name='owner_org_id']").count():
                page.fill("input[name='owner_org_id']", "IT-ENT")
            _select_option_best_effort(page, "select[name='risk_tier']", ["low", "medium", "high"])
            if page.locator("input[name='source_system']").count():
                page.fill("input[name='source_system']", "manual")
            page.locator("button:has-text('Create Vendor')").first.click()
            page.wait_for_load_state("networkidle")
            m = re.search(r"/vendors/(vnd-[^/]+)/summary", page.url)
            if not m:
                raise RuntimeError(f"Vendor create redirect missing vendor id. url={page.url}")
            vendor_state["vendor_id"] = m.group(1)
            # Reset browser process after write/redirect chain to avoid stale socket state.
            browser.close()
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            _attach_page_events(page)
            return vendor_state["vendor_id"]

        run_step("create_vendor", create_vendor)

        def add_vendor_ownership() -> str:
            vendor_id = vendor_state["vendor_id"]
            _goto(page, base_url, f"/vendors/{vendor_id}/ownership?return_to=%2Fvendors", expect_text="Ownership")

            owner_form = page.locator(f"form[action='/vendors/{vendor_id}/owners/add']").first
            display_name_input = owner_form.locator("input[name='owner_user_principal_display_name']").first
            display_name_results = display_name_input.locator(
                "xpath=following-sibling::div[contains(@class,'typeahead-results')]"
            ).first
            display_name_input.fill("admin")
            display_name_results.locator("button.typeahead-option").first.wait_for(timeout=15000)
            display_name_results.locator("button.typeahead-option", has_text="Admin User").first.click()

            email_input = owner_form.locator("input[name='owner_user_principal']").first
            email_results = email_input.locator(
                "xpath=following-sibling::div[contains(@class,'typeahead-results')]"
            ).first
            email_value = str(email_input.input_value() or "").strip().lower()
            display_value = str(display_name_input.input_value() or "").strip().lower()
            if email_value != "admin@example.com":
                raise RuntimeError(f"Owner email field not synced from display selection. value={email_value}")
            if "admin" not in display_value:
                raise RuntimeError(f"Owner display-name field not populated from selection. value={display_value}")

            display_name_input.fill("")
            email_input.fill("admin@example.com")
            email_results.locator("button.typeahead-option").first.wait_for(timeout=15000)
            email_results.locator("button.typeahead-option", has_text="Admin User").first.click()
            display_after_email_pick = str(display_name_input.input_value() or "").strip().lower()
            if "admin" not in display_after_email_pick:
                raise RuntimeError(
                    "Owner display-name field not synced from email selection. "
                    f"value={display_after_email_pick}"
                )

            _select_option_best_effort(page, f"form[action='/vendors/{vendor_id}/owners/add'] select[name='owner_role']", ["business_owner"])
            owner_form.locator("input[name='reason']").fill("E2E owner add")
            owner_form.locator("button:has-text('Add Owner')").click()
            page.wait_for_load_state("networkidle")

            assign_action = f"/vendors/{vendor_id}/lob-assignments/add"
            if page.locator(f"form[action='{assign_action}']").count() == 0:
                assign_action = f"/vendors/{vendor_id}/org-assignments/add"
            assign_form = page.locator(f"form[action='{assign_action}']").first
            assign_form.locator("input[name='org_id']").fill(f"E2E-ORG-{unique_suffix}")
            _select_option_best_effort(page, f"form[action='{assign_action}'] select[name='assignment_type']", ["consumer"])
            assign_form.locator("input[name='reason']").fill("E2E LOB assignment")
            assign_form.locator("button:has-text('Add Assignment')").click()
            page.wait_for_load_state("networkidle")

            contact_form = page.locator(f"form[action='/vendors/{vendor_id}/contacts/add']").first
            contact_form.locator("input[name='full_name']").fill("E2E Contact")
            _select_option_best_effort(page, f"form[action='/vendors/{vendor_id}/contacts/add'] select[name='contact_type']", ["support"])
            contact_form.locator("input[name='email']").fill(f"e2e.contact.{unique_suffix}@example.com")
            contact_form.locator("input[name='phone']").fill("555-0000")
            contact_form.locator("input[name='reason']").fill("E2E contact add")
            contact_form.locator("button:has-text('Add Contact')").click()
            page.wait_for_load_state("networkidle")

            body = page.content()
            if "admin@example.com" not in body:
                raise RuntimeError("Owner add did not render expected user principal.")
            if "E2E Contact" not in body:
                raise RuntimeError("Ownership additions did not render expected contact row.")
            return "owner+assignment+contact added"

        run_step("add_vendor_ownership", add_vendor_ownership)

        def create_offering() -> str:
            vendor_id = vendor_state["vendor_id"]
            _goto(
                page,
                base_url,
                f"/vendors/{vendor_id}/offerings/new?return_to=%2Fvendors",
                expect_text="New Offering",
            )
            page.fill("input[name='offering_name']", f"E2E Offering {unique_suffix}")
            _select_option_best_effort(page, "select[name='offering_type']", ["SaaS", "Platform"])
            _select_option_best_effort(page, "select[name='lob']", ["Finance", "Enterprise"])
            _select_option_best_effort(page, "select[name='service_type']", ["Application", "Platform"])
            _select_option_best_effort(page, "select[name='lifecycle_state']", ["active", "draft"])
            _select_option_best_effort(page, "select[name='criticality_tier']", ["tier_2", "tier_1"])
            page.locator("button:has-text('Create Offering')").first.click()
            page.wait_for_load_state("networkidle")
            m = re.search(rf"/vendors/{vendor_id}/offerings/(off-[^/?]+)", page.url)
            if not m:
                raise RuntimeError(f"Offering create redirect missing offering id. url={page.url}")
            vendor_state["offering_id"] = m.group(1)
            return vendor_state["offering_id"]

        run_step("create_offering", create_offering)

        def add_contract() -> str:
            vendor_id = vendor_state["vendor_id"]
            offering_id = vendor_state["offering_id"]
            _goto(page, base_url, f"/vendors/{vendor_id}/contracts?return_to=%2Fvendors", expect_text="Contracts")
            form = page.locator(f"form[action='/vendors/{vendor_id}/contracts/add']").first
            form.locator("input[name='contract_number']").fill(contract_number)
            _select_option_best_effort(page, f"form[action='/vendors/{vendor_id}/contracts/add'] select[name='offering_id']", [offering_id])
            _select_option_best_effort(page, f"form[action='/vendors/{vendor_id}/contracts/add'] select[name='contract_status']", ["active"])
            form.locator("input[name='start_date']").fill("2026-03-01")
            form.locator("input[name='end_date']").fill("2027-02-28")
            form.locator("input[name='annual_value']").fill("12345.67")
            form.locator("input[name='reason']").fill("E2E contract add")
            form.locator("button:has-text('Add Contract')").click()
            page.wait_for_load_state("networkidle")
            if contract_number not in page.content():
                raise RuntimeError("Added contract not visible on contracts page.")
            return contract_number

        run_step("add_contract", add_contract)

        def add_demo_outcome() -> str:
            vendor_id = vendor_state["vendor_id"]
            offering_id = vendor_state["offering_id"]
            _goto(page, base_url, "/demos", expect_text="Demo Outcomes")
            form = page.locator("form[action='/demos'][method='post']").first
            form.locator("input[name='vendor_id']").fill(vendor_id)
            form.locator("input[name='offering_id']").fill(offering_id)
            form.locator("input[name='demo_date']").fill("2026-02-10")
            form.locator("input[name='overall_score']").fill("8.1")
            _select_option_best_effort(page, "form[action='/demos'] select[name='selection_outcome']", ["selected"])
            note_text = f"E2E demo note {unique_suffix}"
            form.locator("textarea[name='notes']").fill(note_text)
            form.locator("button:has-text('Save Demo Outcome')").click()
            page.wait_for_load_state("networkidle")
            if note_text not in page.content():
                raise RuntimeError("Saved demo outcome note not visible on demos page.")
            return "demo outcome saved"

        run_step("add_demo_outcome", add_demo_outcome)

        def create_project() -> str:
            vendor_id = vendor_state["vendor_id"]
            _goto(
                page,
                base_url,
                f"/vendors/{vendor_id}/projects/new?return_to=%2Fvendors",
                expect_text="New Project",
            )
            form = page.locator(f"form[action='/vendors/{vendor_id}/projects/new']").first
            form.locator("input[name='project_name']").fill(f"E2E Project {unique_suffix}")
            _select_option_best_effort(page, f"form[action='/vendors/{vendor_id}/projects/new'] select[name='project_type']", ["renewal", "implementation"])
            _select_option_best_effort(page, f"form[action='/vendors/{vendor_id}/projects/new'] select[name='status']", ["active", "draft"])
            form.locator("input[name='start_date']").fill("2026-02-01")
            form.locator("input[name='target_date']").fill("2026-04-15")
            form.locator("input[name='owner_principal']").fill("admin@example.com")
            form.locator("textarea[name='description']").fill("E2E project creation")
            form.locator("button:has-text('Create Project')").click()
            page.wait_for_load_state("networkidle")
            m = re.search(r"/projects/(prj-[^/]+)/summary", page.url)
            if not m:
                raise RuntimeError(f"Project create redirect missing project id. url={page.url}")
            vendor_state["project_id"] = m.group(1)
            return vendor_state["project_id"]

        run_step("create_project", create_project)

        def submit_and_approve_workflow() -> str:
            vendor_id = vendor_state["vendor_id"]
            _goto(page, base_url, f"/vendors/{vendor_id}/changes?return_to=%2Fvendors", expect_text="Change Actions")
            form = page.locator(f"form[action='/vendors/{vendor_id}/change-request']").first
            _select_option_best_effort(
                page,
                f"form[action='/vendors/{vendor_id}/change-request'] select[name='change_type']",
                ["update_vendor_profile"],
            )
            form.locator("textarea[name='change_notes']").fill("E2E change request")
            form.locator("button:has-text('Submit Change Request')").click()
            page.wait_for_load_state("networkidle")

            page_text = page.text_content("body") or ""
            match = re.search(r"Change request submitted:\s*([0-9a-f-]{36})", page_text, re.IGNORECASE)
            request_id = match.group(1) if match else ""

            _goto(page, base_url, "/workflows?status=pending", expect_text="Pending Approvals")
            if request_id and request_id not in (page.text_content("body") or ""):
                raise RuntimeError(f"Created request id {request_id} not visible in workflow queue.")

            quick_approve = page.locator("button:has-text('Quick Approve')").first
            if quick_approve.count():
                quick_approve.click()
                page.wait_for_load_state("networkidle")
            return request_id or "request-submitted"

        run_step("submit_and_approve_workflow", submit_and_approve_workflow)

        def admin_defaults_add_option() -> str:
            _goto(page, base_url, "/admin?section=defaults", expect_text="Defaults Catalog")
            form = page.locator("form[action='/admin/lookup/save']:has(input[placeholder='New label'])").first
            if form.count() == 0:
                raise RuntimeError("Admin defaults add-option form not found.")
            label = f"E2E Option {unique_suffix}"
            form.locator("input[name='option_label']").fill(label)
            form.locator("input[name='sort_order']").fill("999")
            form.locator("input[name='valid_from_ts']").fill("2026-01-01")
            form.locator("input[name='valid_to_ts']").fill("9999-12-31")
            form.locator("button:has-text('Add Option')").click()
            page.wait_for_load_state("networkidle")
            if label not in page.content():
                raise RuntimeError("Added admin default option not rendered in table.")
            return label

        def admin_ownership_reassign() -> str:
            _goto(
                page,
                base_url,
                "/admin?section=ownership&source_owner=admin%40example.com",
                expect_text="Ownership Reassignment",
            )
            rows = page.locator("input[name='selected_assignment_key']")
            if rows.count() == 0:
                raise RuntimeError("No ownership rows available for admin source owner.")

            rows.first.check()
            page.locator("input[name='default_target_owner']").fill("pm@example.com")
            page.locator("select[name='action_mode']").select_option("selected_default")
            page.locator("button:has-text('Apply Reassignment')").first.click()
            page.wait_for_load_state("networkidle")

            body = page.text_content("body") or ""
            if "Ownership reassignment complete." not in body:
                raise RuntimeError("Ownership reassignment success message not shown.")
            return "ownership reassignment applied"

        run_step("admin_ownership_reassign", admin_ownership_reassign)
        run_step("admin_defaults_add_option", admin_defaults_add_option)

        def imports_page_smoke() -> str:
            _goto(page, base_url, "/imports", expect_text="Data Imports")
            upload_button = page.locator("button:has-text('Upload And Preview')").first
            if upload_button.count() == 0:
                raise RuntimeError("Imports upload button not present.")
            return "imports ui present"

        run_step("imports_page_smoke", imports_page_smoke)

        context.close()
        browser.close()
    return results


def _read_log_tail(path: Path, max_lines: int = 400) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[-max_lines:])


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    tmp_dir = Path(tempfile.mkdtemp(prefix="tvendor_e2e_"))
    db_path = tmp_dir / "tvendor_local.db"
    base_url = "http://127.0.0.1:8010"

    init_cmd = [
        sys.executable,
        str(repo_root / "setup" / "local_db" / "init_local_db.py"),
        "--db-path",
        str(db_path),
        "--reset",
    ]
    init_proc = subprocess.run(init_cmd, cwd=str(repo_root), capture_output=True, text=True, check=False)
    if init_proc.returncode != 0:
        print("Failed to initialize local db for e2e run.")
        print(init_proc.stdout)
        print(init_proc.stderr)
        return 2

    env = os.environ.copy()
    env.update(
        {
            "TVENDOR_ENV": "dev",
            "TVENDOR_USE_LOCAL_DB": "true",
            "TVENDOR_LOCAL_DB_PATH": str(db_path),
            "TVENDOR_TEST_USER": "admin@example.com",
            "TVENDOR_SESSION_SECRET": "e2e-session-secret",
            "TVENDOR_OPEN_BROWSER": "false",
            "TVENDOR_CSRF_ENABLED": "true",
            "PORT": "8010",
        }
    )
    server_cmd = [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8010"]
    server_log_path = tmp_dir / "server.log"
    server_log_file = server_log_path.open("w", encoding="utf-8")
    server_proc = subprocess.Popen(
        server_cmd,
        cwd=str(repo_root / "app"),
        env=env,
        stdout=server_log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )
    server_output = ""
    try:
        try:
            _wait_for_http_ready(f"{base_url}/api/health", timeout_sec=90)
        except Exception:
            print("Server failed readiness check. Startup output:")
            server_log_file.flush()
            print(_read_log_tail(server_log_path))
            raise
        results = _run_browser_flows(base_url)
    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=15)
        except Exception:
            server_proc.kill()
            server_proc.wait(timeout=5)
        server_log_file.flush()
        server_log_file.close()
        server_output = _read_log_tail(server_log_path, max_lines=4000)

    passed = sum(1 for item in results if item.ok)
    failed = [item for item in results if not item.ok]
    print(json.dumps([item.__dict__ for item in results], indent=2))
    print(f"\nSummary: {passed}/{len(results)} steps passed.")
    if failed:
        print("Failed steps:")
        for item in failed:
            print(f"- {item.name}: {item.detail}")
        if server_output.strip():
            print("\nServer output tail:")
            tail_lines = server_output.strip().splitlines()[-120:]
            print("\n".join(tail_lines))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
