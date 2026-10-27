import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import Permission, Role, RolePermission, UserRole

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def rbac():
    """Seed minimal RBAC for tests."""
    perm_a = Permission.objects.create(
        code="courses.view", name="View", module="courses"
    )
    perm_b = Permission.objects.create(
        code="courses.create", name="Create", module="courses"
    )
    role_lecturer = Role.objects.create(
        code="LECTURER", name="Lecturer", is_system_role=True
    )
    RolePermission.objects.create(role=role_lecturer, permission=perm_a)
    RolePermission.objects.create(role=role_lecturer, permission=perm_b)
    return {"perms": [perm_a, perm_b], "role": role_lecturer}


class TestUserRoleHelpers:
    def test_get_role_codes(self, rbac):
        user = User.objects.create_user(
            email="x@x.y",
            university_id="GU1",
            password="p",
            first_name="A",
            last_name="B",
        )
        UserRole.objects.create(user=user, role=rbac["role"], scope_type="GLOBAL")
        assert user.get_role_codes() == ["LECTURER"]

    def test_get_permission_codes(self, rbac):
        user = User.objects.create_user(
            email="x@x.y",
            university_id="GU1",
            password="p",
            first_name="A",
            last_name="B",
        )
        UserRole.objects.create(user=user, role=rbac["role"], scope_type="GLOBAL")
        codes = set(user.get_permission_codes())
        assert codes == {"courses.view", "courses.create"}

    def test_has_permission_code(self, rbac):
        user = User.objects.create_user(
            email="x@x.y",
            university_id="GU1",
            password="p",
            first_name="A",
            last_name="B",
        )
        UserRole.objects.create(user=user, role=rbac["role"], scope_type="GLOBAL")
        assert user.has_permission_code("courses.view")
        assert not user.has_permission_code("users.delete")

    def test_superuser_has_all(self, rbac):
        su = User.objects.create_superuser(
            email="root@x.y",
            university_id="GU0001",
            password="p",
            first_name="A",
            last_name="B",
        )
        assert su.has_permission_code("anything.at.all")
        assert su.has_role("NOBODY")
