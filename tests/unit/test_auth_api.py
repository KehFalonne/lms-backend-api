import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import StudentProfile, StaffProfile, UserStatus

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def student():
    from apps.accounts.models import Role, RoleScope, UserRole

    u = User.objects.create_user(
        email="john@graciousuniversity.edu",
        university_id="GU2026001",
        password="Student1234!",
        first_name="John",
        last_name="Doe",
        status=UserStatus.ACTIVE,
    )
    StudentProfile.objects.create(
        user=u,
        matricule_number="GU-2026-001234",
        current_level=400,
        admission_year=2026,
    )

    # Assign the STUDENT role — RBAC is authoritative from Sprint 3 onward.
    student_role, _ = Role.objects.get_or_create(
        code="STUDENT",
        defaults={"name": "Student", "is_system_role": True},
    )
    UserRole.objects.create(
        user=u,
        role=student_role,
        scope_type=RoleScope.GLOBAL,
    )
    return u


@pytest.fixture
def lecturer():
    u = User.objects.create_user(
        email="jane@graciousuniversity.edu",
        university_id="GU0002",
        password="Lecturer1234!",
        first_name="Jane",
        last_name="Smith",
        status=UserStatus.ACTIVE,
    )
    StaffProfile.objects.create(user=u, staff_number="GU-STAFF-0001")
    return u


class TestLogin:
    url = "/api/v1/auth/login/"

    def test_login_with_university_id(self, api, student):
        res = api.post(
            self.url,
            {"identifier": "GU2026001", "password": "Student1234!"},
            format="json",
        )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["message"] == "Login successful"
        assert body["data"]["access"]
        assert body["data"]["refresh"]
        assert body["data"]["user"]["universityId"] == "GU2026001"
        assert body["data"]["user"]["firstName"] == "John"
        assert "STUDENT" in body["data"]["user"]["roles"]

    def test_login_with_email(self, api, student):
        res = api.post(
            self.url,
            {"identifier": "john@graciousuniversity.edu", "password": "Student1234!"},
            format="json",
        )
        assert res.status_code == 200

    def test_login_with_matricule(self, api, student):
        res = api.post(
            self.url,
            {"identifier": "GU-2026-001234", "password": "Student1234!"},
            format="json",
        )
        assert res.status_code == 200

    def test_login_wrong_password(self, api, student):
        res = api.post(
            self.url, {"identifier": "GU2026001", "password": "nope"}, format="json"
        )
        assert res.status_code == 400
        body = res.json()
        assert body["success"] is False
        assert body["statusCode"] == 400
        assert "Invalid credentials" in body["message"]

    def test_login_unknown_identifier(self, api):
        res = api.post(self.url, {"identifier": "NOPE", "password": "x"}, format="json")
        assert res.status_code == 400

    def test_login_suspended(self, api, student):
        student.status = UserStatus.SUSPENDED
        student.save()
        res = api.post(
            self.url,
            {"identifier": "GU2026001", "password": "Student1234!"},
            format="json",
        )
        assert res.status_code == 400
        assert "suspended" in res.json()["message"].lower()

    def test_login_response_is_camel_case(self, api, student):
        res = api.post(
            self.url,
            {"identifier": "GU2026001", "password": "Student1234!"},
            format="json",
        )
        assert "universityId" in res.json()["data"]["user"]
        assert "university_id" not in res.json()["data"]["user"]


class TestMe:
    url = "/api/v1/auth/me/"

    def test_me_requires_auth(self, api):
        res = api.get(self.url)
        assert res.status_code == 401

    def test_me_returns_profile(self, api, student):
        login = api.post(
            "/api/v1/auth/login/",
            {"identifier": "GU2026001", "password": "Student1234!"},
            format="json",
        )
        token = login.json()["data"]["access"]
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res = api.get(self.url)
        assert res.status_code == 200
        body = res.json()
        assert body["data"]["universityId"] == "GU2026001"
        assert "STUDENT" in body["data"]["roles"]
        assert body["data"]["studentProfile"]["matriculeNumber"] == "GU-2026-001234"


