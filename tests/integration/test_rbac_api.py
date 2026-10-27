import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import (
    Permission,
    Role,
    RolePermission,
    RoleScope,
    UserRole,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def superuser():
    return User.objects.create_superuser(
        email="root@x.y",
        university_id="GU0001",
        password="p",
        first_name="A",
        last_name="B",
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        email="s@x.y",
        university_id="GU2",
        password="p",
        first_name="A",
        last_name="B",
        status="ACTIVE",
    )


@pytest.fixture
def seeded_roles():
    student_role = Role.objects.create(
        code="STUDENT", name="Student", is_system_role=True
    )
    lecturer_role = Role.objects.create(
        code="LECTURER", name="Lecturer", is_system_role=True
    )
    Permission.objects.create(code="courses.view", name="View", module="courses")
    Permission.objects.create(code="grades.manage", name="Grade", module="grades")
    return {"student": student_role, "lecturer": lecturer_role}


class TestRoleCRUD:
    url = "/api/v1/roles/"

    def test_requires_admin(self, api, student):
        api.force_authenticate(user=student)
        assert api.get(self.url).status_code == 403

    def test_list(self, api, superuser, seeded_roles):
        api.force_authenticate(user=superuser)
        res = api.get(self.url)
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert len(res.json()["data"]) == 2

    def test_create(self, api, superuser):
        api.force_authenticate(user=superuser)
        res = api.post(self.url, {"code": "dean", "name": "Dean"}, format="json")
        assert res.status_code == 201
        # code auto-uppercased
        assert res.json()["data"]["code"] == "DEAN"

    def test_delete_system_role_blocked(self, api, superuser, seeded_roles):
        api.force_authenticate(user=superuser)
        role_id = seeded_roles["student"].id
        res = api.delete(f"{self.url}{role_id}/")
        assert res.status_code == 400


class TestRolePermissions:
    def test_set_permissions(self, api, superuser, seeded_roles):
        api.force_authenticate(user=superuser)
        role = seeded_roles["lecturer"]
        perms = list(Permission.objects.all())
        res = api.put(
            f"/api/v1/roles/{role.id}/permissions/",
            {"permissionIds": [str(p.id) for p in perms]},
            format="json",
        )
        assert res.status_code == 200
        assert len(res.json()["data"]) == len(perms)

    def test_get_permissions(self, api, superuser, seeded_roles):
        api.force_authenticate(user=superuser)
        role = seeded_roles["lecturer"]
        p = Permission.objects.first()
        RolePermission.objects.create(role=role, permission=p)
        res = api.get(f"/api/v1/roles/{role.id}/permissions/")
        assert res.status_code == 200
        assert len(res.json()["data"]) == 1


class TestAssignRole:
    def test_assign_global(self, api, superuser, student, seeded_roles):
        api.force_authenticate(user=superuser)
        res = api.post(
            f"/api/v1/users/{student.id}/assign-role/",
            {"roleId": str(seeded_roles["student"].id), "scopeType": "GLOBAL"},
            format="json",
        )
        assert res.status_code == 201
        student.refresh_from_db()
        assert "STUDENT" in student.get_role_codes()

    def test_assign_course_scope_requires_id(
        self, api, superuser, student, seeded_roles
    ):
        api.force_authenticate(user=superuser)
        res = api.post(
            f"/api/v1/users/{student.id}/assign-role/",
            {"roleId": str(seeded_roles["lecturer"].id), "scopeType": "COURSE"},
            format="json",
        )
        assert res.status_code == 400
        assert "courseofferingid" in str(res.json()["errors"]).lower()

    def test_revoke_role(self, api, superuser, student, seeded_roles):
        api.force_authenticate(user=superuser)
        assignment = UserRole.objects.create(
            user=student, role=seeded_roles["student"], scope_type=RoleScope.GLOBAL
        )
        res = api.delete(f"/api/v1/users/{student.id}/roles/{assignment.id}/")
        assert res.status_code == 200
        assert not UserRole.objects.filter(id=assignment.id).exists()
