# RBAC and Permissions

Role-Based Access Control (RBAC) for VendorCatalog. This document defines roles, permissions, org-scoping, and enforcement patterns.

## Permission Model Overview

VendorCatalog uses a **role-based** model where:
1. Users are assigned **roles** (e.g., `vendor_admin`, `vendor_viewer`)
2. Roles grant **change types** (e.g., `vendor_edit`, `vendor_delete`)
3. Code checks `user.can_apply_change(change_type)` before mutations
4. Org-scoping restricts users to their organization's vendors

## Roles

### 1. system_admin

**Description**: Full system access, manages all vendors and users

**Permissions (change types)**:
- `vendor_create`, `vendor_edit`, `vendor_delete`
- `vendor_contact_create`, `vendor_contact_edit`, `vendor_contact_delete`
- `vendor_address_create`, `vendor_address_edit`, `vendor_address_delete`
- `user_create`, `user_edit`, `user_delete`, `role_assign`
- `config_edit`, `audit_view`

**Org scope**: None (all organizations)

**Typical users**: IT admins, system owners

---

### 2. vendor_admin

**Description**: Manages vendors for their organization

**Permissions**:
- `vendor_create`, `vendor_edit`, `vendor_delete`
- `vendor_contact_create`, `vendor_contact_edit`, `vendor_contact_delete`
- `vendor_address_create`, `vendor_address_edit`, `vendor_address_delete`
- `vendor_tag_create`, `vendor_tag_edit`
- `audit_view` (own org only)

**Org scope**: Single organization (e.g., "Finance")

**Typical users**: Procurement managers, department leads

---

### 3. vendor_approver

**Description**: Approves vendor changes (workflow approval)

**Permissions**:
- `vendor_approve`, `vendor_reject`
- `vendor_view`, `vendor_contact_view`, `vendor_address_view`
- `audit_view`

**Org scope**: Single organization

**Typical users**: Finance approvers, compliance officers

**Note**: Approval workflow not yet implemented. Placeholder role.

---

### 4. vendor_steward

**Description**: Data quality role, can edit vendor metadata but not financial terms

**Permissions**:
- `vendor_edit` (limited to specific fields: dba_name, notes, website_url, tags)
- `vendor_contact_edit`, `vendor_address_edit`
- `vendor_tag_create`, `vendor_tag_edit`

**Org scope**: Single organization

**Typical users**: Data quality analysts, vendor coordinators

---

### 5. vendor_editor

**Description**: Can create and edit vendors, but not delete

**Permissions**:
- `vendor_create`, `vendor_edit`
- `vendor_contact_create`, `vendor_contact_edit`
- `vendor_address_create`, `vendor_address_edit`
- `vendor_tag_create`

**Org scope**: Single organization

**Typical users**: Procurement specialists, vendor coordinators

---

### 6. vendor_viewer

**Description**: Read-only access to vendors

**Permissions**:
- `vendor_view`, `vendor_contact_view`, `vendor_address_view`
- `vendor_search`, `vendor_export`

**Org scope**: Single organization

**Typical users**: Finance analysts, auditors, read-only stakeholders

---

### 7. vendor_auditor

**Description**: Read-only access plus audit trail access

**Permissions**:
- `vendor_view`, `vendor_contact_view`, `vendor_address_view`
- `audit_view`, `audit_export`

**Org scope**: Single organization (or all orgs for compliance auditor)

**Typical users**: Internal audit, compliance team

---

## Approval Workflow Levels

**Not yet implemented.** Placeholder for future approval workflow.

When implemented:
- **Level 1**: Auto-approve (vendor_editor can create/edit without approval)
- **Level 2**: Single approver (vendor_approver must approve)
- **Level 3**: Dual approval (two vendor_approvers must approve)

Approval required for:
- New vendor creation (Level 2)
- Vendor deletion (Level 3)
- Payment terms change (Level 2)
- Legal name change (Level 2)

## Org-Scoping Mechanism

### Database Schema

Users have `organization_id` FK to `core_organization` table.

```sql
CREATE TABLE core_user (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    email TEXT,
    organization_id INTEGER,  -- FK to core_organization
    role TEXT,  -- e.g., 'vendor_admin'
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE core_organization (
    organization_id INTEGER PRIMARY KEY,
    name TEXT,  -- e.g., 'Finance', 'Procurement'
    parent_organization_id INTEGER  -- for hierarchical orgs
);
```

### Enforcement

All queries for vendor data must filter by `organization_id`:

```python
# Repository method
def get_vendors_for_user(self, user: User):
    if user.role == 'system_admin':
        # No org filter for system_admin
        return self._execute_read("SELECT * FROM twvendor.core_vendor")
    else:
        # Filter by user's org
        return self._execute_read(
            "SELECT * FROM twvendor.core_vendor WHERE organization_id = ?",
            (user.organization_id,)
        )
```

**Critical**: Every SELECT/UPDATE/DELETE on vendor tables must include org filter (except system_admin).

