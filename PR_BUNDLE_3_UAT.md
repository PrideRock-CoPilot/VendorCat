# PR Bundle 3: UAT Plan

## Feature: Full Role-Based Access Control (RBAC) Enforcement
**Objective**: Verify that all write operations across the application are protected by permission checks, and that different roles have appropriate access levels.

---

## 1. Preconditions
- **Environment**: Staging or Local Dev (`TVENDOR_ENV=dev`) with Local DB.
- **Test Users**:
    - `admin@vendorcat.com` (System Admin)
    - `vendor_editor@vendorcat.com` (Vendor Editor)
    - `vendor_viewer@vendorcat.com` (Vendor Viewer/Steward)
    - `no_access@vendorcat.com` (No Role)

## 2. Test Scenarios

### Scenario A: Vendor Management (Editor vs Viewer)
| Step | Actor | Action | Expected Result |
|------|-------|--------|-----------------|
| 1 | `vendor_editor` | Navigate to a Vendor "Ownership" tab | "Add Owner" button is visible. |
| 2 | `vendor_editor` | Click "Add Owner" and submit form | Success message. Owner added. |
| 3 | `vendor_viewer` | Navigate to same Vendor "Ownership" tab | "Add Owner" button is HIDDEN or disabled. |
| 4 | `vendor_viewer` | Attempt to POST directly to `/vendors/{id}/owners/add` (via script/curl) | **403 Forbidden**. Error page or JSON response. |

### Scenario B: Offering Management (CRUD Operations)
| Step | Actor | Action | Expected Result |
|------|-------|--------|-----------------|
| 1 | `vendor_editor` | Create a new Offering for a Vendor | Success. Redirected to Offering page. |
| 2 | `vendor_editor` | Edit Offering Profile (Summary/Description) | Success. Changes saved. |
| 3 | `vendor_viewer` | Attempt to Create Offering | **403 Forbidden** (if button somehow accessible). |
| 4 | `vendor_viewer` | Attempt to Edit Offering Profile | **403 Forbidden**. |
| 5 | `vendor_editor` | Delete an Offering Contact | Success. Contact removed. |
| 6 | `vendor_viewer` | Attempt to Delete Offering Contact | **403 Forbidden**. |

### Scenario C: Admin-Only Erasure
| Step | Actor | Action | Expected Result |
|------|-------|--------|-----------------|
| 1 | `vendor_editor` | Try to **Delete** a Vendor | **403 Forbidden**. Only Admins can delete vendors. |
| 2 | `admin` | Delete a Vendor | Success. |

### Scenario D: Document Management
| Step | Actor | Action | Expected Result |
|------|-------|--------|-----------------|
| 1 | `vendor_editor` | Link a Document URL to a Project | Success. |
| 2 | `vendor_editor` | Remove a linked Document | Success (Verified `doc_delete` permission). |
| 3 | `vendor_viewer` | Attempt to Remove a Document | **403 Forbidden**. |

## 3. Negative Testing
1. **Unauthenticated Access**: Try to POST to `/vendors/{id}/update` without being logged in. should redirect to Login or return 401.
2. **Cross-Tenant Access**: User from Org A tries to edit Vendor from Org B. Should return 403 (checked by `check_org_scope` + RBAC).

## 4. Acceptance Criteria
- [ ] All "Mutation" endpoints (POST/PUT/DELETE) reject users without specific permissions.
- [ ] `vendor_editor` role can perform all standard CRUD operations except destructive Deletes of top-level entities if restricted.
- [ ] `vendor_viewer` cannot perform ANY writes.
- [ ] Audit logs show "Permission denied" warnings for failed attempts.
