"""RBAC decorator and permission enforcement utilities."""

from __future__ import annotations

import functools
from typing import Any, Callable

from django.http import HttpRequest, HttpResponse

from apps.core.contracts.identity import resolve_identity_context
from apps.core.responses import api_error
from apps.core.services.permission_registry import authorize_mutation, permission_for_read
from apps.identity.services import build_policy_snapshot, sync_user_directory


def require_permission(permission: str | None = None, method: str | None = None, path_template: str | None = None):
    """
    Decorator to enforce role-based access control on a view.
    
    Usage:
        @require_permission("vendor.write")
        def my_view(request):
            ...
        
        @require_permission(method="POST", path_template="/api/v1/vendors")
        def endpoint(request):
            ...
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            # Resolve identity and build policy snapshot
            identity = resolve_identity_context(request)
            sync_user_directory(identity)
            snapshot = build_policy_snapshot(identity)
            
            # Determine the permission to check
            perm_to_check = permission
            
            # If method/path_template provided, look up the permission
            if not perm_to_check and method and path_template:
                try:
                    # Try mutation permission first
                    perm_to_check = permission_for_read(method, path_template)
                except KeyError:
                    try:
                        # Fall back to mutation permission
                        from apps.core.services.permission_registry import permission_for_mutation
                        perm_to_check = permission_for_mutation(method, path_template)
                    except KeyError:
                        pass
            
            if not perm_to_check:
                # If no permission specified, deny access
                return api_error(
                    request,
                    code="permission_not_configured",
                    message="Permission check not configured for this endpoint",
                    status=500,
                )
            
            # Check permission using policy engine
            from apps.core.services.policy_engine import PolicyEngine
            decision = PolicyEngine.decide(snapshot, perm_to_check)
            
            if not decision.allowed:
                return api_error(
                    request,
                    code="forbidden",
                    message=f"Missing permission: {perm_to_check}",
                    status=403,
                )
            
            # Permission granted, call the view
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator


def require_any_permission(*permissions: str):
    """
    Decorator to enforce that user has ANY of the specified permissions.
    
    Usage:
        @require_any_permission("vendor.write", "admin.all")
        def my_view(request):
            ...
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            identity = resolve_identity_context(request)
            sync_user_directory(identity)
            snapshot = build_policy_snapshot(identity)
            from apps.core.services.policy_engine import PolicyEngine
            
            # Check if user has ANY of the permissions
            for perm in permissions:
                decision = PolicyEngine.decide(snapshot, perm)
                if decision.allowed:
                    return view_func(request, *args, **kwargs)
            
            # No permission granted
            perm_list = ", ".join(permissions)
            return api_error(
                request,
                code="forbidden",
                message=f"Missing one of required permissions: {perm_list}",
                status=403,
            )
        
        return wrapper
    
    return decorator


def require_all_permissions(*permissions: str):
    """
    Decorator to enforce that user has ALL of the specified permissions.
    
    Usage:
        @require_all_permissions("vendor.write", "audit.log")
        def my_view(request):
            ...
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            identity = resolve_identity_context(request)
            sync_user_directory(identity)
            snapshot = build_policy_snapshot(identity)
            from apps.core.services.policy_engine import PolicyEngine
            
            # Check if user has ALL permissions
            for perm in permissions:
                decision = PolicyEngine.decide(snapshot, perm)
                if not decision.allowed:
                    return api_error(
                        request,
                        code="forbidden",
                        message=f"Missing required permission: {perm}",
                        status=403,
                    )
            
            # All permissions granted
            return view_func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator
