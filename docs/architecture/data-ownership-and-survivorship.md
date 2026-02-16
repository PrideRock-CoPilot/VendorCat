# Data Ownership and Survivorship

This document defines which system owns which entity fields and how conflicts are resolved when multiple systems modify the same data.

## Problem Statement

VendorCatalog ingests vendor data from external systems (PeopleSoft, Zycus) while users manually edit vendors in the app. When batch ingestion runs, it may overwrite user edits, or user edits may conflict with authoritative source data.

We need clear rules for:
1. **Field ownership**: Which system is the source of truth for each field
2. **Survivorship**: When conflicts occur, which value wins
3. **Override mechanism**: How users can override ingestion values when needed

## Source Systems

| Source | Type | Frequency | Entities |
|--------|------|-----------|----------|
| PeopleSoft | ERP, batch ingest | Daily | Vendors, Contacts, Addresses |
| Zycus | Procurement, batch ingest | Weekly | Vendor certifications, compliance |
| VendorCatalog App | UI, real-time | On-demand | All entities (user edits) |
| Manual CSV Import | Batch, ad-hoc | As needed | Any entity |

## Field Ownership Matrix

### core_vendor Table

| Field | Owner | Rationale | Override Allowed? |
|-------|-------|-----------|-------------------|
| vendor_id | App | App-generated PK | No |
| erp_vendor_id | PeopleSoft | ERP is source of truth for vendor ID mapping | No |
| legal_name | PeopleSoft | Legal entity name from ERP | Yes (user_override_legal_name) |
| dba_name | App | Users manage DBA name | N/A (app-owned) |
| vendor_status | PeopleSoft | ERP controls active/inactive | Yes (user_override_status) |
| payment_terms | PeopleSoft | Financial terms from ERP | Yes (user_override_payment_terms) |
| primary_contact_id | App | Users select primary contact | N/A |
| vendor_type | App | User classification | N/A |
| notes | App | User-entered notes | N/A |
| website_url | App | User-entered URL | N/A |
| is_minority_owned | Zycus | Diversity data from Zycus | Yes (user_override_diversity) |
| is_woman_owned | Zycus | Diversity data from Zycus | Yes (user_override_diversity) |
| is_veteran_owned | Zycus | Diversity data from Zycus | Yes (user_override_diversity) |
| created_at | App | Audit timestamp | No |
| updated_at | App | Audit timestamp | No |

### core_vendor_contact Table

| Field | Owner | Rationale | Override Allowed? |
|-------|-------|-----------|-------------------|
| contact_id | App | App-generated PK | No |
| vendor_id | App/PeopleSoft | FK to vendor (both systems can create) | No |
| name | PeopleSoft | Contact name from ERP | Yes (user_override_name) |
| email | PeopleSoft | Email from ERP | Yes (user_override_email) |
| phone | PeopleSoft | Phone from ERP | Yes (user_override_phone) |
| title | App | User-entered title | N/A |
| is_primary | App | User-selected primary contact | N/A |
| is_preferred_contact | App | User-selected preference | N/A |
| notes | App | User notes | N/A |

### core_vendor_address Table

| Field | Owner | Rationale | Override Allowed? |
|-------|-------|-----------|-------------------|
| address_id | App | App-generated PK | No |
| vendor_id | App/PeopleSoft | FK to vendor | No |
| address_line1 | PeopleSoft | Address from ERP | Yes (user_override_address) |
| address_line2 | PeopleSoft | Address from ERP | Yes (user_override_address) |
| city | PeopleSoft | City from ERP | Yes (user_override_address) |
| state | PeopleSoft | State from ERP | Yes (user_override_address) |
| postal_code | PeopleSoft | Zip from ERP | Yes (user_override_address) |
| country | PeopleSoft | Country from ERP | Yes (user_override_address) |
| address_type | App | User classification (billing, shipping) | N/A |
| is_primary | App | User-selected primary address | N/A |

### Diversity & Compliance Tables

| Table | Owner | Rationale |
|-------|-------|-----------|
| diversity_certification | Zycus | Zycus is source for certifications | 
| compliance_document | Zycus | Zycus manages compliance docs |
| vendor_rating | App | Users enter ratings |
| vendor_tag | App | Users manage tags |

## Survivorship Strategy

### Priority 1: User Override Flag

If a user explicitly overrides an ingestion-owned field, the override persists until user clears it.

**Implementation**:
```python
# In ingestion merge logic
def merge_vendor_from_peoplesoft(ps_vendor: dict, existing_vendor: dict):
    merged = existing_vendor.copy()
    
    # Always overwrite ingestion-owned fields WITHOUT override flag
    merged['erp_vendor_id'] = ps_vendor['vendor_id']
    
    # Conditional overwrite: only if user hasn't overridden
    if not existing_vendor.get('user_override_legal_name'):
        merged['legal_name'] = ps_vendor['legal_name']
    
    if not existing_vendor.get('user_override_payment_terms'):
        merged['payment_terms'] = ps_vendor['payment_terms']
    
    # Never overwrite app-owned fields
    # (notes, website_url, primary_contact_id stay from existing_vendor)
    
    return merged
```

### Priority 2: Source Hierarchy

When multiple ingestion sources provide the same field:

