# Vendor Catalog REST API Documentation

## Overview

The Vendor Catalog REST API provides comprehensive endpoints for managing vendors, contacts, identifiers, onboarding workflows, and related entities. All endpoints require authentication (API token or session).

## Base URL

```
http://localhost:8011/api/v1/
```

## Authentication

Include your authentication token in request headers:

```
Authorization: Token YOUR_AUTH_TOKEN
```

## Endpoints

### Vendors

#### List Vendors
```
GET /api/v1/vendors/
```

**Query Parameters:**
- `page` (int): Page number (default: 1)
- `page_size` (int): Results per page (default: 20, max: 100)
- `lifecycle_state` (string): Filter by state (active, inactive, pending)
- `risk_tier` (string): Filter by risk level (low, medium, high, critical)
- `owner_org_id` (string): Filter by owning organization
- `search` (string): Search by vendor_id, legal_name, or display_name
- `ordering` (string): Order by field (vendor_id, created_at, updated_at, risk_tier)

**Example:**
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8011/api/v1/vendors/?lifecycle_state=active&risk_tier=high"
```

**Response:**
```json
{
  "count": 150,
  "next": "http://localhost:8011/api/v1/vendors/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "vendor_id": "VENDOR-001",
      "display_name": "Acme Corp",
      "legal_name": "Acme Corporation",
      "lifecycle_state": "active",
      "risk_tier": "medium",
      "contact_count": 3,
      "identifier_count": 2,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-02-20T15:45:00Z"
    }
  ]
}
```

#### Get Vendor Details
```
GET /api/v1/vendors/{id}/
```

**Response:**
```json
{
  "id": 1,
  "vendor_id": "VENDOR-001",
  "legal_name": "Acme Corporation",
  "display_name": "Acme Corp",
  "lifecycle_state": "active",
  "owner_org_id": "ORG-001",
  "risk_tier": "medium",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-02-20T15:45:00Z",
  "contacts": [
    {
      "id": 1,
      "full_name": "John Smith",
      "contact_type": "primary",
      "email": "john@acme.com",
      "phone": "+1-555-0100",
      "is_primary": true,
      "is_active": true
    }
  ],
  "identifiers": [
    {
      "id": 1,
      "identifier_type": "duns",
      "identifier_value": "123456789",
      "country_code": "US",
      "is_verified": true
    }
  ],
  "business_owners": [],
  "org_assignments": [],
  "onboarding_workflow": {
    "id": 1,
    "current_state": "active",
    "initiated_at": "2024-01-15T10:30:00Z"
  }
}
```

#### Create Vendor
```
POST /api/v1/vendors/
```

**Request Body:**
```json
{
  "vendor_id": "VENDOR-NEW",
  "legal_name": "New Vendor LLC",
  "display_name": "New Vendor",
  "lifecycle_state": "active",
  "risk_tier": "medium",
  "owner_org_id": "ORG-001"
}
```

#### Update Vendor
```
PATCH /api/v1/vendors/{id}/
```

**Request Body:**
```json
{
  "legal_name": "Updated Legal Name",
  "display_name": "Updated Display",
  "risk_tier": "high"
}
```

#### Delete Vendor
```
DELETE /api/v1/vendors/{id}/
```

#### Get Vendor Contacts
```
GET /api/v1/vendors/{id}/contacts/
```

#### Get Vendor Identifiers
```
GET /api/v1/vendors/{id}/identifiers/
```

#### Get Vendor Notes
```
GET /api/v1/vendors/{id}/notes/
```

#### Get Vendor Warnings
```
GET /api/v1/vendors/{id}/warnings/
```

#### Get Vendor Tickets
```
GET /api/v1/vendors/{id}/tickets/
```

#### Get Vendor Summary
```
GET /api/v1/vendors/{id}/summary/
```

**Response:**
```json
{
  "vendor_id": "VENDOR-001",
  "display_name": "Acme Corp",
  "contact_count": 3,
  "identifier_count": 2,
  "note_count": 5,
  "warning_count": 1,
  "open_ticket_count": 2,
  "business_owner_count": 1,
  "org_assignment_count": 1
}
```

### Vendor Contacts

#### List Vendor Contacts
```
GET /api/v1/vendor-contacts/
```

**Query Parameters:**
- `vendor_id` (string): Filter by vendor vendor_id
- `contact_type` (string): Filter by contact type
- `is_active` (boolean): Filter by active status
- `is_primary` (boolean): Filter by primary status
- `search` (string): Search by full_name or email

#### Create Vendor Contact
```
POST /api/v1/vendor-contacts/
```

**Request Body:**
```json
{
  "vendor": 1,
  "full_name": "Jane Doe",
  "contact_type": "support",
  "email": "jane@example.com",
  "phone": "+1-555-0101",
  "title": "Support Manager",
  "is_primary": false,
  "notes": "Primary support contact"
}
```

### Vendor Identifiers

#### List Vendor Identifiers
```
GET /api/v1/vendor-identifiers/
```

**Query Parameters:**
- `vendor_id` (string): Filter by vendor vendor_id
- `identifier_type` (string): Filter by identifier type
- `is_verified` (boolean): Filter by verification status

#### Create Vendor Identifier
```
POST /api/v1/vendor-identifiers/
```

**Request Body:**
```json
{
  "vendor": 1,
  "identifier_type": "tax_id",
  "identifier_value": "98-7654321",
  "country_code": "US",
  "is_primary": false,
  "is_verified": true,
  "verified_by": "compliance@company.com"
}
```

### Onboarding Workflows

#### List Workflows
```
GET /api/v1/onboarding-workflows/
```

**Query Parameters:**
- `current_state` (string): Filter by state
- `vendor` (int): Filter by vendor ID

#### Get Workflow Details
```
GET /api/v1/onboarding-workflows/{id}/
```

**Response:**
```json
{
  "id": 1,
  "vendor": 1,
  "current_state": "active",
  "current_state_display": "Active",
  "initiated_by": "admin@company.com",
  "initiated_at": "2024-01-15T10:30:00Z",
  "next_states": {
    "active": "Active"
  },
  "days_in_state": 36,
  "total_onboarding_days": 36,
  "status_change_reason": "onboarding_complete",
  "assigned_reviewer": "reviewer@company.com",
  "assigned_date": "2024-01-20T14:00:00Z"
}
```

#### Change Workflow State
```
POST /api/v1/onboarding-workflows/{id}/change_state/
```

**Request Body:**
```json
{
  "action": "approve_vendor",
  "reviewer": "manager@company.com",
  "notes": "Approved after compliance review"
}
```

**Available Actions:**
- `request_information` - Request additional information
- `mark_information_received` - Mark as information received
- `assign_for_review` - Assign for review
- `approve_vendor` - Approve vendor
- `reject_vendor` - Reject vendor
- `activate_vendor` - Activate vendor
- `archive_workflow` - Archive workflow
- `reopen_draft` - Reopen as draft

#### Get Workflow History
```
GET /api/v1/onboarding-workflows/{id}/history/
```

### Vendor Notes

#### List Vendor Notes
```
GET /api/v1/vendor-notes/
```

**Query Parameters:**
- `vendor_id` (string): Filter by vendor vendor_id
- `note_type` (string): Filter by note type

#### Create Vendor Note
```
POST /api/v1/vendor-notes/
```

**Request Body:**
```json
{
  "vendor": 1,
  "note_type": "compliance",
  "note_text": "Compliance review completed successfully",
  "created_by": "reviewer@company.com"
}
```

### Vendor Warnings

#### List Vendor Warnings
```
GET /api/v1/vendor-warnings/
```

**Query Parameters:**
- `vendor_id` (string): Filter by vendor vendor_id
- `severity` (string): Filter by severity (info, warning, critical)
- `status` (string): Filter by status (active, acknowledged, resolved)

#### Create Vendor Warning
```
POST /api/v1/vendor-warnings/
```

**Request Body:**
```json
{
  "vendor": 1,
  "warning_category": "compliance",
  "severity": "critical",
  "title": "Missing Compliance Documentation",
  "detail": "Vendor needs to submit SOC 2 compliance certificate",
  "detected_at": "2024-02-20T10:00:00Z",
  "created_by": "compliance@company.com"
}
```

### Vendor Tickets

#### List Vendor Tickets
```
GET /api/v1/vendor-tickets/
```

**Query Parameters:**
- `vendor_id` (string): Filter by vendor vendor_id
- `status` (string): Filter by status (open, in_progress, closed)
- `priority` (string): Filter by priority (low, medium, high, critical)

#### Create Vendor Ticket
```
POST /api/v1/vendor-tickets/
```

**Request Body:**
```json
{
  "vendor": 1,
  "title": "Security Assessment Required",
  "description": "Vendor needs to complete security assessment",
  "status": "open",
  "priority": "high",
  "opened_date": "2024-02-20T10:00:00Z",
  "created_by": "security@company.com"
}
```

### Vendor Demos

#### List Vendor Demos
```
GET /api/v1/vendor-demos/
```

**Query Parameters:**
- `vendor_id` (string): Filter by vendor vendor_id
- `selection_outcome` (string): Filter by outcome (selected, not_selected, pending)

#### Create Vendor Demo
```
POST /api/v1/vendor-demos/
```

**Request Body:**
```json
{
  "vendor": 1,
  "offering_id": "OFFERING-123",
  "demo_id": "DEMO-001",
  "demo_date": "2024-02-22T14:00:00Z",
  "overall_score": 87.5,
  "selection_outcome": "selected",
  "attendees_internal": "John Smith, Jane Doe",
  "created_by": "evaluator@company.com"
}
```

### Demo Scores

#### Add Demo Score
```
POST /api/v1/demo-scores/
```

**Request Body:**
```json
{
  "demo": 1,
  "score_category": "usability",
  "score_value": 92,
  "weight": 1.0,
  "comments": "Excellent user interface"
}
```

**Score Values:** 0-100

### Business Owners

#### List Business Owners
```
GET /api/v1/vendor-business-owners/
```

**Query Parameters:**
- `vendor_id` (string): Filter by vendor vendor_id
- `is_primary` (boolean): Filter by primary status

#### Assign Business Owner
```
POST /api/v1/vendor-business-owners/
```

**Request Body:**
```json
{
  "vendor": 1,
  "owner_user_principal": "manager@company.com",
  "owner_name": "John Manager",
  "owner_department": "Procurement",
  "is_primary": true,
  "assigned_by": "admin@company.com"
}
```

### Organization Assignments

#### List Organization Assignments
```
GET /api/v1/vendor-org-assignments/
```

#### Assign Organization
```
POST /api/v1/vendor-org-assignments/
```

**Request Body:**
```json
{
  "vendor": 1,
  "org_id": "ORG-001",
  "org_name": "Procurement Department",
  "is_primary": true,
  "assigned_by": "admin@company.com"
}
```

## Error Responses

All endpoints return appropriate HTTP status codes:

- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Permission denied
- `404 Not Found` - Resource not found
- `409 Conflict` - Duplicate resource
- `500 Internal Server Error` - Server error

**Error Response Format:**
```json
{
  "detail": "Error message describing what went wrong",
  "field_name": ["Error for specific field"]
}
```

## Filtering and Search

Most endpoints support filtering and searching via query parameters:

**Example:**
```bash
GET /api/v1/vendors/?lifecycle_state=active&search=acme&ordering=-created_at
```

## Pagination

List endpoints return paginated results by default:

```json
{
  "count": 150,
  "next": "http://localhost:8011/api/v1/vendors/?page=2",
  "previous": null,
  "results": [...]
}
```

**Pagination Parameters:**
- `page` (int): Page number (default: 1)
- `page_size` (int): Results per page (default: 20, max: 100)

## Rate Limiting

Currently no rate limits are enforced. Future versions may implement rate limiting.

## Versioning

The API uses URL-based versioning (v1). Future versions will be available as:
- `/api/v2/...`
- `/api/v3/...`

## Management Commands

### Seed Sample Data
```bash
python manage.py seed_vendors --count 10
```

Clear existing data:
```bash
python manage.py seed_vendors --clear --count 10
```

### Generate Reports
```bash
python manage.py vendor_reports --report summary
python manage.py vendor_reports --report all --format json
```

## WebHooks (Future)

Future versions will support webhooks for:
- Vendor status changes
- Warning escalations
- Workflow state transitions
- Ticket updates

## Import/Export

**Export Vendors (CSV)** - Coming soon
**Import Vendors (CSV)** - Coming soon

## Support

For API issues, contact support@company.com

## Changelog

### Version 1.0 (Current)
- Initial release
- Core vendor management endpoints
- Onboarding workflow state machine
- Vendor notes, warnings, and tickets
- Demo and evaluation tracking
- Business owner and organization assignment
