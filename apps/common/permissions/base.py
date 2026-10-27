"""
Base DRF permission classes.

Concrete scope-aware permissions (faculty / department / course) are added in
Sprint 3 once RBAC models exist.
"""

from rest_framework.permissions import BasePermission


class IsAuthenticatedAndActive(BasePermission):
    """Require authentication AND an active account."""

    message = "Your account is not active."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.is_active
        )


class HasRole(BasePermission):
    """
    Require at least one of the roles named in `view.required_roles`.

    Roles are read from `request.user.role_codes` which is populated in
    Sprint 3.
    """

    def has_permission(self, request, view):
        required = getattr(view, "required_roles", None)
        if not required:
            return True
        user_roles = set(getattr(request.user, "role_codes", []) or [])
        return bool(user_roles & set(required))


class HasPermissionCode(BasePermission):
    """
    Require at least one of the permission codes in `view.required_permissions`.

    Permission codes are read from `request.user.permission_codes` which is
    populated in Sprint 3.
    """

    def has_permission(self, request, view):
        required = getattr(view, "required_permissions", None)
        if not required:
            return True
        user_perms = set(getattr(request.user, "permission_codes", []) or [])
        return bool(user_perms & set(required))
