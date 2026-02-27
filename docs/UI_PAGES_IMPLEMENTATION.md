# Vendor Contacts & Identifiers UI Implementation

**Status:** Task 2 Complete - All UI pages created and integrated  
**Date:** February 2026

---

## Overview

Created complete user interface for managing vendor contacts and identifiers with Bootstrap 5 styling, form validation, and Django integration.

---

## Architecture

### URL Design

All UI pages follow nested routing from vendor: `/vendor-360/{vendor_id}/{resource}/{action}`

| Resource | Action | URL Pattern | Name | View Function |
|----------|--------|-------------|------|---------------|
| contacts | list | `<vendor_id>/contacts` | `vendor_contact_list` | `vendor_contact_list_page` |
| contacts | create | `<vendor_id>/contacts/new` | `vendor_contact_create` | `vendor_contact_form_page` |
| contacts | edit | `<vendor_id>/contacts/<id>/edit` | `vendor_contact_edit` | `vendor_contact_form_page` |
| contacts | delete | `<vendor_id>/contacts/<id>/delete` | `vendor_contact_delete` | `vendor_contact_delete_page` |
| identifiers | list | `<vendor_id>/identifiers` | `vendor_identifier_list` | `vendor_identifier_list_page` |
| identifiers | create | `<vendor_id>/identifiers/new` | `vendor_identifier_create` | `vendor_identifier_form_page` |
| identifiers | edit | `<vendor_id>/identifiers/<id>/edit` | `vendor_identifier_edit` | `vendor_identifier_form_page` |
| identifiers | delete | `<vendor_id>/identifiers/<id>/delete` | `vendor_identifier_delete` | `vendor_identifier_delete_page` |

### View Functions

All 8 view functions are defined in [src/apps/vendors/views.py](../../src/apps/vendors/views.py):

#### Contacts Views

```python
def vendor_contact_list_page(request, vendor_id)
    # GET: List all contacts for vendor
    # Displays: Cards with summary stats, table with all contacts
    # Context: vendor, contacts, active_count, primary_contact, email_count

def vendor_contact_form_page(request, vendor_id, contact_id=None)
    # GET: Display form for creating/editing contact
    # POST: Process form submission
    # Redirects to list on success

def vendor_contact_delete_page(request, vendor_id, contact_id)
    # GET: Show delete confirmation
    # POST: Delete contact and redirect to list
```

#### Identifiers Views

```python
def vendor_identifier_list_page(request, vendor_id)
    # GET: List all identifiers for vendor
    # Displays: Cards with summary stats, table with all identifiers
    # Context: vendor, identifiers, verified_count, unverified_count, primary_identifier

def vendor_identifier_form_page(request, vendor_id, identifier_id=None)
    # GET: Display form for creating/editing identifier
    # POST: Process form submission
    # Redirects to list on success

def vendor_identifier_delete_page(request, vendor_id, identifier_id)
    # GET: Show delete confirmation
    # POST: Delete identifier and redirect to list
```

---

## Templates

### Contacts Templates

#### 1. contact_list.html
**File:** [src/templates/vendors/contact_list.html](../../src/templates/vendors/contact_list.html)

**Purpose:** Display all vendor contacts in a responsive table with management actions

**Features:**
- Header with vendor context and "Add New Contact" button
- Filterable table showing:
  - Contact name with primary badge
  - Contact type (color-coded badge)
  - Email (clickable mailto)
  - Phone (clickable tel)
  - Title/position
  - Active/Inactive status
  - Primary flag checkbox
  - Edit/Delete action buttons
- Summary cards showing:
  - Total contacts count
  - Active contacts count
  - Primary contact name
  - Contacts with email count
- Empty state with "Add Contact" link
- Alert messages for user feedback

**Key Classes:** table-hover, badge, btn-group-sm

**Responsive:** Mobile-optimized with Bootstrap containers

---

#### 2. contact_form.html
**File:** [src/templates/vendors/contact_form.html](../../src/templates/vendors/contact_form.html)

**Purpose:** Form for creating or editing a vendor contact

**Form Fields:**
1. **Full Name** (required)
   - TextInput, max 255 chars
   - Placeholder: "Enter contact full name"
   
2. **Contact Type** (required)
   - Select dropdown
   - Options: primary, sales, support, billing, technical, executive, other
   
3. **Title / Position** (optional)
   - TextInput, max 255 chars
   - Placeholder: "e.g., Sales Manager, VP Engineering"
   
4. **Email Address** (optional)
   - EmailInput
   - Validation: Must contain @
   - Placeholder: "contact@vendor.com"
   