1. **App (user edit)** > PeopleSoft > Zycus > CSV Import
2. Exception: If app value is NULL and ingestion has value, ingestion wins

**Example**: 
- PeopleSoft says vendor is "Active"
- Zycus says vendor is "Inactive"
- **PeopleSoft wins** (higher priority)

### Priority 3: Timestamp (Last Write Wins)

If sources have equal priority, most recent update wins.

**Implementation**: Track `last_updated_by_source` and `last_updated_at` per field.

## Override Mechanism

### User Override Workflow

1. **User edits field** in VendorCatalog app (e.g., changes legal_name)
2. **Repository sets override flag**: `user_override_legal_name = TRUE`
3. **Audit log records override**: `change_type = "user_override"`, includes original value
4. **Ingestion respects override**: Next PeopleSoft batch skips legal_name for this vendor
5. **User can clear override**: Checkbox "Use value from PeopleSoft" sets flag to FALSE

### UI Indication

Fields under user override should show visual indicator:
- Icon: 🔒 "User override active - ingestion will not update this field"
- Tooltip: "This value was manually set and will not be overwritten by PeopleSoft. Click to revert to ERP value."

### Schema Addition

Add override flag columns to `core_vendor`:

```sql
ALTER TABLE twvendor.core_vendor ADD COLUMN user_override_legal_name BOOLEAN DEFAULT FALSE;
ALTER TABLE twvendor.core_vendor ADD COLUMN user_override_payment_terms BOOLEAN DEFAULT FALSE;
ALTER TABLE twvendor.core_vendor ADD COLUMN user_override_status BOOLEAN DEFAULT FALSE;
ALTER TABLE twvendor.core_vendor ADD COLUMN user_override_diversity BOOLEAN DEFAULT FALSE;
```

## Conflict Detection

### Pre-Merge Conflict Check

Before merging ingestion data, check for conflicts:

```python
def detect_conflicts(ps_vendor: dict, existing_vendor: dict):
    conflicts = []
    
    if ps_vendor['legal_name'] != existing_vendor['legal_name']:
        if not existing_vendor.get('user_override_legal_name'):
            conflicts.append({
                'field': 'legal_name',
                'current': existing_vendor['legal_name'],
                'incoming': ps_vendor['legal_name'],
                'resolution': 'auto_merge_ingestion_wins'
            })
        else:
            conflicts.append({
                'field': 'legal_name',
                'current': existing_vendor['legal_name'],
                'incoming': ps_vendor['legal_name'],
                'resolution': 'skip_user_override_active'
            })
    
    return conflicts
```

### Conflict Reporting

Generate daily conflict report:
- Fields updated by ingestion that had user override (flagged for review)
- Fields with high change frequency (potential data quality issue)
- Vendors with >5 overrides (possible ingestion mapping error)

## Idempotency

Ingestion must be idempotent: running the same batch twice produces same result.

**Pattern**:
```python
def upsert_vendor_from_peoplesoft(ps_vendor: dict):
    existing = repo.get_vendor_by_erp_id(ps_vendor['vendor_id'])
    
    if existing:
        merged = merge_vendor_from_peoplesoft(ps_vendor, existing)
        repo.update_vendor(existing['vendor_id'], merged)
    else:
        repo.create_vendor_from_ingestion(ps_vendor)
```

**Key**: Use natural key (erp_vendor_id) to determine create vs update.

## Edge Cases

### Case 1: User Edits Field Before First Ingestion

- User creates vendor manually, sets legal_name = "Acme Corp"
- PeopleSoft ingestion arrives with legal_name = "Acme Corporation"
- **Resolution**: Set override flag on manual create, ingestion skips field

### Case 2: ERP Value Reverts to Match User Override

- User overrides payment_terms = "Net 60"
- PeopleSoft later updates to "Net 60" (matching user value)
- **Resolution**: Keep override flag set until user explicitly clears it

### Case 3: Ingestion Source Deprecated

- Zycus feed discontinued, app becomes source of truth for diversity fields
- **Resolution**: Update ownership matrix, remove override flags, mark fields as app-owned

### Case 4: Bulk Re-Ingest After Data Fix

- PeopleSoft data corrected, need to re-ingest all vendors
- Some vendors have user overrides
- **Resolution**: Provide "force merge" flag in ingestion script, generates conflict report for manual review

## Testing

### Test Scenarios

1. **test_ingestion_respects_override**: User override prevents ingestion merge
2. **test_ingestion_without_override**: Ingestion updates field normally
3. **test_app_owned_never_overwritten**: Ingestion never touches app-owned fields
4. **test_idempotent_ingestion**: Running ingestion twice produces same result
5. **test_conflict_detection**: Conflict report generated correctly
6. **test_source_priority**: PeopleSoft wins over Zycus for same field

## Monitoring

Track ingestion metrics:
- Records merged (updated existing vendor)
- Records inserted (new vendor)
- Fields skipped due to override (by field name)
- Conflicts detected (by field name)
- Override flags set by users (by field name)

Alert if:
- Override skip rate >20% (possible ingestion mapping issue)
- Conflict rate >10% (data quality problem)
- Zero records merged for >2 days (ingestion pipeline broken)

---

Last updated: 2026-02-15
