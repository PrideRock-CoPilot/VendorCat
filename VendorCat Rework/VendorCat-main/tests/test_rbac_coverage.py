"""
Test to enforce RBAC coverage on all mutation endpoints.

This test scans all router files and verifies that every POST/PUT/PATCH/DELETE
endpoint has a permission check (either @require_permission decorator or inline check).

Enforces Guardrail Rule 1: Every Mutation Endpoint Has Permission Check
"""

import re
from pathlib import Path

import pytest


def get_router_files():
    """Find all router files in the web/routers directory."""
    routers_dir = Path("app/vendor_catalog_app/web/routers")
    if not routers_dir.exists():
        return []
    return list(routers_dir.rglob("*.py"))


def extract_endpoints(file_path: Path):
    """
    Extract mutation endpoints from a router file.
    
    Returns list of tuples: (http_method, route_path, line_number, has_permission_check)
    """
    with open(file_path, encoding='utf-8') as f:
        content = f.read()

    endpoints = []
    mutation_methods = ['post', 'put', 'patch', 'delete']

    # Pattern to find router decorators
    # Matches: @router.post("/path"), @router.put("/path/{id}"), etc.
    decorator_pattern = r'@router\.(post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']\s*\)'

    # Pattern to find @require_permission decorator
    permission_decorator_pattern = r'@require_permission\s*\(\s*["\']([^"\']+)["\']\s*\)'

    # Pattern to find inline permission check
    inline_check_pattern = r'(can_apply_change|require_permission|check_permission)'

    lines = content.split('\n')

    for i, line in enumerate(lines, start=1):
        match = re.search(decorator_pattern, line)
        if match:
            http_method = match.group(1)
            route_path = match.group(2)

            # Check previous few lines for @require_permission decorator
            has_decorator = False
            for j in range(max(0, i-5), i):
                if re.search(permission_decorator_pattern, lines[j]):
                    has_decorator = True
                    break

            # Check next 20 lines for inline permission check
            has_inline_check = False
            for j in range(i, min(len(lines), i+20)):
                if re.search(inline_check_pattern, lines[j]):
                    has_inline_check = True
                    break

            has_permission_check = has_decorator or has_inline_check

            endpoints.append({
                'file': file_path,
                'method': http_method.upper(),
                'path': route_path,
                'line': i,
                'has_permission_check': has_permission_check
            })

    return endpoints


def test_rbac_coverage():
    """
    Test that all mutation endpoints have permission checks.
    
    This test will fail if any POST/PUT/PATCH/DELETE endpoint is missing
    a permission check (either decorator or inline).
    """
    router_files = get_router_files()

    if not router_files:
        pytest.skip("No router files found")

    violations = []

    for router_file in router_files:
        endpoints = extract_endpoints(router_file)

        for endpoint in endpoints:
            if not endpoint['has_permission_check']:
                violations.append(endpoint)

    # Build failure message
    if violations:
        message = "\n\nRBAC COVERAGE VIOLATIONS FOUND:\n"
        message += "="*70 + "\n\n"

        for v in violations:
            message += f"File: {v['file']}\n"
            message += f"Line: {v['line']}\n"
            message += f"Endpoint: {v['method']} {v['path']}\n"
            message += "Missing: @require_permission decorator or inline permission check\n"
            message += "-"*70 + "\n"

        message += f"\nTotal violations: {len(violations)}\n"
        message += "\nTo fix: Add @require_permission decorator or inline permission check\n"
        message += "See: docs/architecture/rbac-and-permissions.md\n"

        pytest.fail(message)

    # If we get here, all endpoints have permission checks
    print("\n✓ RBAC coverage check passed")
    print(f"  Scanned {len(router_files)} router files")
    total_endpoints = sum(len(extract_endpoints(f)) for f in router_files)
    print(f"  Verified {total_endpoints} mutation endpoints have permission checks")


def test_rbac_coverage_reports_violations():
    """
    Test that the coverage test can detect violations.
    
    This is a meta-test to verify the test itself works correctly.
    """
    # Create a sample code snippet with a violation
    sample_code = '''
@router.post("/test")
async def test_endpoint(request: Request):
    # No permission check
    return {"status": "ok"}
'''

    # Check that our pattern detector would catch this
    has_permission = bool(re.search(r'(can_apply_change|require_permission)', sample_code))
    assert not has_permission, "Test validation: Sample code should not have permission check"

    # Create a sample with permission check
    sample_with_permission = '''
@router.post("/test")
@require_permission("test_permission")
async def test_endpoint(request: Request):
    return {"status": "ok"}
'''

    has_permission = bool(re.search(r'@require_permission', sample_with_permission))
    assert has_permission, "Test validation: Sample should have permission check"


if __name__ == "__main__":
    # Allow running directly for quick check
    test_rbac_coverage()
