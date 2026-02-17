# Help Center Screenshot Automation

This document describes how to generate and maintain screenshots for Help Center articles using Playwright automation.

## Overview

Screenshots are stored in `app/vendor_catalog_app/web/static/help/screenshots/` and are embedded in Help articles using standard Markdown image syntax:

```markdown
![Screenshot description](/static/help/screenshots/image-name.png)
```

When the app UI changes, screenshots can be automatically regenerated to stay in sync with the current user interface.

## Quick Start: Generate All Screenshots

### Prerequisites
- Python 3.8+ with venv/conda configured
- Playwright browsers installed
- Development environment variables configured

### Running the Screenshot Generator

```bash
# From the workspace root
python tests/e2e/help_screenshots.py
```

The script will:
1. Check if the dev server is running at `http://localhost:8000`
2. Start the server if needed (in dev mode with sample data)
3. Capture 15+ key pages at standard resolution (1280×1024)
4. Save PNG files to `app/vendor_catalog_app/web/static/help/screenshots/`
5. Report success/failure for each screenshot

### Expected Output

```
📸 Help Center Screenshot Automation
   Output directory: .../app/vendor_catalog_app/web/static/help/screenshots
   Base URL: http://localhost:8000

✓ Server already running at http://localhost:8000
📹 Capturing 15 screenshots...
  Capturing: vendor-360-list... ✓ (vendor-360-list.png)
  Capturing: vendor-detail-summary... ✓ (vendor-detail-summary.png)
  ...
✓ Complete: 15 successful, 0 failed
📂 Screenshots saved to: .../help/screenshots
```

## Screenshot Naming Convention

Screenshots use **kebab-case names** following this pattern:

| Feature | Screenshot | Route |
|---------|-----------|-------|
| **Vendor Workflows** |
| Vendor List | `vendor-360-list.png` | `/vendors` |
| Vendor Detail | `vendor-detail-summary.png` | `/vendors/{id}` |
| Vendor Offerings | `vendor-detail-offerings.png` | `/vendors/{id}#offerings` |
| Vendor Ownership | `vendor-ownership-section.png` | `/vendors/{id}#ownership` |
| Vendor Unassigned | `vendor-offerings-unassigned.png` | `/vendors/{id}#offerings` |
| Vendor Edit Form | `vendor-edit-form.png` | `/vendors/{id}/edit` |
| Vendor Changes | `vendor-changes-section.png` | `/vendors/{id}#changes` |
| **Offering Workflows** |
| Offering Profile | `offering-profile-edit.png` | `/vendors/{id}/offerings/{id}#profile` |
| **Project Workflows** |
| Projects List | `project-list-view.png` | `/projects` |
| Project Detail | `project-detail-summary.png` | `/projects/{id}` |
| Project Demos | `project-demos-section.png` | `/projects/{id}#demos` |
| Project Linked | `project-linked-vendors.png` | `/projects/{id}/edit` |
| Project Edit Form | `project-edit-form.png` | `/projects/{id}/edit` |
| **Demo Workflows** |
| Demo List | `demo-catalog-list.png` | `/demos` |
| Demo Detail | `demo-workspace-stage.png` | `/demos/{id}` |
| **Documents** |
| Add Document Link | `documents-add-link.png` | `/vendors/{id}#documents` |
| **Admin Portal** |
| Admin Defaults | `admin-defaults-catalog.png` | `/admin?section=defaults` |
| Admin Defaults Detail | `admin-section-defaults.png` | `/admin?section=defaults` |
| Admin Access/Roles | `admin-access-roles.png` | `/admin?section=access` |
| **Help Center** |
| Help Index | `help-center-index.png` | `/help` |
| Help Articles | `help-{article-slug}-article.png` | `/help/{article-slug}` |
| **Dashboard** |
| Dashboard Main | `dashboard-main-view.png` | `/dashboard` |

## Help Article Image References

All Help articles in `setup/local_db/sql/seed/002_seed_help_center.sql` that include screenshots use the format:

```markdown
![Screenshot: Description](/static/help/screenshots/image-name.png)
```

Example from "Add a new vendor" article:

```markdown
## Scenario
You onboard a new vendor for a project kickoff.

## Navigate
- Vendor 360: /vendors
- Create vendor: /vendors/new

![Vendor 360 list with New Vendor button](/static/help/screenshots/vendor-360-list.png)

## Steps
1. Open Vendor 360 and select New Vendor.
...
```

## Customizing Screenshot Capture

To modify which pages are captured or add new screenshots, edit `tests/e2e/help_screenshots.py`:

### Screenshot object structure

