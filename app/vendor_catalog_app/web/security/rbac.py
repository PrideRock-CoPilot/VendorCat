"""
RBAC (Role-Based Access Control) Security Module

Provides decorators and utilities for enforcing permission checks on API endpoints.
"""

from collections.abc import Callable
from functools import wraps

from fastapi import HTTPException, Request


def require_permission(change_type: str) -> Callable:
    """
    Decorator to enforce permission checks on API endpoints.
    
    Usage:
        @router.post("/vendor")
        @require_permission("vendor_create")
        async def create_vendor(request: Request):
            # Handler code - permission already checked
            ...
    
    Args:
        change_type: The permission required (e.g., "vendor_create", "vendor_edit")
    
    Raises:
        HTTPException: 403 if user lacks required permission
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request and 'request' in kwargs:
                request = kwargs['request']

            if not request:
                raise HTTPException(
                    status_code=500,
                    detail="Request object not found - cannot verify permissions"
                )

            # Get user from request state (set by middleware)
            user = getattr(request.state, 'user', None)
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="User not authenticated"
                )

            # Check permission
            if not user.can_apply_change(change_type):
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions: {change_type} required"
                )

            # Permission check passed, execute handler
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def check_org_scope(user, entity_org_id: int) -> None:
    """
    Verify user can access entity from their organization.
    
    Usage:
        vendor = repo.get_vendor_by_id(vendor_id)
        check_org_scope(request.state.user, vendor.organization_id)
    
    Args:
        user: UserContext object from request.state.user
        entity_org_id: Organization ID of the entity being accessed
    
    Raises:
        HTTPException: 403 if user org doesn't match entity org (unless system_admin)
    """
    # system_admin can access all orgs
    if user.role == 'system_admin':
        return

    # Check org match
    if user.organization_id != entity_org_id:
        raise HTTPException(
            status_code=403,
            detail="Entity belongs to different organization"
        )


def require_field_permission(user, field_name: str, permission_map: dict) -> None:
    """
    Check permission for field-level access (e.g., financial fields).
    
    Usage:
        permission_map = {
            'payment_terms': 'vendor_edit_financial',
            'tax_id': 'vendor_view_financial'
        }
        if 'payment_terms' in form_data:
            require_field_permission(user, 'payment_terms', permission_map)
    
    Args:
        user: UserContext object
        field_name: Name of field being accessed
        permission_map: Dict mapping field names to required permissions
    
    Raises:
        HTTPException: 403 if user lacks field permission
    """
    required_permission = permission_map.get(field_name)
    if required_permission and not user.can_apply_change(required_permission):
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions to access field: {field_name}"
        )
