# PR Bundle 3: Full RBAC Rollout
## Endpoints Needing @require_permission Decorators

Based on test_rbac_coverage.py scans, here are the remaining endpoints without permission checks:

### vendor_detail_pages.py (2 endpoints)
1. `@router.post("/{vendor_id}/owners/add")` - add_vendor_owner_submit → vendor_owner_create
2. `@router.post("/{vendor_id}/org-assignments/add")` - add_vendor_org_assignment_submit → vendor_org_assignment_create

### offering_writes.py (1 endpoint)  
3. `@router.post("/{vendor_id}/offerings/{offering_id}/invoices/{invoice_id}/remove")` - remove_offering_invoice_submit → offering_invoice_delete
4. `@router.post("/{vendor_id}/offerings/{offering_id}/owners/remove")` - remove_offering_owner_submit → offering_owner_delete
5. `@router.post("/{vendor_id}/offerings/{offering_id}/owners/{offering_owner_id}/update")` - update_offering_owner_submit → offering_owner_edit
6. `@router.post("/{vendor_id}/offerings/{offering_id}/contacts/remove")` - remove_offering_contact_submit → offering_contact_delete

### offering_profile_writes.py (Multiple endpoints)
7. `@router.post("/{vendor_id}/offerings/{offering_id}/profile/save")` - save_offering_profile_submit → offering_profile_edit
8. `@router.post("/{vendor_id}/offerings/{offering_id}/dataflows/add")` - add_offering_dataflow_submit → offering_dataflow_create
9. `@router.post("/{vendor_id}/offerings/{offering_id}/dataflows/remove")` - remove_offering_dataflow_submit → offering_dataflow_delete
10. `@router.post("/{vendor_id}/offerings/{offering_id}/dataflows/update")` - update_offering_dataflow_submit → offering_dataflow_edit
11. `@router.post("/{vendor_id}/offerings/{offering_id}/notes/add")` - add_offering_note_submit → offering_note_create
12. `@router.post("/{vendor_id}/offerings/{offering_id}/tickets/add")` - add_offering_ticket_submit → offering_ticket_create
13. `@router.post("/{vendor_id}/offerings/{offering_id}/tickets/{ticket_id}/status")` - update_offering_ticket_status → offering_ticket_update

### offering_pages.py (2 endpoints)
14. `@router.post("/{vendor_id}/offerings/new")` - create_offering_submit → offering_create
15. `@router.post("/{vendor_id}/offerings/{offering_id}/update")` - update_offering_submit → offering_edit

### list_pages.py (2 endpoints)
16. `@router.post("/settings")` - save_list_settings → vendor_search_settings_edit
17. `@router.post("/new")` - create_vendor_submit → vendor_create

### docs.py (5 endpoints)
18. `@router.post("/{vendor_id}/docs/link")` - link_vendor_doc → vendor_doc_create
19. `@router.post("/{vendor_id}/projects/{project_id}/docs/link")` - link_project_doc → project_doc_create
20. `@router.post("/{vendor_id}/offerings/{offering_id}/docs/link")` - link_offering_doc → offering_doc_create
21. `@router.post("/{vendor_id}/projects/{project_id}/demos/{demo_id}/docs/link")` - link_demo_doc → demo_doc_create
22. `@router.post("/docs/{doc_id}/remove")` - remove_doc → doc_delete

### demos.py (2 endpoints)
23. `@router.post("/{vendor_id}/map-demo")` - map_demo → vendor_demo_map
24. `@router.post("/{vendor_id}/map-demos/bulk")` - map_demos_bulk → vendor_demo_map_bulk

### contracts.py (5 endpoints)
25. `@router.post("/{vendor_id}/map-contract")` - map_contract → vendor_contract_map
26. `@router.post("/{vendor_id}/contracts/add")` - add_contract → vendor_contract_create
27. `@router.post("/{vendor_id}/contracts/{contract_id}/cancel")` - cancel_contract → vendor_contract_cancel
28. `@router.post("/{vendor_id}/contracts/{contract_id}/update")` - update_contract → vendor_contract_update
29. `@router.post("/{vendor_id}/map-contracts/bulk")` - map_contracts_bulk → vendor_contract_map_bulk

### changes.py (2 endpoints)
30. `@router.post("/{vendor_id}/direct-update")` - direct_update_vendor → vendor_edit
31. `@router.post("/{vendor_id}/change-request")` - request_vendor_change → vendor_change_request_create

Note: Some of these endpoints have inline `user.can_apply_change()` checks which satisfy the RBAC coverage test,
but we want to standardize on @require_permission decorator for all endpoints.

## Total Count
- Already fixed in PR Bundle 2: 5 endpoints
- Remaining: ~26 endpoints (need to verify exact count with test)

## Permissions to Add
Need to add these to permissions.py ROLE_PERMISSIONS for vendor_admin and vendor_editor:
- vendor_owner_create, vendor_org_assignment_create
- offering_invoice_delete, offering_owner_delete, offering_owner_edit, offering_contact_delete
- offering_profile_edit, offering_dataflow_create, offering_dataflow_delete, offering_dataflow_edit
- offering_note_create, offering_ticket_create, offering_ticket_update
- offering_create, offering_edit
- vendor_search_settings_edit, vendor_create
- vendor_doc_create, project_doc_create, offering_doc_create, demo_doc_create, doc_delete
- vendor_demo_map, vendor_demo_map_bulk
- vendor_contract_map, vendor_contract_create, vendor_contract_cancel, vendor_contract_update, vendor_contract_map_bulk
- vendor_change_request_create

## Implementation Plan
1. Update permissions.py with all missing permissions
2. Apply decorators to all endpoints systematically (file by file)
3. Run RBAC coverage test to verify 0 violations
4. Update CI workflow to fail on RBAC violations (remove continue-on-error)
5. Commit and create PR