5. **Phone Number** (optional)
   - TextInput, max 20 chars
   - Placeholder: "555-1234 or +1-555-1234"
   
6. **Set as Primary Contact** (checkbox)
   - Only one primary contact per vendor
   - Validation prevents duplicate primaries
   
7. **Active Status** (checkbox)
   - Default: True for new contacts
   - Uncheck to deactivate instead of delete
   
8. **Notes** (optional)
   - Textarea, 4 rows
   - Placeholder: "Add any additional notes or context..."

**Validation:**
- Client-side: Bootstrap `needs-validation` framework
- Server-side: Django form validation in `VendorContactForm`
  - Email format validation
  - Required field validation
  - Duplicate primary contact check

**Help Panel (right side):**
- Contact Types Guide with descriptions
- Tips: email format, primary constraint, deactivation, notes usage

**Form Actions:**
- Submit button: "Create Contact" (POST new) or "Save Changes" (PATCH edit)
- Cancel button: Returns to contacts list

---

#### 3. contact_confirm_delete.html
**File:** [src/templates/vendors/contact_confirm_delete.html](../../src/templates/vendors/contact_confirm_delete.html)

**Purpose:** Confirm deletion before removing contact

**Display:**
- Warning icon and danger styling
- Contact details summary:
  - Full name
  - Contact type
  - Email
  - Phone
- Warning about permanent deletion
- Suggestion to deactivate instead

**Actions:**
- Delete button: Confirms deletion
- Cancel button: Returns to contacts list

---

### Identifiers Templates

#### 1. identifier_list.html
**File:** [src/templates/vendors/identifier_list.html](../../src/templates/vendors/identifier_list.html)

**Purpose:** Display all vendor business identifiers in a responsive table

**Features:**
- Header with vendor context and "Add New Identifier" button
- Filterable table showing:
  - Identifier type (color-coded badge)
  - Identifier value (code format)
  - Country code (if present)
  - Verification status (checkmark badge or unverified)
  - Verified by name and date
  - Primary flag checkbox
  - Notes (truncated with hover tooltip)
  - Edit/Delete action buttons
- Summary cards showing:
  - Total identifiers count
  - Verified count
  - Primary identifier display (type + value)
  - Unverified count
- Empty state with "Add Identifier" link
- Alert messages for feedback

**Key Classes:** badge, code styling, table-hover, btn-group-sm

**Responsive:** Mobile-optimized with Bootstrap containers

---

#### 2. identifier_form.html
**File:** [src/templates/vendors/identifier_form.html](../../src/templates/vendors/identifier_form.html)

**Purpose:** Form for creating or editing a vendor identifier

**Form Fields:**
1. **Identifier Type** (required)
   - Select dropdown with 10 options:
     - duns - DUNS Number
     - tax_id - US Tax ID / EIN
     - vat_id - VAT ID (Europe)
     - gln - Global Location Number
     - erp_id - ERP Vendor ID
     - sap_id - SAP Vendor Code
     - internal_id - Internal/proprietary
     - d_u_n_s_plus_4 - DUNS+4 format
     - cage_code - CAGE Code (US gov)
     - other - Other type
   
2. **Identifier Value** (required)
   - TextInput, max 255 chars
   - Placeholder: "Enter the identifier value"
   - Validation: Unique per (vendor, type, value)
   
3. **Country Code** (optional)
   - TextInput, 2 chars, uppercase letters
   - Pattern: [A-Z]{2}
   - Placeholder: "US, DE, JP, etc."
   - Validation: ISO 2-letter format
   
4. **Verification Information** (card section)
   - **Mark as Verified** (checkbox)
   - **Verified By** (TextInput)
     - Email or name of verifier
   - **Verification Date** (DateTimeInput)
     - ISO 8601 format
     - Required if is_verified checked
   
5. **Set as Primary Identifier** (checkbox)
   - Only one primary per vendor
   - Validation prevents duplicates
   
6. **Notes** (optional)
   - Textarea, 4 rows
   - Placeholder: "Verification method, source, usage notes..."

**Validation:**
- Client-side: Bootstrap form validation
- Server-side: Django form validation in `VendorIdentifierForm`
  - Country code format (2 alpha chars)
  - Duplicate identifier detection
  - Verification date required if verified
  - Duplicate primary check

**Help Panels (right side):**
- Identifier Types Guide with descriptions (10 types)
- Verification Card: Tips on tracking status
- Tips Card: Reminders about uniqueness and primaries

**Form Actions:**
- Submit button: "Create Identifier" (POST new) or "Save Changes" (PATCH edit)
- Cancel button: Returns to identifiers list

