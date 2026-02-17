"""
Permission definitions and role mappings.

This module defines the mapping between roles and their permitted change types.
"""

# Role to change types mapping
ROLE_PERMISSIONS = {
    'system_admin': ['*'],  # All permissions

    'vendor_admin': [
        # Vendor permissions
        'vendor_create',
        'vendor_edit',
        'vendor_delete',
        'vendor_owner_create',
        'vendor_owner_delete',
        'vendor_org_assignment_create',
        'vendor_contact_create',
        'vendor_contact_edit',
        'vendor_contact_delete',
        'vendor_address_create',
        'vendor_address_edit',
        'vendor_address_delete',
        'vendor_tag_create',
        'vendor_tag_edit',
        'vendor_tag_delete',
        'vendor_search_settings_edit',
        'vendor_change_request_create',
        
        # Vendor-level associations
        'vendor_doc_create',
        'vendor_demo_map',
        'vendor_demo_map_bulk',
        'vendor_contract_map',
        'vendor_contract_create',
        'vendor_contract_cancel',
        'vendor_contract_update',
        'vendor_contract_map_bulk',
        
        # Project permissions
        'project_create',
        'project_edit',
        'project_delete',
        'project_owner_update',
        'project_doc_create',
        'project_note_create',
        'project_vendor_add',
        'project_offering_add',
        'project_demo_create',
        'project_demo_map',
        'project_demo_update',
        'project_demo_delete',
        
        # Offering permissions
        'offering_create',
        'offering_edit',
        'offering_delete',
        'offering_invoice_create',
        'offering_invoice_edit',
        'offering_invoice_delete',
        'offering_owner_create',
        'offering_owner_edit',
        'offering_owner_delete',
        'offering_contact_create',
        'offering_contact_edit',
        'offering_contact_delete',
        'offering_profile_edit',
        'offering_dataflow_create',
        'offering_dataflow_delete',
        'offering_dataflow_edit',
        'offering_note_create',
        'offering_ticket_create',
        'offering_ticket_update',
        'offering_doc_create',
        
        # Demo permissions
        'demo_create',
        'demo_stage',
        'demo_form_save',
        'demo_form_copy',
        'demo_form_delete',
        'demo_review_form_template',
        'demo_review_form_attach',
        'demo_review_form_submit',
        'demo_doc_create',
        
        # System permissions
        'doc_delete',
        'import_preview',
        'import_apply',
        'approval_decision',
        'access_request',
        'feedback_submit',
        'report_submit',
        'report_email',
        'admin_lookup_manage',
        'admin_role_manage',
        'admin_scope_manage',
        'admin_testing_role',
        
        # View/audit permissions
        'audit_view',
        'vendor_view',
        'vendor_contact_view',
        'vendor_address_view',
        'vendor_search',
        'vendor_export'
    ],

    'vendor_approver': [
        'vendor_approve',
        'vendor_reject',
        'vendor_view',
        'vendor_contact_view',
        'vendor_address_view',
        'audit_view',
        'vendor_search'
    ],

    'vendor_steward': [
        'vendor_edit_metadata',  # Limited edit (not financial fields)
        'vendor_contact_edit',
        'vendor_address_edit',
        'vendor_tag_create',
        'vendor_tag_edit',
        'vendor_view',
        'vendor_contact_view',
        'vendor_address_view',
        'vendor_search'
    ],

    'vendor_editor': [
        # Vendor permissions
        'vendor_create',
        'vendor_edit',
        'vendor_owner_create',
        'vendor_org_assignment_create',
        'vendor_contact_create',
        'vendor_contact_edit',
        'vendor_address_create',
        'vendor_address_edit',
        'vendor_tag_create',
        'vendor_search_settings_edit',
        'vendor_change_request_create',
        
        # Vendor-level associations
        'vendor_doc_create',
        'vendor_demo_map',
        'vendor_contract_map',
        'vendor_contract_create',
        'vendor_contract_update',
        
        # Project permissions
        'project_create',
        'project_edit',
        'project_owner_update',
        'project_doc_create',
        'project_note_create',
        'project_vendor_add',
        'project_offering_add',
        'project_demo_create',
        'project_demo_map',
        'project_demo_update',
        
        # Offering permissions
        'offering_create',
        'offering_edit',
        'offering_invoice_create',
        'offering_invoice_edit',
        'offering_owner_create',
        'offering_owner_edit',
        'offering_contact_create',
        'offering_contact_edit',
        'offering_profile_edit',
        'offering_dataflow_create',
        'offering_dataflow_edit',
        'offering_note_create',
        'offering_ticket_create',
        'offering_ticket_update',
        'offering_doc_create',
        
        # Demo permissions
        'demo_create',
        'demo_stage',
        'demo_form_save',
        'demo_form_copy',
        'demo_review_form_template',
        'demo_review_form_attach',
        'demo_review_form_submit',
        'demo_doc_create',
        
        # System permissions
        'import_preview',
        'import_apply',
        'access_request',
        'feedback_submit',
        'report_submit',
        'report_email',
        
        # View permissions
        'vendor_view',
        'vendor_contact_view',
        'vendor_address_view',
        'vendor_search'
    ],

    'vendor_viewer': [
        'vendor_view',
        'vendor_contact_view',
        'vendor_address_view',
        'vendor_search',
        'vendor_export'
    ],

    'vendor_auditor': [
        'vendor_view',
        'vendor_contact_view',
        'vendor_address_view',
        'audit_view',
        'audit_export',
        'vendor_search'
    ]
}


def get_permissions_for_role(role: str) -> list[str]:
    """
    Get list of permitted change types for a role.
    
    Args:
        role: Role name (e.g., 'vendor_admin')
    
    Returns:
        List of change type strings
    """
    return ROLE_PERMISSIONS.get(role, [])


def role_can_apply_change(role: str, change_type: str) -> bool:
    """
    Check if role has permission for change type.
    
    Args:
        role: Role name
        change_type: Change type to check
    
    Returns:
        True if role has permission, False otherwise
    """
    if role == 'system_admin':
        return True  # system_admin has all permissions

    permissions = get_permissions_for_role(role)
    return change_type in permissions