```python
Screenshot(
    path="/vendors",                          # URL path to capture
    name="vendor-360-list",                   # Output filename (kebab-case)
    expect_text="Vendors",                    # Text to wait for (optional)
    viewport_width=1280,                      # Default: 1280
    viewport_height=1024,                     # Default: 1024
    wait_for_selector=".vendor-list",         # Selector to wait for (optional)
    delay_ms=500                              # Extra delay for dynamic content
)
```

### Example: Adding a new screenshot

```python
HELP_SCREENSHOTS = [
    # ... existing screenshots ...
    
    # New feature
    Screenshot(
        path="/contracts",
        name="contracts-list-view",
        expect_text="Contracts",
        wait_for_selector=".contract-list, [data-testid='contract-list']",
        delay_ms=500
    ),
]
```

Then update the help articles to reference the new screenshot:

```markdown
![Contracts list view](/static/help/screenshots/contracts-list-view.png)
```

## Automated Screenshot Regeneration (CI/CD)

The `help_screenshots.py` script can be integrated into CI/CD pipelines to regenerate screenshots automatically on every code change:

### GitHub Actions Example

```yaml
name: Regenerate Help Screenshots
on: [push]
jobs:
  screenshots:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r app/requirements.txt
          python -m playwright install chromium
      - name: Generate screenshots
        run: python tests/e2e/help_screenshots.py
      - name: Commit changes
        run: |
          git config user.email "bot@example.com"
          git config user.name "Screenshot Bot"
          git add app/vendor_catalog_app/web/static/help/screenshots/
          git commit -m "🤖 Auto-update Help screenshots" || echo "No changes"
          git push
```

### Local Development Workflow

1. Make UI changes (component styles, layouts, forms)
2. Run: `python tests/e2e/help_screenshots.py`
3. Review generated screenshots for correctness
4. Commit updated images: `git add -A app/vendor_catalog_app/web/static/help/screenshots/`
5. Push changes

## Troubleshooting

### Screenshots are not appearing in Help articles

**Problem**: Images render as broken links.

**Solutions**:
- Verify image files exist in `app/vendor_catalog_app/web/static/help/screenshots/`
- Check image filename matches exactly (case-sensitive on Linux/Mac)
- Ensure `img` tag is in `_ALLOWED_TAGS` in `app/vendor_catalog_app/web/utils/markdown.py`
- Clear browser cache (Ctrl+Shift+Delete or Cmd+Shift+Delete)
- Restart dev server

### Screenshot capture fails or hangs

**Problem**: Script exits with timeout or "element not found" error.

**Solutions**:
- Verify server is running: `curl http://localhost:8000/health`
- Check if pages have loaded correctly (manually navigate in browser)
- Increase timeout or `delay_ms` in `help_screenshots.py` for slow pages
- Check for JavaScript errors in browser console

### Dev server won't start

**Problem**: Script fails to start `uvicorn` server.

**Solutions**:
- Check Python environment: `python -m pip list | grep -E 'fastapi|uvicorn'`
- Verify port 8000 is not in use: `lsof -i :8000` (Mac/Linux) or `netstat -ano | findstr :8000` (Windows)
- Ensure dev environment variables are set:
  ```bash
  export TVENDOR_DEV_ALLOW_ALL_ACCESS=true
  export TVENDOR_DB_MODE=local
  export FLASK_ENV=development  # if applicable
  ```

### Playwright browsers not installed

**Problem**: `Error: failed to launch browser`

**Solutions**:
```bash
# Install Chromium for Playwright
python -m playwright install chromium
```

## Performance Notes

- Screenshot capture typically takes 30-60 seconds total
- Each screenshot is 1-3 MB PNG at 1280×1024 resolution
- Total directory size: ~50+ MB for all screenshots

For faster iteration during development, you can capture individual screenshots by temporarily modifying `HELP_SCREENSHOTS` list to include only the ones you're working on.

## Related Files

- **Generator script**: `tests/e2e/help_screenshots.py`
- **Screenshot directory**: `app/vendor_catalog_app/web/static/help/screenshots/`
- **Markdown renderer**: `app/vendor_catalog_app/web/utils/markdown.py`
- **Help seed data**: `setup/local_db/sql/seed/002_seed_help_center.sql`
- **Help template**: `app/vendor_catalog_app/web/templates/help_center.html`

## Future Enhancements

- [ ] Add visual diff comparison tool to detect unexpected UI changes
- [ ] Integrate with visual regression testing (Percy, BackstopJS)
- [ ] Generate responsive screenshots at multiple breakpoints (mobile, tablet, desktop)
- [ ] Add screenshot watermarks or annotations for clarity
- [ ] Create thumbnail gallery for preview before commit
