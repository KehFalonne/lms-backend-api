"""
RBAC business logic.

Views stay thin. All state-changing operations on roles, permissions, and
user-role assignments go through here.
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from apps.accounts.models import (
    Permission,
    Role,
    RolePermission,
    RoleScope,
    UserRole,
)

User = get_user_model()


class RBACError(Exception):
    def __init__(self, message: str, code: str = "rbac_error"):
        super().__init__(message)
        self.code = code


class RBACService:

    # ── Roles ────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def create_role(*, code: str, name: str, description: str = "") -> Role:
        code = code.strip().upper()
        if not code:
            raise RBACError("Role code is required.", code="invalid_code")
        if Role.objects.filter(code=code).exists():
            raise RBACError(f"Role '{code}' already exists.", code="duplicate_code")
        try:
            return Role.objects.create(code=code, name=name, description=description)
        except IntegrityError:
            raise RBACError("Role could not be created.", code="integrity_error")

    @staticmethod
    @transaction.atomic
    def update_role(*, role: Role, **fields) -> Role:
        allowed = {"name", "description"}
        for k, v in fields.items():
            if k in allowed:
                setattr(role, k, v)
        role.save()
        return role

    @staticmethod
    @transaction.atomic
    def delete_role(*, role: Role) -> None:
        if role.is_system_role:
            raise RBACError("System roles cannot be deleted.", code="system_role")
        role.delete()

    @staticmethod
    @transaction.atomic
    def set_role_permissions(*, role: Role, permission_ids: list) -> Role:
        """
        Replace the role's permission set with `permission_ids`.
        Idempotent — safe to call with the same list twice.
        """
        permissions = Permission.objects.filter(id__in=permission_ids)
        found_ids = {p.id for p in permissions}
        missing = set(permission_ids) - found_ids
        if missing:
            raise RBACError(
                f"Unknown permission IDs: {', '.join(str(i) for i in missing)}",
                code="unknown_permission",
            )

        RolePermission.objects.filter(role=role).exclude(
            permission_id__in=permission_ids
        ).delete()

        existing = set(
            RolePermission.objects.filter(role=role).values_list(
                "permission_id", flat=True
            )
        )
        to_create = [
            RolePermission(role=role, permission=p)
            for p in permissions
            if p.id not in existing
        ]
        RolePermission.objects.bulk_create(to_create)
        return role

    # ── User-role assignments ────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def assign_role(
        *,
        user,
        role_id,
        scope_type: str = RoleScope.GLOBAL,
        faculty_id=None,
        department_id=None,
        course_offering_id=None,
        assigned_by=None,
    ) -> UserRole:
        try:
            role = Role.objects.get(pk=role_id)
        except Role.DoesNotExist:
            raise RBACError("Role not found.", code="role_not_found")

        assignment = UserRole(
            user=user,
            role=role,
            scope_type=scope_type,
            faculty_id=faculty_id,
            department_id=department_id,
            course_offering_id=course_offering_id,
            assigned_by=assigned_by,
        )

        try:
            assignment.full_clean()
        except DjangoValidationError as exc:
            raise RBACError(str(exc.message_dict), code="validation_error")

        try:
            assignment.save()
        except IntegrityError:
            raise RBACError(
                "This role is already assigned with the same scope.",
                code="duplicate_assignment",
            )

        # Invalidate cached role list on the user instance
        if hasattr(user, "_role_codes_cache"):
            del user._role_codes_cache
        if hasattr(user, "_permission_codes_cache"):
            del user._permission_codes_cache

        return assignment

    @staticmethod
    @transaction.atomic
    def revoke_role(*, user, assignment_id) -> None:
        try:
            assignment = UserRole.objects.get(pk=assignment_id, user=user)
        except UserRole.DoesNotExist:
            raise RBACError("Assignment not found.", code="assignment_not_found")
        assignment.delete()

        if hasattr(user, "_role_codes_cache"):
            del user._role_codes_cache
        if hasattr(user, "_permission_codes_cache"):
            del user._permission_codes_cache
