"""
Permission definitions and role mappings.

This module defines the mapping between roles and their permitted change types.
"""

# Role to change types mapping
ROLE_PERMISSIONS = {
    'system_admin': ['*'],  # All permissions

    'vendor_admin': [
        'vendor_create',
        'vendor_edit',
        'vendor_delete',
        'vendor_contact_create',
        'vendor_contact_edit',
        'vendor_contact_delete',
        'vendor_address_create',
        'vendor_address_edit',
        'vendor_address_delete',
        'vendor_tag_create',
        'vendor_tag_edit',
        'vendor_tag_delete',
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
        'vendor_create',
        'vendor_edit',
        'vendor_contact_create',
        'vendor_contact_edit',
        'vendor_address_create',
        'vendor_address_edit',
        'vendor_tag_create',
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