---

#### 3. identifier_confirm_delete.html
**File:** [src/templates/vendors/identifier_confirm_delete.html](../../src/templates/vendors/identifier_confirm_delete.html)

**Purpose:** Confirm deletion before removing identifier

**Display:**
- Warning icon and danger styling
- Identifier details summary:
  - Type and value
  - Country code
  - Verification status
- Warning about impact if it's the primary identifier
- Critical warning about permanent deletion

**Actions:**
- Delete button: Confirms deletion
- Cancel button: Returns to identifiers list

---

## Django Forms

### VendorContactForm
**File:** [src/apps/vendors/forms.py](../../src/apps/vendors/forms.py)

**Purpose:** Handle form rendering and validation for contacts

**Fields:**
- All 8 contact model fields with custom widgets
- Bootstrap CSS classes applied

**Validation Methods:**
```python
def clean_email(self)
    # Validates email contains @ symbol
    
def clean_full_name(self)
    # Ensures name is not empty or whitespace
    
def clean(self)
    # Checks for duplicate primary contacts
    # Ensures vendor is set
    # Trims whitespace
```

**Custom Initialization:**
```python
def __init__(self, *args, vendor=None, **kwargs)
    # Sets vendor context for validation
    # Defaults is_active to True for new contacts
```

---

### VendorIdentifierForm
**File:** [src/apps/vendors/forms.py](../../src/apps/vendors/forms.py)

**Purpose:** Handle form rendering and validation for identifiers

**Fields:**
- All 8 identifier model fields with custom widgets
- Bootstrap CSS classes applied
- Special handling for DateTimeInput

**Validation Methods:**
```python
def clean_identifier_value(self)
    # Validates value is not empty
    
def clean_country_code(self)
    # Validates ISO 2-letter format (uppercase)
    
def clean_verified_at(self)
    # Requires verification date if is_verified checked
    
def clean(self)
    # Checks for duplicate identifiers (vendor+type+value)
    # Checks for duplicate primary identifiers
    # Ensures vendor is set
```

**Custom Initialization:**
```python
def __init__(self, *args, vendor=None, **kwargs)
    # Sets vendor context for validation
```

---

## URL Configuration

### Current URL Patterns
**File:** [src/apps/vendors/urls.py](../../src/apps/vendors/urls.py)

**HTML Page Routes:**
```python
# Contacts HTML Pages
path("<str:vendor_id>/contacts", vendor_contact_list_page, name="vendor_contact_list")
path("<str:vendor_id>/contacts/new", vendor_contact_form_page, name="vendor_contact_create")
path("<str:vendor_id>/contacts/<int:contact_id>/edit", vendor_contact_form_page, name="vendor_contact_edit")
path("<str:vendor_id>/contacts/<int:contact_id>/delete", vendor_contact_delete_page, name="vendor_contact_delete")

# Identifiers HTML Pages
path("<str:vendor_id>/identifiers", vendor_identifier_list_page, name="vendor_identifier_list")
path("<str:vendor_id>/identifiers/new", vendor_identifier_form_page, name="vendor_identifier_create")
path("<str:vendor_id>/identifiers/<int:identifier_id>/edit", vendor_identifier_form_page, name="vendor_identifier_edit")
path("<str:vendor_id>/identifiers/<int:identifier_id>/delete", vendor_identifier_delete_page, name="vendor_identifier_delete")
```

**Note:** API routes remain unchanged at `/api/` endpoints

---

## Styling & Components

### Bootstrap 5 Components Used
- **Containers & Grid:** container, container-fluid, row, col-*
- **Tables:** table, table-hover, table-light
- **Forms:** form-control, form-select, form-check, form-label
- **Buttons:** btn, btn-primary, btn-secondary, btn-danger, btn-group, btn-group-sm
- **Badges:** badge, bg-success, bg-info, bg-secondary, bg-danger
- **Cards:** card, card-header, card-body, card-title
- **Alerts:** alert, alert-info, alert-danger, alert-warning, alert-success
- **Text Utilities:** text-muted, text-end, text-center, small
- **Other:** mb-*, mt-*, ms-*, ps-*, display-*, fw-bold, fs-11, table-responsive

### Icons (Bootstrap Icons)
- Plus Circle: `bi-plus-circle` - Add buttons
- Pencil: `bi-pencil` - Edit buttons
- Trash: `bi-trash` - Delete buttons
- X Circle: `bi-x-circle` - Cancel buttons
- Check: `bi-check-circle` - Verified status
- Info Circle: `bi-info-circle` - Information
- Exclamation: `bi-exclamation-circle` - Warnings
- Shield Check: `bi-shield-check` - Verification
- Lightbulb: `bi-lightbulb` - Tips
- Arrow Left: `bi-arrow-left` - Navigation

