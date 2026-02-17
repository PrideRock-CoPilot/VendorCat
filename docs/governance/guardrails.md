# Guardrails: Non-Negotiable Rules

These are the 10 hard rules for VendorCatalog. Every PR must comply. No exceptions without Tech Lead approval and documentation.

## Rule 1: Every Mutation Endpoint Has Permission Check

**Rationale**: Prevent unauthorized data modification (DRIFT-001)

**Enforcement**: CI test `test_rbac_coverage.py` scans routers and fails if mutation endpoint lacks permission check

**Compliant Example**:
```python
@router.post("/vendor/{vendor_id}/contact")
@require_permission("vendor_contact_edit")
async def create_vendor_contact(vendor_id: int, request: Request):
    user = request.state.user
    if not user.can_apply_change("vendor_contact_edit"):
        raise HTTPException(403, "Insufficient permissions")
    # ... rest of handler
```

**Non-Compliant Example**:
```python
@router.post("/vendor/{vendor_id}/contact")  # MISSING PERMISSION CHECK
async def create_vendor_contact(vendor_id: int, request: Request):
    # ... handler without authorization
```

**Reference**: [RBAC & Permissions](../architecture/rbac-and-permissions.md)

---

## Rule 2: Every Schema Change Has Migration File

**Rationale**: Prevent schema drift and deployment failures (DRIFT-002)

**Enforcement**: Manual code review + future CI check for modified SQL without migration

**Compliant Example**:
```sql
-- File: setup/databricks/migration_007_add_contact_preferred_flag.sql
ALTER TABLE twvendor.core_vendor_contact 
ADD COLUMN is_preferred_contact BOOLEAN DEFAULT FALSE;

INSERT INTO twvendor.app_schema_version (version_number, description, applied_by)
VALUES (7, 'Add is_preferred_contact to core_vendor_contact', current_user());
```

**Non-Compliant Example**:
- Running DDL directly in SQL editor without creating migration file
- Modifying table structure without version tracking

**Reference**: [Migrations & Schema](../operations/migrations-and-schema.md)

---

## Rule 3: Every Mutation Writes Audit Record

**Rationale**: Compliance, debugging, security investigation (DRIFT-003)

**Enforcement**: Code review checks for `_write_audit_entity_change(...)` call

**Compliant Example**:
```python
def update_vendor_status(self, vendor_id: int, new_status: str, actor: str):
    old_vendor = self.get_vendor_by_id(vendor_id)
    self._execute_write(
        "UPDATE twvendor.core_vendor SET status = ? WHERE vendor_id = ?",
        (new_status, vendor_id)
    )
    new_vendor = self.get_vendor_by_id(vendor_id)
    self._write_audit_entity_change(
        entity_type="vendor",
        entity_id=vendor_id,
        change_type="status_change",
        before_snapshot=old_vendor,
        after_snapshot=new_vendor,
        actor=actor,
        request_id=get_correlation_id()
    )
```

**Non-Compliant Example**:
```python
def update_vendor_status(self, vendor_id: int, new_status: str):
    self._execute_write(
        "UPDATE twvendor.core_vendor SET status = ? WHERE vendor_id = ?",
        (new_status, vendor_id)
    )
    # MISSING AUDIT CALL
```

**Reference**: [Observability & Audit](../operations/observability-and-audit.md)

---

## Rule 4: No Raw SQL in Routers

**Rationale**: Maintain repository pattern, improve testability (DRIFT-007)

**Enforcement**: CI lint detects SQL keywords in router files (ruff custom rule)

**Compliant Example**:
```python
# In router
@router.get("/vendor/{vendor_id}/contacts")
async def get_vendor_contacts(vendor_id: int, repo=Depends(get_repository)):
    contacts = repo.get_vendor_contacts(vendor_id)  # delegates to repository
    return contacts

# In repository
def get_vendor_contacts(self, vendor_id: int):
    return self._execute_read_sql_file(
        "get_vendor_contacts.sql",
        {"vendor_id": vendor_id}
    )
```

