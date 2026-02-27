# CI Quality Gates

This document defines the exact checks that run in CI, how to run them locally, and how to triage failures.

## CI Pipeline Overview

File: `.github/workflows/ci.yml`

**Trigger**: Every push to any branch, every PR

**Jobs**:
1. **Test**: Run pytest suite
2. **Lint**: Run ruff linter
3. **Type Check**: Run mypy type checker
4. **Coverage**: Verify test coverage >= 80%
5. **RBAC Coverage**: Verify all mutation endpoints have permission checks
6. **Data Governance Guards**: No legacy `lob` runtime terms, governed dropdowns remain lookup-backed
7. **Security Scan**: Check for known vulnerabilities (future)

**Total Runtime**: ~3-5 minutes

## Job Definitions

### Job 1: Test

**Purpose**: Ensure all tests pass

**Command**:
```bash
pytest tests/ -v --tb=short
```

**Pass Criteria**: All tests pass, exit code 0

**Failure Triage**:
1. Read test failure output for failing test name
2. Run failing test locally: `pytest tests/test_file.py::test_name -v`
3. Check if test is flaky (re-run 3 times)
4. If consistent failure, fix code or update test

**Common Failures**:
- Database connection errors: Check Databricks config in env
- Fixture errors: Ensure conftest.py fixtures available
- Assertion errors: Code change broke expected behavior

---

### Job 2: Lint

**Purpose**: Enforce code style and detect common errors

**Command**:
```bash
ruff check app/ tests/ --config .ruff.toml
```

**Pass Criteria**: No linting errors, exit code 0

**Failure Triage**:
1. Run locally: `ruff check app/ tests/`
2. Read error message for file and line number
3. Fix manually or run auto-fix: `ruff check --fix app/ tests/`
4. Re-run to verify fix

**Common Failures**:
- Unused imports: Remove them or add `# noqa: F401` if intentional
- Line too long: Break into multiple lines
- SQL in routers: Move SQL to repository or SQL file (Rule 4)

**Custom Rules** (defined in `.ruff.toml`):
- Detect SQL keywords (SELECT, INSERT, UPDATE, DELETE) in router files
- Enforce max line length 120 chars
- Require docstrings on public functions

---

### Job 3: Type Check

**Purpose**: Catch type errors before runtime

**Command**:
```bash
mypy app/ --config-file pyproject.toml
```

**Pass Criteria**: No type errors, exit code 0

**Failure Triage**:
1. Run locally: `mypy app/`
2. Read error for file and line number
3. Add type annotations or fix incorrect type usage
4. Use `# type: ignore` only if unavoidable

**Common Failures**:
- Missing return type: Add `-> ReturnType` to function signature
- Incompatible types: Fix type mismatch in assignment
- Untyped function call: Add type hints to called function

---

### Job 4: Coverage

**Purpose**: Ensure test coverage stays above threshold

**Command**:
```bash
pytest tests/ --cov=app/vendor_catalog_app --cov-report=term --cov-fail-under=80
```

**Pass Criteria**: Coverage >= 80%, exit code 0

**Failure Triage**:
1. Run locally: `pytest tests/ --cov=app/vendor_catalog_app --cov-report=html`
2. Open `htmlcov/index.html` in browser
3. Identify uncovered lines (red highlighting)
4. Add tests for uncovered code paths
5. Re-run coverage to verify improvement

**Common Failures**:
- New feature added without tests: Add unit + integration tests
- Untestable code: Refactor to be testable (extract dependencies, use DI)
- Edge cases not covered: Add tests for error paths

**Coverage Exclusions**:
- `if __name__ == "__main__":` blocks
- Debug print statements
- Abstract methods (will be covered by subclass tests)

---

### Job 5: RBAC Coverage

**Purpose**: Ensure all mutation endpoints have permission checks (Rule 1)

**Command**:
```bash
pytest tests/test_rbac_coverage.py -v
```

**Pass Criteria**: No violations, exit code 0

**How It Works**:
1. Scans all router files in `app/vendor_catalog_app/web/routers/`
2. Finds all `@router.post`, `@router.put`, `@router.patch`, `@router.delete` decorators
3. Checks for `@require_permission` decorator or inline `if not user.can_apply_change(...)` check
4. Reports violations

**Failure Triage**:
1. Run locally: `pytest tests/test_rbac_coverage.py -v`
2. Read output for violating router and endpoint
3. Add `@require_permission(change_type)` decorator or inline check
4. Re-run to verify fix

