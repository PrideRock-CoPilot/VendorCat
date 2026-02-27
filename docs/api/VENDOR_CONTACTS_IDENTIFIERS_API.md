# Vendor Contacts & Identifiers API Documentation

**Version:** 1.0  
**Released:** February 2026  
**Base URL:** `/vendor-360/api/{vendor_id}/`

---

## Overview

These endpoints provide full CRUD (Create, Read, Update, Delete) operations for vendor contact information and business identifiers. All endpoints require authentication and appropriate role-based permissions.

### Quick Links
- [Vendor Contacts API](#vendor-contacts-api)
- [Vendor Identifiers API](#vendor-identifiers-api)
- [Error Handling](#error-handling)
- [Response Formats](#response-formats)
- [Examples](#examples)

---

## Vendor Contacts API

### Resource: VendorContact

Represents contact information for a vendor (sales reps, support contacts, billing, etc.).

**Contact Types:**
- `primary` - Primary contact for vendor relationship
- `sales` - Sales representative
- `support` - Support/technical contact
- `billing` - Billing/payments contact
- `technical` - Technical point of contact
- `executive` - Executive sponsor
- `other` - Other contact type

### GET /vendor-360/api/{vendor_id}/contacts

Retrieve all contacts for a vendor.

**Parameters:**
| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| `vendor_id` | string | path | yes | The vendor ID (e.g., "TEST-001") |

**Response:** 200 OK
```json
{
  "contacts": [
    {
      "id": 1,
      "vendor": 5,
      "full_name": "John Doe",
      "contact_type": "primary",
      "email": "john@vendor.com",
      "phone": "555-1234",
      "title": "VP Sales",
      "is_primary": true,
      "is_active": true,
      "notes": "Primary point of contact",
      "created_at": "2026-02-20T14:30:00Z",
      "updated_at": "2026-02-20T14:30:00Z"
    },
    {
      "id": 2,
      "vendor": 5,
      "full_name": "Jane Smith",
      "contact_type": "support",
      "email": "support@vendor.com",
      "phone": "555-5678",
      "title": "Support Manager",
      "is_primary": false,
      "is_active": true,
      "notes": null,
      "created_at": "2026-02-20T15:00:00Z",
      "updated_at": "2026-02-20T15:00:00Z"
    }
  ]
}
```

**Permissions Required:** `vendor.read` (implied through vendor access)

**Error Responses:**
- `404 Not Found` - Vendor does not exist

---

### POST /vendor-360/api/{vendor_id}/contacts

Create a new contact for a vendor.

**Parameters:**
| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| `vendor_id` | string | path | yes | The vendor ID |

**Request Body:**
```json
{
  "full_name": "Bob Johnson",
  "contact_type": "billing",
  "email": "billing@vendor.com",
  "phone": "555-9999",
  "title": "AP Manager",
  "is_primary": false,
  "is_active": true,
  "notes": "Handles invoice and payment processing"
}
```

**Field Validation:**
| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `full_name` | string | yes | max 255 characters |
| `contact_type` | enum | yes | One of: primary, sales, support, billing, technical, executive, other |
| `email` | email | no | Valid email format if provided |
| `phone` | string | no | max 20 characters |
| `title` | string | no | max 255 characters |
| `is_primary` | boolean | no | Default: false |
| `is_active` | boolean | no | Default: true |
| `notes` | string | no | Any length |

**Response:** 201 Created
```json
{
  "id": 3,
  "vendor": 5,
  "full_name": "Bob Johnson",
  "contact_type": "billing",
  "email": "billing@vendor.com",
  "phone": "555-9999",
  "title": "AP Manager",
  "is_primary": false,
  "is_active": true,
  "notes": "Handles invoice and payment processing",
  "created_at": "2026-02-20T16:00:00Z",
  "updated_at": "2026-02-20T16:00:00Z"
}
```

**Permissions Required:** `vendor.write`

**Error Responses:**
- `400 Bad Request` - Validation error (see response for details)
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Vendor does not exist

**Validation Errors Example:**
```json
{
  "full_name": ["This field may not be blank."],
  "email": ["Enter a valid email address."]
}
```

---

### GET /vendor-360/api/{vendor_id}/contacts/{contact_id}

Retrieve a specific contact by ID.

**Parameters:**
| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| `vendor_id` | string | path | yes | The vendor ID |
| `contact_id` | integer | path | yes | The contact ID |

**Response:** 200 OK
```json
{
  "id": 1,
  "vendor": 5,
  "full_name": "John Doe",
  "contact_type": "primary",
  "email": "john@vendor.com",
  "phone": "555-1234",
  "title": "VP Sales",
  "is_primary": true,
  "is_active": true,
  "notes": "Primary point of contact",
  "created_at": "2026-02-20T14:30:00Z",
  "updated_at": "2026-02-20T14:30:00Z"
}
```

**Permissions Required:** `vendor.read` (implied)

**Error Responses:**
- `404 Not Found` - Contact or vendor not found

---

### PATCH /vendor-360/api/{vendor_id}/contacts/{contact_id}

Update an existing contact (partial update).

**Parameters:**
| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| `vendor_id` | string | path | yes | The vendor ID |
| `contact_id` | integer | path | yes | The contact ID |

**Request Body (all fields optional):**
```json
{
  "phone": "555-1111",
  "is_active": false,
  "notes": "No longer active - left company"
}
```

**Response:** 200 OK
```json
{
  "id": 1,
  "vendor": 5,
  "full_name": "John Doe",
  "contact_type": "primary",
  "email": "john@vendor.com",
  "phone": "555-1111",
  "title": "VP Sales",
  "is_primary": true,
  "is_active": false,
  "notes": "No longer active - left company",
  "created_at": "2026-02-20T14:30:00Z",
  "updated_at": "2026-02-20T16:15:00Z"
}
```

**Permissions Required:** `vendor.write`

**Error Responses:**
- `400 Bad Request` - Validation error
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Contact or vendor not found

---

### DELETE /vendor-360/api/{vendor_id}/contacts/{contact_id}

Delete a contact.

**Parameters:**
| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| `vendor_id` | string | path | yes | The vendor ID |
| `contact_id` | integer | path | yes | The contact ID |

**Response:** 204 No Content

**Permissions Required:** `vendor.write`

**Error Responses:**
- `403 Forbidden` - Insufficient permissions  
- `404 Not Found` - Contact or vendor not found

---

## Vendor Identifiers API

### Resource: VendorIdentifier

Represents business identifiers for a vendor (DUNS, Tax ID, ERP codes, etc.).

**Identifier Types:**
- `duns` - DUNS Number (Dun & Bradstreet)
- `tax_id` - Tax ID / EIN (US)
- `vat_id` - VAT ID (Europe)
- `gln` - GLN (Global Location Number)
- `erp_id` - ERP Vendor ID (internal system)
- `sap_id` - SAP Vendor Code
- `internal_id` - Internal/proprietary ID
- `d_u_n_s_plus_4` - DUNS+4 format
- `cage_code` - CAGE Code (US government)
- `other` - Other identifier type

### GET /vendor-360/api/{vendor_id}/identifiers

Retrieve all identifiers for a vendor.

**Parameters:**
| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| `vendor_id` | string | path | yes | The vendor ID |

**Response:** 200 OK
```json
{
  "identifiers": [
    {
      "id": 1,
      "vendor": 5,
      "identifier_type": "duns",
      "identifier_value": "123456789",
      "country_code": "US",
      "is_primary": true,
      "is_verified": true,
      "verified_at": "2026-01-15T10:00:00Z",
      "verified_by": "admin@company.com",
      "notes": "Verified against Dun & Bradstreet",
      "created_at": "2026-01-10T08:00:00Z",
      "updated_at": "2026-02-20T14:30:00Z"
    },
    {
      "id": 2,
      "vendor": 5,
      "identifier_type": "tax_id",
      "identifier_value": "12-3456789",
      "country_code": "US",
      "is_primary": false,
      "is_verified": false,
      "verified_at": null,
      "verified_by": null,
      "notes": null,
      "created_at": "2026-02-20T15:00:00Z",
      "updated_at": "2026-02-20T15:00:00Z"
    }
  ]
}
```

**Permissions Required:** `vendor.read` (implied)

**Error Responses:**
- `404 Not Found` - Vendor does not exist

---

### POST /vendor-360/api/{vendor_id}/identifiers

Create a new identifier for a vendor.

**Parameters:**
| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| `vendor_id` | string | path | yes | The vendor ID |

**Request Body:**
```json
{
  "identifier_type": "erp_id",
  "identifier_value": "VENDOR-12345",
  "country_code": "US",
  "is_primary": false,
  "notes": "SAP vendor code for payables"
}
```

**Field Validation:**
| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `identifier_type` | enum | yes | One of the types listed above |
| `identifier_value` | string | yes | max 255 characters; unique per (vendor, type, value) |
| `country_code` | string | no | 2-character ISO country code |
| `is_primary` | boolean | no | Default: false |
| `is_verified` | boolean | no | Default: false |
| `verified_at` | datetime | no | ISO 8601 format |
| `verified_by` | string | no | Email or user identifier |
| `notes` | string | no | Any length |

**Response:** 201 Created
```json
{
  "id": 3,
  "vendor": 5,
  "identifier_type": "erp_id",
  "identifier_value": "VENDOR-12345",
  "country_code": "US",
  "is_primary": false,
  "is_verified": false,
  "verified_at": null,
  "verified_by": null,
  "notes": "SAP vendor code for payables",
  "created_at": "2026-02-20T16:00:00Z",
  "updated_at": "2026-02-20T16:00:00Z"
}
```

**Permissions Required:** `vendor.write`

**Error Responses:**
- `400 Bad Request` - Validation error (including duplicate identifier)
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Vendor does not exist

**Unique Constraint Error Example:**
```json
{
  "non_field_errors": ["This duns already exists for this vendor"]
}
```

---

### GET /vendor-360/api/{vendor_id}/identifiers/{identifier_id}

Retrieve a specific identifier by ID.

**Parameters:**
| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| `vendor_id` | string | path | yes | The vendor ID |
| `identifier_id` | integer | path | yes | The identifier ID |

**Response:** 200 OK
```json
{
  "id": 1,
  "vendor": 5,
  "identifier_type": "duns",
  "identifier_value": "123456789",
  "country_code": "US",
  "is_primary": true,
  "is_verified": true,
  "verified_at": "2026-01-15T10:00:00Z",
  "verified_by": "admin@company.com",
  "notes": "Verified against Dun & Bradstreet",
  "created_at": "2026-01-10T08:00:00Z",
  "updated_at": "2026-02-20T14:30:00Z"
}
```

**Permissions Required:** `vendor.read` (implied)

**Error Responses:**
- `404 Not Found` - Identifier or vendor not found

---

### PATCH /vendor-360/api/{vendor_id}/identifiers/{identifier_id}

Update an existing identifier (partial update).

**Parameters:**
| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| `vendor_id` | string | path | yes | The vendor ID |
| `identifier_id` | integer | path | yes | The identifier ID |

**Request Body (all fields optional):**
```json
{
  "is_verified": true,
  "verified_at": "2026-02-20T16:00:00Z",
  "verified_by": "auditor@company.com",
  "notes": "Verified with third-party service"
}
```

**Response:** 200 OK
```json
{
  "id": 1,
  "vendor": 5,
  "identifier_type": "duns",
  "identifier_value": "123456789",
  "country_code": "US",
  "is_primary": true,
  "is_verified": true,
  "verified_at": "2026-02-20T16:00:00Z",
  "verified_by": "auditor@company.com",
  "notes": "Verified with third-party service",
  "created_at": "2026-01-10T08:00:00Z",
  "updated_at": "2026-02-20T16:30:00Z"
}
```

**Permissions Required:** `vendor.write`

**Error Responses:**
- `400 Bad Request` - Validation error
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Identifier or vendor not found

---

### DELETE /vendor-360/api/{vendor_id}/identifiers/{identifier_id}

Delete an identifier.

**Parameters:**
| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| `vendor_id` | string | path | yes | The vendor ID |
| `identifier_id` | integer | path | yes | The identifier ID |

**Response:** 204 No Content

**Permissions Required:** `vendor.write`

**Error Responses:**
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Identifier or vendor not found

---

## Response Formats

### Success Response Structure

All successful responses follow this pattern:

**Single Resource (GET, POST, PATCH, DELETE):**
```json
{
  "id": 1,
  "vendor": 5,
  "field_name": "value",
  ...
  "created_at": "2026-02-20T14:30:00Z",
  "updated_at": "2026-02-20T14:30:00Z"
}
```

**Multiple Resources (GET list):**
```json
{
  "contacts": [...],
}
```

**Delete Success:**
```
HTTP/1.1 204 No Content
```

### Error Response Structure

```json
{
  "error": "error_code",
  "detail": "Detailed error message",
  "field_errors": {
    "field_name": ["Error message for this field"]
  }
}
```

### HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| `200` | Success | GET successful, PATCH successful |
| `201` | Created | POST successful |
| `204` | No Content | DELETE successful |
| `400` | Bad Request | Invalid data, validation failed |
| `403` | Forbidden | User lacks required permissions |
| `404` | Not Found | Vendor/contact/identifier doesn't exist |
| `500` | Server Error | Unexpected error (rare) |

---

## Error Handling

### Common Error Scenarios

**Vendor Not Found:**
```json
{
  "error": "not_found",
  "detail": "vendor TEST-999 not found"
}
```
**HTTP 404**

**Invalid Email Format:**
```json
{
  "email": ["Enter a valid email address."]
}
```
**HTTP 400**

**Missing Required Field:**
```json
{
  "full_name": ["This field may not be blank."]
}
```
**HTTP 400**

**Duplicate Identifier:**
```json
{
  "non_field_errors": ["This duns already exists for this vendor"]
}
```
**HTTP 400**

**Permission Denied:**
```json
{
  "error": "forbidden",
  "reason": "User lacks 'vendor.write' permission"
}
```
**HTTP 403**

---

## Examples

### Example 1: Create a Contact and Identifier for a New Vendor

**Step 1: Create Primary Contact**
```bash
curl -X POST http://localhost:8011/vendor-360/api/ACME-001/contacts \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Alice Johnson",
    "contact_type": "primary",
    "email": "alice@acme.com",
    "phone": "212-555-0100",
    "title": "Procurement Director",
    "is_primary": true,
    "is_active": true
  }'
```

**Response:**
```json
{
  "id": 1,
  "vendor": 1,
  "full_name": "Alice Johnson",
  "contact_type": "primary",
  "email": "alice@acme.com",
  "phone": "212-555-0100",
  "title": "Procurement Director",
  "is_primary": true,
  "is_active": true,
  "notes": null,
  "created_at": "2026-02-20T10:00:00Z",
  "updated_at": "2026-02-20T10:00:00Z"
}
```

**Step 2: Add DUNS Identifier**
```bash
curl -X POST http://localhost:8011/vendor-360/api/ACME-001/identifiers \
  -H "Content-Type: application/json" \
  -d '{
    "identifier_type": "duns",
    "identifier_value": "087654321",
    "country_code": "US",
    "is_primary": true
  }'
```

**Response:**
```json
{
  "id": 1,
  "vendor": 1,
  "identifier_type": "duns",
  "identifier_value": "087654321",
  "country_code": "US",
  "is_primary": true,
  "is_verified": false,
  "verified_at": null,
  "verified_by": null,
  "notes": null,
  "created_at": "2026-02-20T10:05:00Z",
  "updated_at": "2026-02-20T10:05:00Z"
}
```

### Example 2: Update Contact and Mark Identifier as Verified

**Update Contact Phone:**
```bash
curl -X PATCH http://localhost:8011/vendor-360/api/ACME-001/contacts/1 \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "212-555-0200",
    "notes": "Updated primary contact number"
  }'
```

**Verify Identifier:**
```bash
curl -X PATCH http://localhost:8011/vendor-360/api/ACME-001/identifiers/1 \
  -H "Content-Type: application/json" \
  -d '{
    "is_verified": true,
    "verified_at": "2026-02-20T11:00:00Z",
    "verified_by": "compliance@company.com",
    "notes": "Verified via Dun & Bradstreet online service"
  }'
```

### Example 3: List All Contacts and Identifiers

```bash
# Get all contacts
curl -X GET http://localhost:8011/vendor-360/api/ACME-001/contacts

# Get all identifiers
curl -X GET http://localhost:8011/vendor-360/api/ACME-001/identifiers
```

### Example 4: Remove Inactive Contact

```bash
curl -X DELETE http://localhost:8011/vendor-360/api/ACME-001/contacts/1
```

**Response:** HTTP 204 No Content

---

## Authorization & Permissions

### Required Roles

| Operation | Required Permission | Typical Roles |
|-----------|-------------------|----------------|
| GET (list/detail) | `vendor.read` | vendor_viewer, vendor_editor, vendor_admin |
| POST (create) | `vendor.write` | vendor_editor, vendor_admin |
| PATCH (update) | `vendor.write` | vendor_editor, vendor_admin |
| DELETE | `vendor.write` | vendor_admin |

### Permission Context

All endpoints are gated by the `vendor.write` or `vendor.read` permissions defined in the permission registry. Users must be authenticated and have the appropriate role assignment.

---

## Rate Limiting & Performance

- **No explicit rate limits** on these endpoints (planned for Phase 6)
- **Typical response time:** < 100ms for list operations
- **Typical response time:** < 50ms for single resource operations
- **Pagination:** Not implemented (all contacts/identifiers returned)
- **Future:** Consider pagination for vendors with 100+ contacts

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-20 | 1.0 | Initial API specification |

---

## Support & Questions

For questions about these APIs:
- Check the [source code](../../src/apps/vendors/views.py)
- Review [test examples](../../tests_rebuild/test_vendor_contacts_identifiers.py)
- See [models documentation](../../src/apps/vendors/models.py)