## Permission Enforcement Patterns

### Pattern 1: Decorator (Recommended)

Use `@require_permission` decorator on router endpoints:

```python
from app.vendor_catalog_app.web.security.rbac import require_permission

@router.post("/vendor")
@require_permission("vendor_create")
async def create_vendor(request: Request, vendor_data: dict):
    user = request.state.user
    # Permission already checked by decorator
    vendor = repo.create_vendor(vendor_data, user.organization_id)
    return vendor
```

**Benefits**:
- Declarative, easy to audit
- Prevents bypassing permission check
- Detectable by static analysis (test_rbac_coverage.py)

---

### Pattern 2: Inline Check

For complex logic or conditional permissions:

```python
@router.put("/vendor/{vendor_id}")
async def update_vendor(vendor_id: int, request: Request, form_data: dict):
    user = request.state.user
    vendor = repo.get_vendor_by_id(vendor_id)
    
    # Check org scope
    if vendor.organization_id != user.organization_id and user.role != 'system_admin':
        raise HTTPException(403, "Vendor belongs to different organization")
    
    # Check permission
    if 'payment_terms' in form_data:
        if not user.can_apply_change("vendor_edit_financial"):
            raise HTTPException(403, "Cannot edit financial terms")
    
    if not user.can_apply_change("vendor_edit"):
        raise HTTPException(403, "Insufficient permissions")
    
    repo.update_vendor(vendor_id, form_data)
```

**Use when**: Permission depends on request data or vendor state.

---

### Pattern 3: Repository-Level Check

For defense in depth, add permission check in repository:

```python
# In repository
def delete_vendor(self, vendor_id: int, user: User):
    if not user.can_apply_change("vendor_delete"):
        raise PermissionError("User cannot delete vendors")
    
    vendor = self.get_vendor_by_id(vendor_id)
    if vendor.organization_id != user.organization_id and user.role != 'system_admin':
        raise PermissionError("Vendor belongs to different organization")
    
    self._execute_write("DELETE FROM twvendor.core_vendor WHERE vendor_id = ?", (vendor_id,))
```

**Benefits**: Prevents accidental bypass if router check missing.

**Drawback**: Harder to test, couples repository to auth logic.

**Recommendation**: Use Pattern 1 (decorator) at router + audit trail in repository.

---

## User Context

### UserContext Object

```python
from dataclasses import dataclass

@dataclass
class UserContext:
    user_id: int
    username: str
    email: str
    role: str
    organization_id: int | None
    change_types: list[str]  # Permitted change types
    
    def can_apply_change(self, change_type: str) -> bool:
        return change_type in self.change_types or self.role == 'system_admin'
    
    def is_org_scoped(self) -> bool:
        return self.organization_id is not None
```

### Middleware (Request State)

Attach user to every request:

```python
# In main.py or middleware
@app.middleware("http")
async def add_user_context(request: Request, call_next):
    # Extract user from session/JWT/Databricks auth
    user = get_authenticated_user(request)
    request.state.user = user
    response = await call_next(request)
    return response
```

### Accessing User in Router

```python
@router.post("/vendor")
async def create_vendor(request: Request):
    user = request.state.user  # UserContext object
    if not user.can_apply_change("vendor_create"):
        raise HTTPException(403, "Insufficient permissions")
    # ... rest of handler
```

## Role Assignment

### Bootstrap Admin

On first run, create system_admin user:

```python
# In setup/databricks/validate_schema_and_bootstrap_admin.py
def bootstrap_admin():
    admin_exists = repo.get_user_by_username("admin")
    if not admin_exists:
        repo.create_user(
            username="admin",
            email="admin@example.com",
            role="system_admin",
            organization_id=None  # No org scope
        )
```

### Role Management UI

System admins can assign roles via `/admin/users` page:
- List all users
- Edit user role (dropdown with 7 roles)
- Assign organization (dropdown)
- Revoke access (set is_active = FALSE)

## Common RBAC Mistakes

### Mistake 1: Forgetting Org Scope Filter

```python
# BAD: Returns vendors from all orgs
def get_vendors(self):
    return self._execute_read("SELECT * FROM twvendor.core_vendor")

# GOOD: Filters by user's org
def get_vendors(self, user: UserContext):
    if user.role == 'system_admin':
        return self._execute_read("SELECT * FROM twvendor.core_vendor")
    else:
        return self._execute_read(
            "SELECT * FROM twvendor.core_vendor WHERE organization_id = ?",
            (user.organization_id,)
        )
```

---

### Mistake 2: Checking Permission After Action

```python
# BAD: Deletes first, checks permission after
def delete_vendor(self, vendor_id: int, user: UserContext):
    self._execute_write("DELETE FROM twvendor.core_vendor WHERE vendor_id = ?", (vendor_id,))
    if not user.can_apply_change("vendor_delete"):  # TOO LATE
        raise PermissionError("Cannot delete vendor")

# GOOD: Checks permission first
def delete_vendor(self, vendor_id: int, user: UserContext):
    if not user.can_apply_change("vendor_delete"):
        raise PermissionError("Cannot delete vendor")
    self._execute_write("DELETE FROM twvendor.core_vendor WHERE vendor_id = ?", (vendor_id,))
```