**Example Violation**:
```
FAIL: Missing permission check on POST /vendor/{vendor_id}/contact
File: app/vendor_catalog_app/web/routers/contacts.py
Line: 45
```

**Fix**:
```python
@router.post("/vendor/{vendor_id}/contact")
@require_permission("vendor_contact_create")  # ADD THIS
async def create_vendor_contact(vendor_id: int, request: Request):
    # ... handler
```

---

### Job 7: Security Scan (Future)

**Purpose**: Detect known vulnerabilities in dependencies

**Command**:
```bash
pip-audit --desc
```

**Pass Criteria**: No high/critical vulnerabilities, exit code 0

**Failure Triage**:
1. Read vulnerability report for affected package and CVE
2. Update package to patched version: `pip install --upgrade package_name`
3. Update `requirements.txt`
4. Re-run security scan
5. If no patch available, add exception with justification

**Note**: Not yet implemented. Add in future PR.

---

### Job 6: Data Governance Guards

**Purpose**: Enforce Business Unit terminology and lookup-governed dropdown controls.

**Command**:
```bash
pytest tests/test_business_unit_governance_guards.py -v
```

**Pass Criteria**:
- No legacy `lob`/`Line of Business` references in runtime app code (except explicit rejection guard paths)
- Governed dropdown selects are rendered from lookup loops
- No free-form “add new business unit” control in governed vendor create flow

---

## Running CI Locally

### Full CI Simulation

Run all checks locally before pushing:

```bash
# 1. Run tests
pytest tests/ -v

# 2. Run linter
ruff check app/ tests/

# 3. Run type checker
mypy app/

# 4. Run coverage
pytest tests/ --cov=app/vendor_catalog_app --cov-fail-under=80

# 5. Run RBAC coverage
pytest tests/test_rbac_coverage.py -v
```

Or create a script `scripts/ci_local.sh`:

```bash
#!/bin/bash
set -e  # Exit on first failure

echo "Running tests..."
pytest tests/ -v

echo "Running linter..."
ruff check app/ tests/

echo "Running type checker..."
mypy app/

echo "Running coverage..."
pytest tests/ --cov=app/vendor_catalog_app --cov-fail-under=80

echo "Running RBAC coverage..."
pytest tests/test_rbac_coverage.py -v

echo "All CI checks passed!"
```

Run: `bash scripts/ci_local.sh`

---

### Quick Checks (Pre-Commit)

For fast feedback before committing:

```bash
# Format code
ruff check --fix app/ tests/

# Run only affected tests (if using pytest-picked)
pytest --picked -v

# Type check only changed files
mypy app/vendor_catalog_app/web/routers/contacts.py
```

---

## CI Configuration Files

### .github/workflows/ci.yml

Located at `.github/workflows/ci.yml`. See full contents in implementation artifacts section.

**Key settings**:
- `runs-on: ubuntu-latest`
- `python-version: '3.11'`
- `timeout-minutes: 10`

---

### pyproject.toml

Located at `pyproject.toml`. Configures pytest, mypy, coverage.

**Key settings**:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"
addopts = "--strict-markers --tb=short"

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.coverage.run]
source = ["app/vendor_catalog_app"]
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
fail_under = 80
```

---

### .ruff.toml

Located at `.ruff.toml`. Configures linter rules.

**Key settings**:
- Line length: 120
- Select rules: E (PEP8 errors), F (pyflakes), I (isort), N (naming)
- Custom rule: Detect SQL keywords in routers

---

## Handling CI Failures

### General Process

1. **Read failure message**: CI logs show exact error
2. **Reproduce locally**: Run failing check on your machine
3. **Fix root cause**: Don't mask with `# noqa` or `# type: ignore` unless necessary
4. **Verify fix**: Re-run check locally
5. **Push fix**: Commit and push, CI re-runs automatically

### When to Skip CI

**Never.** All CI checks must pass before merge. No exceptions.

If urgent hotfix needed:
1. Still must pass CI
2. Fast-track review, but CI still runs
3. If CI fails, fix and re-push

### False Positives

If CI check is incorrect:
1. Document in issue why check is wrong
2. Update CI config to fix check
3. Do not disable check globally to work around one case

---

## CI Metrics

Track over time:
- **Pass rate**: % of pushes that pass CI on first try (target >90%)
- **Mean time to green**: Time from push to CI pass (target <5 min)
- **Flaky test rate**: % of test failures that pass on re-run (target <2%)

Review quarterly and improve flaky tests or slow checks.

---

Last updated: 2026-02-15
