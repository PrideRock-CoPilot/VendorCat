# Repository Structure

## Overview
This repository is organized into **current build** (active development) and **archive** (legacy/reference).

---

## 📊 Current Build Structure

The active development environment consists of:

### Core Application
- **`src/`** - Django 5 vendor catalog application
  - `manage.py` - Django management entry point
  - `apps/` - Django application modules (vendors, contracts, etc.)
  - `templates/` - Jinja2 templates for vendor UI
  - `static/` - CSS, JavaScript, and assets
  - `schema/` - Database models

### Testing
- **`tests/`** - Current unit and integration tests (pytest)
  - Covers API endpoints, database operations, workflows
  - 33+ test modules with comprehensive coverage

- **`tests_rebuild/`** - Rebuild-specific integration tests
  - Phase 4/5/6 contract testing
  - Access control and RBAC verification
  - Import workflow testing

### Documentation & Configuration
- **`docs/`** - Project documentation
  - CHANGELOG.md, production-readiness.md
  - Architecture, configuration, operations guides
  - UI/UX and governance documentation

- **`deploy/`** - Deployment configuration
  - Databricks sync scripts
  - Production/staging configurations

- **`scripts/`** - Build and utility scripts
  - Database rebuild scripts
  - Migration helpers

- **`setup/`** - Setup utilities
  - Local database bootstrap
  - Databricks configuration
  - v1 schema creation

- **`pyproject.toml`** - Python project configuration (dependencies, build metadata)
- **`databricks.yml`** - Active Databricks workspace configuration
- **`README.md`** - Project overview and quick start

---

## 📦 Archive Structure

Legacy files, older implementations, and historical artifacts are organized in `archive/`:

### `legacy-dev-artifacts/`
Old development files and configurations (22 items)

### `legacy-setup/`
Historical setup scripts:
- `add_user_notebook.sql` - Old user onboarding
- `add_user_to_directory.py` - User directory setup
- Database initialization scripts

### `legacy-test-artifacts/`
Old test files and screenshots (20 items):
- Historical test Python files (test_app_layout_children.py, etc.)
- Dashboard screenshots (PNG files)
- Old HTML mockups

### `old-configuration/`
Deprecated configuration files (5 items):
- `requirements-rebuild.txt` - Old dependency list
- `mypy-rebuild.ini` - Old type checking config
- Test scripts (test_api.ps1, test_api_auth.ps1)
- DELIVERY_SUMMARY.md - Old delivery notes

### `old-revisions/`
Historical revision/branch tracking (8 items)

### `original-build/` ⭐
**Complete FastAPI implementation** (980 items)
- Fully functional FastAPI vendor catalog
- Contains production-ready endpoints
- ~70% feature parity with legacy system
- Kept as reference/alternative implementation
- Located at: `archive/original-build/`

### `schema_creation/`
Historical database schema creation scripts (4 items)

### `sql_catalog/`
Historical SQL scripts and migrations (205 items)

---

## 🚀 Getting Started

### For Active Development:
```bash
cd src/
python manage.py runserver 0.0.0.0:8011
```

### For Running Tests:
```bash
# Current test suite
pytest tests/ -v

# Rebuild tests
pytest tests_rebuild/ -v --tb=short
```

### For Reference (Legacy):
If you need to reference the FastAPI implementation:
```bash
# View complete FastAPI app
ls archive/original-build/app/
```

---

## 📋 Directory Cleanup Summary

**Moved to Archive:**
- ✅ All legacy test files → `legacy-test-artifacts/`
- ✅ All old setup scripts → `legacy-setup/`, `old-configuration/`
- ✅ Screenshots and mockups → `legacy-test-artifacts/`
- ✅ Revision history → `old-revisions/`
- ✅ FastAPI implementation → `original-build/`
- ✅ Temporary rebuild logs → `legacy-test-artifacts/`

**Result:** Clean root directory with only essential files for current Django build.

---

## 📝 Notes

- **Primary focus**: Django 5 rebuild with progressive feature restoration
- **Reference implementation**: FastAPI (stored in `archive/original-build/`)
- **Feature restoration plan**: See `docs/` for detailed roadmap
- **All legacy code preserved**: Nothing deleted, safely archived for reference

---

Last updated: February 2026
