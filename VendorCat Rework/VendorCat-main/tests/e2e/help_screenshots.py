"""
Playwright-based screenshot automation for Help Center articles.
Captures screenshots of key app pages for documentation purposes.
Can be run standalone to regenerate all screenshots.
Usage: python tests/e2e/help_screenshots.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import Page, sync_playwright


@dataclass
class Screenshot:
    """Screenshot metadata and capture parameters."""
    path: str
    name: str  # kebab-case filename for output
    expect_text: str | None = None
    viewport_width: int = 1280
    viewport_height: int = 1024
    wait_for_selector: str | None = None
    delay_ms: int = 500  # additional delay after page load


# Define all screenshots needed for Help articles
HELP_SCREENSHOTS = [
    # Vendor workflows
    Screenshot(
        path="/vendors",
        name="vendor-360-list",
        expect_text="Vendors",
        wait_for_selector=".vendor-list, [data-testid='vendor-list']"
    ),
    Screenshot(
        path="/vendors",
        name="vendor-list-filters",
        expect_text="Vendors",
        wait_for_selector=".vendor-filters, [data-testid='vendor-filters']"
    ),
    Screenshot(
        path="/vendors/new",
        name="vendor-form-new",
        expect_text="New",
        wait_for_selector=".form-container, [data-testid='vendor-form']",
        delay_ms=800
    ),

    # Project workflows
    Screenshot(
        path="/projects",
        name="project-list-view",
        expect_text="Projects",
        wait_for_selector=".project-list, [data-testid='project-list']"
    ),
    Screenshot(
        path="/projects",
        name="project-filters-status",
        expect_text="Projects",
        wait_for_selector=".filter-section, [data-testid='filter-section']"
    ),

    # Demo workflows
    Screenshot(
        path="/demos",
        name="demo-catalog-list",
        expect_text="Demo",
        wait_for_selector=".demo-list, [data-testid='demo-list']"
    ),

    # Admin portal
    Screenshot(
        path="/admin",
        name="admin-defaults-catalog",
        expect_text="Default",
        wait_for_selector=".admin-panel, [data-testid='admin-panel']",
        delay_ms=800
    ),
    Screenshot(
        path="/admin?section=defaults",
        name="admin-section-defaults",
        expect_text="Default",
        wait_for_selector=".settings-grid, [data-testid='settings-grid']",
        delay_ms=800
    ),
    Screenshot(
        path="/admin?section=access",
        name="admin-access-roles",
        expect_text="Access",
        wait_for_selector=".role-table, [data-testid='role-table']",
        delay_ms=800
    ),

    # Help Center index
    Screenshot(
        path="/help",
        name="help-center-index",
        expect_text="Help",
        wait_for_selector=".help-training, [data-testid='help-training']",
        delay_ms=1000
    ),

    # Sample help articles
    Screenshot(
        path="/help/add-vendor",
        name="help-add-vendor-article",
        expect_text="Vendor",
        wait_for_selector=".article-content, [data-testid='article-content']",
        delay_ms=800
    ),
    Screenshot(
        path="/help/create-project",
        name="help-create-project-article",
        expect_text="Project",
        wait_for_selector=".article-content, [data-testid='article-content']",
        delay_ms=800
    ),
    Screenshot(
        path="/help/user-roles",
        name="help-user-roles-article",
        expect_text="Role",
        wait_for_selector=".article-content, [data-testid='article-content']",
        delay_ms=800
    ),

    # Dashboard
    Screenshot(
        path="/dashboard",
        name="dashboard-main-view",
        expect_text="Dashboard",
        wait_for_selector=".dashboard, [data-testid='dashboard']",
        delay_ms=1000
    ),
]


def _wait_for_http_ready(url: str, timeout_sec: int = 60) -> None:
    """Wait for HTTP server to be ready."""
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
    """Navigate to a page with safety checks."""
    response = page.goto(f"{base_url}{path}", wait_until="domcontentloaded", timeout=120000)
    if response is None or response.status >= 500:
        status = "none" if response is None else str(response.status)
        raise RuntimeError(f"GET {path} failed with status={status}")
    if expect_text:
        try:
            page.get_by_text(expect_text, exact=False).first.wait_for(timeout=15000)
        except Exception as e:
            print(f"  ⚠ Warning: expected text '{expect_text}' not found on {path}: {e}")


def capture_screenshot(page: Page, base_url: str, screenshot: Screenshot, output_dir: Path) -> bool:
    """Capture a single screenshot. Returns True if successful."""
    try:
        print(f"  Capturing: {screenshot.name}...", end=" ", flush=True)

        # Set viewport
        page.set_viewport_size({"width": screenshot.viewport_width, "height": screenshot.viewport_height})

        # Navigate
        _goto(page, base_url, screenshot.path, screenshot.expect_text)

        # Wait for specific elements if provided
        if screenshot.wait_for_selector:
            try:
                page.wait_for_selector(screenshot.wait_for_selector, timeout=10000)
            except Exception:
                # Selector not found, but continue - take screenshot anyway
                pass

        # Additional delay for dynamic content
        if screenshot.delay_ms > 0:
            page.wait_for_timeout(screenshot.delay_ms)

        # Capture screenshot
        output_path = output_dir / f"{screenshot.name}.png"
        page.screenshot(path=str(output_path), full_page=False)
        print(f"✓ ({output_path.name})")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main() -> int:
    """Main entry point."""
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    server_port = 8000

    # Create output directory
    output_dir = Path(__file__).parent.parent.parent / "app" / "vendor_catalog_app" / "web" / "static" / "help" / "screenshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    print("\n📸 Help Center Screenshot Automation")
    print(f"   Output directory: {output_dir}")
    print(f"   Base URL: {base_url}")
    print()

    # Check if server is already running
    server_running = False
    try:
        with urlopen(f"{base_url}/health", timeout=2):
            server_running = True
            print(f"✓ Server already running at {base_url}")
    except Exception:
        print(f"Server not running at {base_url}")
        print("Starting local development server...")

        # Start the app in dev mode
        app_dir = Path(__file__).parent.parent.parent / "app"
        env = os.environ.copy()
        env["TVENDOR_DEV_ALLOW_ALL_ACCESS"] = "true"
        env["TVENDOR_DB_MODE"] = "local"

        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "localhost", "--port", str(server_port)],
            cwd=str(app_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for server to be ready
        try:
            _wait_for_http_ready(f"{base_url}/health", timeout_sec=30)
            print(f"✓ Server started (PID: {proc.pid})")
            server_running = True
        except RuntimeError as e:
            print(f"✗ Failed to start server: {e}")
            proc.terminate()
            return 1

    # Capture screenshots
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(screen={"width": 1920, "height": 1080})
            page = context.new_page()

            print(f"\n📹 Capturing {len(HELP_SCREENSHOTS)} screenshots...")
            successful = 0
            failed = 0

            for screenshot in HELP_SCREENSHOTS:
                if capture_screenshot(page, base_url, screenshot, output_dir):
                    successful += 1
                else:
                    failed += 1

            page.close()
            context.close()
            browser.close()

            print(f"\n✓ Complete: {successful} successful, {failed} failed")
            print(f"📂 Screenshots saved to: {output_dir}")
            return 0
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Clean up server if we started it and it's still running
        if not server_running and "proc" in locals():
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