---

### Mistake 3: Hardcoding Roles Instead of Change Types

```python
# BAD: Hardcodes role check
if user.role != "vendor_admin":
    raise HTTPException(403)

# GOOD: Checks change type (role-agnostic)
if not user.can_apply_change("vendor_edit"):
    raise HTTPException(403)
```

**Why**: Change types are more flexible. Multiple roles can have same change type. Easier to refactor roles.

---

### Mistake 4: Missing Permission Check on Mutation

```python
# BAD: No permission check
@router.delete("/vendor/{vendor_id}")
async def delete_vendor(vendor_id: int):
    repo.delete_vendor(vendor_id)

# GOOD: Permission check present
@router.delete("/vendor/{vendor_id}")
@require_permission("vendor_delete")
async def delete_vendor(vendor_id: int, request: Request):
    user = request.state.user
    repo.delete_vendor(vendor_id, user)
```

---

### Mistake 5: Exposing PII to Unauthorized Users

```python
# BAD: Viewer can see sensitive fields
@router.get("/vendor/{vendor_id}")
async def get_vendor(vendor_id: int):
    vendor = repo.get_vendor_by_id(vendor_id)
    return vendor  # Includes payment_terms, tax_id

# GOOD: Filter fields based on role
@router.get("/vendor/{vendor_id}")
async def get_vendor(vendor_id: int, request: Request):
    user = request.state.user
    vendor = repo.get_vendor_by_id(vendor_id)
    
    if not user.can_apply_change("vendor_view_financial"):
        # Redact financial fields for non-privileged users
        vendor.pop('payment_terms', None)
        vendor.pop('tax_id', None)
    
    return vendor
```

---

## Role-to-ChangeType Mapping

Defined in code (`app/vendor_catalog_app/core/permissions.py`):

```python
ROLE_PERMISSIONS = {
    'system_admin': ['*'],  # All permissions
    'vendor_admin': [
        'vendor_create', 'vendor_edit', 'vendor_delete',
        'vendor_contact_create', 'vendor_contact_edit', 'vendor_contact_delete',
        'vendor_address_create', 'vendor_address_edit', 'vendor_address_delete',
        'vendor_tag_create', 'vendor_tag_edit',
        'audit_view'
    ],
    'vendor_approver': [
        'vendor_approve', 'vendor_reject',
        'vendor_view', 'vendor_contact_view', 'vendor_address_view',
        'audit_view'
    ],
    'vendor_steward': [
        'vendor_edit_metadata',  # Limited edit
        'vendor_contact_edit', 'vendor_address_edit',
        'vendor_tag_create', 'vendor_tag_edit',
        'vendor_view', 'vendor_contact_view', 'vendor_address_view'
    ],
    'vendor_editor': [
        'vendor_create', 'vendor_edit',
        'vendor_contact_create', 'vendor_contact_edit',
        'vendor_address_create', 'vendor_address_edit',
        'vendor_tag_create',
        'vendor_view', 'vendor_contact_view', 'vendor_address_view'
    ],
    'vendor_viewer': [
        'vendor_view', 'vendor_contact_view', 'vendor_address_view',
        'vendor_search', 'vendor_export'
    ],
    'vendor_auditor': [
        'vendor_view', 'vendor_contact_view', 'vendor_address_view',
        'audit_view', 'audit_export'
    ]
}
```

## Testing RBAC

### Test Coverage

Every mutation endpoint must have:
1. **Happy path test**: Authorized user can perform action
2. **Unauthorized test**: User without permission gets 403
3. **Org scope test**: User from different org cannot access vendor

Example:

```python
def test_create_vendor_as_vendor_admin():
    user = create_test_user(role='vendor_admin', org_id=1)
    response = client.post('/vendor', json={'name': 'Acme'}, headers=auth_header(user))
    assert response.status_code == 200

def test_create_vendor_as_viewer_forbidden():
    user = create_test_user(role='vendor_viewer', org_id=1)
    response = client.post('/vendor', json={'name': 'Acme'}, headers=auth_header(user))
    assert response.status_code == 403

def test_view_vendor_from_different_org_forbidden():
    user = create_test_user(role='vendor_admin', org_id=2)
    vendor = create_test_vendor(org_id=1)
    response = client.get(f'/vendor/{vendor.id}', headers=auth_header(user))
    assert response.status_code == 403
```

### RBAC Coverage Enforcement

CI test `test_rbac_coverage.py` scans all routers and verifies:
- All `@router.post/put/patch/delete` have `@require_permission` or inline permission check
- Generates report of violations
- Fails CI if violations found

---

Last updated: 2026-02-15