class TestLogout:
    def test_logout_blacklists_refresh(self, api, student):
        login = api.post(
            "/api/v1/auth/login/",
            {"identifier": "GU2026001", "password": "Student1234!"},
            format="json",
        ).json()
        access, refresh = login["data"]["access"], login["data"]["refresh"]
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        res = api.post("/api/v1/auth/logout/", {"refresh": refresh}, format="json")
        assert res.status_code == 200

        # Refresh should now fail
        api.credentials()
        res = api.post(
            "/api/v1/auth/token/refresh/", {"refresh": refresh}, format="json"
        )
        assert res.status_code == 401


class TestChangePassword:
    def test_change_password_success(self, api, student):
        login = api.post(
            "/api/v1/auth/login/",
            {"identifier": "GU2026001", "password": "Student1234!"},
            format="json",
        ).json()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {login['data']['access']}")

        res = api.post(
            "/api/v1/auth/change-password/",
            {"currentPassword": "Student1234!", "newPassword": "NewPass5678!"},
            format="json",
        )
        assert res.status_code == 200

        # Verify new password works
        api.credentials()
        res = api.post(
            "/api/v1/auth/login/",
            {"identifier": "GU2026001", "password": "NewPass5678!"},
            format="json",
        )
        assert res.status_code == 200

    def test_change_password_wrong_current(self, api, student):
        login = api.post(
            "/api/v1/auth/login/",
            {"identifier": "GU2026001", "password": "Student1234!"},
            format="json",
        ).json()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {login['data']['access']}")
        res = api.post(
            "/api/v1/auth/change-password/",
            {"currentPassword": "wrong", "newPassword": "NewPass5678!"},
            format="json",
        )
        assert res.status_code == 400


class TestForgotResetPassword:
    def test_forgot_password_never_leaks_user(self, api, student):
        res = api.post(
            "/api/v1/auth/forgot-password/",
            {"email": "john@graciousuniversity.edu"},
            format="json",
        )
        assert res.status_code == 200
        # Same message for unknown email
        res2 = api.post(
            "/api/v1/auth/forgot-password/",
            {"email": "nobody@example.com"},
            format="json",
        )
        assert res2.status_code == 200
        assert res.json()["message"] == res2.json()["message"]


class TestUserCRUD:
    url = "/api/v1/users/"

    def test_list_requires_admin(self, api, student):
        login = api.post(
            "/api/v1/auth/login/",
            {"identifier": "GU2026001", "password": "Student1234!"},
            format="json",
        ).json()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {login['data']['access']}")
        res = api.get(self.url)
        assert res.status_code == 403

    def test_admin_can_list_users(self, api, superuser, student):
        api.force_authenticate(user=superuser)
        res = api.get(self.url)
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert "meta" in body
        assert body["meta"]["total"] >= 2

    def test_admin_can_create_user(self, api, superuser):
        api.force_authenticate(user=superuser)
        res = api.post(
            self.url,
            {
                "email": "new@graciousuniversity.edu",
                "universityId": "GU2026900",
                "password": "NewUser1234!",
                "firstName": "New",
                "lastName": "User",
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"]["universityId"] == "GU2026900"

    def test_admin_can_activate_deactivate(self, api, superuser, student):
        api.force_authenticate(user=superuser)
        res = api.post(f"{self.url}{student.id}/deactivate/")
        assert res.status_code == 200
        student.refresh_from_db()
        assert student.is_active is False

        res = api.post(f"{self.url}{student.id}/activate/")
        assert res.status_code == 200
        student.refresh_from_db()
        assert student.is_active is True

    def test_search_filter(self, api, superuser, student):
        api.force_authenticate(user=superuser)
        res = api.get(f"{self.url}?search=John")
        assert res.status_code == 200
        assert len(res.json()["data"]) >= 1