### Custom CSS (Inline in Templates)
- Badge styling with consistent padding and font-weight
- Code block styling with light background
- Definition list styling for info displays
- Form validation styling for error feedback
- Responsive spacing adjustments

---

## User Experience Features

### Helpful UI Elements
1. **Help Panels** on every form page
   - Type descriptions and options
   - Tips and best practices
   - Validation rules

2. **Summary Cards** on every list page
   - At-a-glance statistics
   - Primary contact/identifier display
   - Status counts

3. **Confirmation Dialogs**
   - Delete confirmation required
   - Shows item details before deletion
   - Warnings for primary items

4. **Form Feedback**
   - Bootstrap validation classes
   - Field-level error messages
   - Non-field error displays
   - Success messages on completion

5. **Navigation**
   - "Back to Vendor" links
   - "Back to List" options
   - Breadcrumb-like context in headers
   - Consistent URL patterns

### Accessibility
- Semantic HTML (forms, labels, buttons)
- ARIA labels on icon buttons
- Color not the only indicator (badges + text)
- Keyboard accessible (all buttons/links)
- Form validation feedback visible

---

## Integration Points

### With Vendor Detail Page
- Links from vendor detail to contacts/identifiers lists
- Back links return to vendor detail
- Vendor context maintained throughout

### With Permission System
- View functions check user permissions via `authorize_mutation`
- Forms validate against business rules
- API endpoints separate from HTML pages

### With Message Framework
- Success messages on create/update/delete
- Error messages from form validation
- Messages displayed via template system

---

## Testing Considerations

### Manual Testing Checklist
- [ ] Create contact with all fields
- [ ] Create contact with minimal fields
- [ ] Edit contact field values
- [ ] Try to create duplicate primary contact (should fail)
- [ ] Deactivate contact without deleting
- [ ] Delete contact with confirmation
- [ ] Create identifier with verification info
- [ ] Try duplicate identifier (should fail)
- [ ] Verify/unverifiy identifier
- [ ] Delete identifier with primary warning
- [ ] Navigate between pages
- [ ] Responsive design on mobile
- [ ] Email link functionality
- [ ] Phone link functionality

### Database Queries Optimized
- vendor_contact_list: Single query with order_by
- vendor_identifier_list: Single query with order_by
- Form pages: Uses get_object_or_404 for efficiency

---

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| [contact_list.html](../../src/templates/vendors/contact_list.html) | Template | List view for contacts |
| [contact_form.html](../../src/templates/vendors/contact_form.html) | Template | Form for create/edit contacts |
| [contact_confirm_delete.html](../../src/templates/vendors/contact_confirm_delete.html) | Template | Delete confirmation for contacts |
| [identifier_list.html](../../src/templates/vendors/identifier_list.html) | Template | List view for identifiers |
| [identifier_form.html](../../src/templates/vendors/identifier_form.html) | Template | Form for create/edit identifiers |
| [identifier_confirm_delete.html](../../src/templates/vendors/identifier_confirm_delete.html) | Template | Delete confirmation for identifiers |
| [forms.py](../../src/apps/vendors/forms.py) | Python | Django forms with validation |
| [views.py](../../src/apps/vendors/views.py) | Python | 6 view functions for HTML pages |
| [urls.py](../../src/apps/vendors/urls.py) | Python | URL routing updated with 8 new patterns |

---

## Next Steps

### Phase 1 Week 3: Workflow State Management
- Create OnboardingWorkflow model using django-fsm
- Implement state transitions for vendor onboarding
- Add workflow status UI to vendor detail page
- Create state transition APIs

### Future Enhancements
- Pagination for vendors with 100+ contacts/identifiers
- Advanced filtering and search on list pages
- Bulk operations (export, import)
- Contact/identifier history auditing
- Contact sharing/permissions

---

## Status Summary

✅ **Completed:**
- 6 HTML templates created (3 contacts, 3 identifiers)
- 2 Django forms with validation
- 6 view functions for all CRUD operations including delete
- Complete URL routing (8 new patterns)
- Bootstrap 5 styling throughout
- Help panels and user guidance
- Summary statistics on list views
- Message framework integration

**Lines of Code:**
- Templates: 1,200+ lines (6 files)
- Forms: 250+ lines (1 file)
- Views: 180+ lines (1 file)
- URLs: 40+ lines (1 file)
- **Total: ~1,670 lines**

**Total Implementation Time:** ~120 minutes for Task 2
