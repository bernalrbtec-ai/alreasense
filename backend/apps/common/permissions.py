"""
Custom permissions for multi-tenant access control.
"""

from rest_framework import permissions


class IsTenantMember(permissions.BasePermission):
    """
    Permission to ensure user belongs to the tenant.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            hasattr(request.user, 'tenant')
        )


class IsAdminUser(permissions.BasePermission):
    """
    Permission to ensure user is admin.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.is_admin
        )


class IsOperatorOrAdmin(permissions.BasePermission):
    """
    Permission to ensure user is operator or admin.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_operator or request.user.is_admin)
        )


class IsTenantOwner(permissions.BasePermission):
    """
    Permission to ensure user owns the tenant resource.
    """
    
    def has_object_permission(self, request, view, obj):
        # Check if object has tenant attribute
        if hasattr(obj, 'tenant'):
            return obj.tenant == request.user.tenant
        
        # Check if object is the tenant itself
        if hasattr(obj, 'id'):
            return obj.id == request.user.tenant.id
        
        return False