**Non-Compliant Example**:
```python
# In router
@router.get("/vendor/{vendor_id}/contacts")
async def get_vendor_contacts(vendor_id: int, db=Depends(get_db_connection)):
    cursor = db.cursor()
    cursor.execute(f"SELECT * FROM twvendor.core_vendor_contact WHERE vendor_id = {vendor_id}")  # SQL IN ROUTER
    return cursor.fetchall()
```

**Reference**: [Architecture Docs](../architecture/07-application-architecture.md)

---

## Rule 5: All User Input Validated Before Storage

**Rationale**: Data quality, security, prevent injection (DRIFT-004)

**Enforcement**: Code review checks for validation on form.get() calls

**Compliant Example**:
```python
from pydantic import BaseModel, validator, HttpUrl

class VendorContactForm(BaseModel):
    name: str
    email: str
    phone: str | None = None
    website: HttpUrl | None = None
    
    @validator('name')
    def name_length(cls, v):
        if not v or len(v) > 200:
            raise ValueError("Name required, max 200 chars")
        return v
    
    @validator('email')
    def email_format(cls, v):
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', v):
            raise ValueError("Invalid email format")
        return v

@router.post("/vendor/{vendor_id}/contact")
async def create_contact(vendor_id: int, form_data: VendorContactForm):
    # form_data already validated by Pydantic
    repo.create_vendor_contact(vendor_id, form_data.dict())
```

**Non-Compliant Example**:
```python
@router.post("/vendor/{vendor_id}/contact")
async def create_contact(vendor_id: int, request: Request):
    form = await request.form()
    name = form.get("name")  # NO VALIDATION
    email = form.get("email")  # NO VALIDATION
    repo.create_vendor_contact(vendor_id, name, email)
```

**Reference**: [Security Checklist](../operations/security-checklist.md)

---

## Rule 6: Foreign Keys Validated Before Insert

**Rationale**: Prevent orphaned records, data integrity (DRIFT-005)

**Enforcement**: Code review + data quality checks

**Compliant Example**:
```python
def create_vendor_contact(self, vendor_id: int, contact_data: dict):
    # Validate FK exists
    vendor = self.get_vendor_by_id(vendor_id)
    if not vendor:
        raise ValueError(f"Vendor {vendor_id} does not exist")
    
    # Now safe to insert
    self._execute_write(
        "INSERT INTO twvendor.core_vendor_contact (vendor_id, name, email) VALUES (?, ?, ?)",
        (vendor_id, contact_data['name'], contact_data['email'])
    )
```

**Non-Compliant Example**:
```python
def create_vendor_contact(self, vendor_id: int, contact_data: dict):
    # NO FK VALIDATION - may insert orphaned record
    self._execute_write(
        "INSERT INTO twvendor.core_vendor_contact (vendor_id, name, email) VALUES (?, ?, ?)",
        (vendor_id, contact_data['name'], contact_data['email'])
    )
```

**Reference**: [Data Ownership & Survivorship](../architecture/data-ownership-and-survivorship.md)

---

## Rule 7: No |safe Filter Without Sanitization

**Rationale**: Prevent XSS attacks (DRIFT-008)

**Enforcement**: Manual code review of templates

**Compliant Example**:
```python
# At write time
import bleach

def save_vendor_notes(vendor_id: int, notes_html: str):
    sanitized = bleach.clean(
        notes_html,
        tags=['p', 'b', 'i', 'u', 'br', 'ul', 'ol', 'li'],
        strip=True
    )
    repo.update_vendor_notes(vendor_id, sanitized)

# In template
<div class="vendor-notes">
    {{ vendor.notes | safe }}  {# Safe because sanitized at write time #}
</div>
```

**Non-Compliant Example**:
```python
# In template
<div class="vendor-notes">
    {{ vendor.notes | safe }}  {# UNSAFE: user input not sanitized #}
</div>
```

**Reference**: [Security Checklist](../operations/security-checklist.md)

---

## Rule 8: Every Feature Has Tests

**Rationale**: Prevent regressions, maintain coverage (DRIFT-010)

**Enforcement**: CI fails if coverage <80%, Definition of Done requires tests

**Compliant Example**:
```python
# Feature: app/vendor_catalog_app/backend/vendor_service.py
def deactivate_vendor(self, vendor_id: int):
    # implementation

# Test: tests/test_vendor_service.py
def test_deactivate_vendor_success():
    service = VendorService()
    result = service.deactivate_vendor(vendor_id=123)
    assert result.status == "inactive"

def test_deactivate_vendor_not_found():
    service = VendorService()
    with pytest.raises(ValueError):
        service.deactivate_vendor(vendor_id=999999)
```

**Non-Compliant Example**:
- Adding feature without corresponding test file
- PR that reduces coverage below 80%

**Reference**: [Definition of Done](definition-of-done.md)

---

## Rule 9: App-Owned Fields Protected from Ingestion Overwrite

**Rationale**: Prevent user edits from being lost (DRIFT-006)

**Enforcement**: Code review of ingestion merge logic

**Compliant Example**:
```python
# In ingestion merge logic
def merge_vendor_from_peoplesoft(ps_vendor: dict, existing_vendor: dict):
    merged = existing_vendor.copy()
    
    # Ingestion-owned fields: always overwrite
    merged['erp_vendor_id'] = ps_vendor['vendor_id']
    merged['legal_name'] = ps_vendor['legal_name']
    
    # App-owned fields: preserve if user_override set
    if not existing_vendor.get('user_override_payment_terms'):
        merged['payment_terms'] = ps_vendor['payment_terms']
    
    return merged
```

**Non-Compliant Example**:
```python
# In ingestion
def merge_vendor_from_peoplesoft(ps_vendor: dict):
    # Overwrites ALL fields, including user edits
    return ps_vendor
```

**Reference**: [Data Ownership & Survivorship](../architecture/data-ownership-and-survivorship.md)

---

## Rule 10: Security Vulnerabilities Fixed Within 7 Days

**Rationale**: Minimize attack surface, compliance (DRIFT SLO)

**Enforcement**: Dependabot alerts + Security Lead review

**Compliant Example**:
- Dependabot alert received Monday
- PR created to update dependency by Wednesday
- Tested and merged by Friday
- Deployed to production by next Monday

**Non-Compliant Example**:
- Dependabot alert sits unaddressed for 2 weeks

**Reference**: [Security Checklist](../operations/security-checklist.md)

---

## Enforcement Summary

| Rule | Enforcement Method | Blocker |
|------|-------------------|---------|
| 1. Permission checks | CI test (test_rbac_coverage.py) | Yes |
| 2. Migration files | Manual code review | Yes |
| 3. Audit records | Manual code review | No |
| 4. No SQL in routers | CI lint (ruff) | Yes |
| 5. Input validation | Manual code review | No |
| 6. FK validation | Manual code review | No |
| 7. No unsafe |safe | Manual code review | No |
| 8. Tests required | CI coverage check (80%) | Yes |
| 9. App-owned field protection | Manual code review | No |
| 10. Vulnerability remediation | Security Lead tracking | No |

**Note**: "No" blockers should be added as CI checks in future PRs to increase automation.

## Exception Process

To violate a guardrail:

1. Create issue explaining why exception needed
2. Get Tech Lead approval in writing (GitHub comment)
3. Document exception in ADR: `docs/architecture/decisions/NNNN-exception-guardrail-X.md`
4. Add technical debt issue to remediate
5. Set expiration date for exception

Without this process, PR will be rejected.

---

Last updated: 2026-02-15
