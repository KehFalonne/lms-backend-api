"""Read-side helpers for RBAC."""

from django.contrib.auth import get_user_model

from apps.accounts.models import Role, UserRole

User = get_user_model()


def user_role_codes(user) -> set[str]:
    if not user or not user.is_authenticated:
        return set()
    return set(user.get_role_codes())


def user_permission_codes(user) -> set[str]:
    if not user or not user.is_authenticated:
        return set()
    return set(user.get_permission_codes())


def user_has_global_scope(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.user_roles.filter(scope_type="GLOBAL").exists()


def user_scoped_roles(user):
    return (
        UserRole.objects.filter(user=user)
        .select_related("role", "assigned_by")
        .order_by("-assigned_at")
    )


def role_with_counts(role_id):
    from django.db.models import Count

    return (
        Role.objects.filter(id=role_id)
        .annotate(
            user_count=Count("user_roles", distinct=True),
            permission_count=Count("role_permissions", distinct=True),
        )
        .first()
    )


def roles_with_counts():
    from django.db.models import Count

    return Role.objects.annotate(
        user_count=Count("user_roles", distinct=True),
        permission_count=Count("role_permissions", distinct=True),
    ).order_by("code")
