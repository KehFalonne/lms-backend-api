import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.analytics.models import LearningEvent, StudentCourseProgress
from apps.audit.models import AuditLog
from apps.audit.services.audit_service import AuditService

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def student():
    return User.objects.create_user(
        email="s@x.y",
        university_id="GU1",
        password="p",
        first_name="S",
        last_name="S",
        status="ACTIVE",
    )


@pytest.fixture
def admin():
    return User.objects.create_superuser(
        email="a@x.y",
        university_id="GU0001",
        password="p",
        first_name="A",
        last_name="B",
    )


class TestLearningEvents:
    def test_record_event(self, api, student):
        api.force_authenticate(user=student)
        res = api.post(
            "/api/v1/learning-events/",
            {
                "eventType": "COURSE_VIEWED",
                "entityType": "course",
                "metadata": {"x": 1},
            },
            format="json",
        )
        assert res.status_code == 201
        assert LearningEvent.objects.filter(
            student=student, event_type="COURSE_VIEWED"
        ).exists()


class TestAuditLog:
    def test_redacts_sensitive_keys_recursively(self):
        log = AuditService.record(
            action="USER_CREATED",
            new_values={
                "email": "x@y.z",
                "password": "secret",
                "nested": [
                    {"accessToken": "access-secret", "refresh_token": "refresh-secret"}
                ],
            },
            metadata={"Authorization": "Bearer secret", "client_secret": "secret"},
        )
        assert log is not None
        assert log.new_values["password"] == "***REDACTED***"
        assert log.new_values["email"] == "x@y.z"
        assert log.new_values["nested"][0]["accessToken"] == "***REDACTED***"
        assert log.new_values["nested"][0]["refresh_token"] == "***REDACTED***"
        assert log.metadata["Authorization"] == "***REDACTED***"
        assert log.metadata["client_secret"] == "***REDACTED***"

    def test_captures_request_actor_and_client_metadata(self, admin):
        from rest_framework.test import APIRequestFactory, force_authenticate

        request = APIRequestFactory().post("/", HTTP_USER_AGENT="audit-test")
        request.META["REMOTE_ADDR"] = "192.0.2.10"
        force_authenticate(request, user=admin)
        log = AuditService.record(action="TEST_REQUEST", request=request)

        assert log.actor == admin
        assert log.ip_address == "192.0.2.10"
        assert log.user_agent == "audit-test"

    def test_list_requires_audit_permission(self, api, student):
        api.force_authenticate(user=student)
        res = api.get("/api/v1/audit-logs/")
        assert res.status_code == 403

    def test_invalid_audit_filters_return_400(self, api, admin):
        api.force_authenticate(user=admin)
        assert api.get("/api/v1/audit-logs/?actorId=invalid").status_code == 400
        assert api.get("/api/v1/audit-logs/?createdFrom=invalid").status_code == 400

    def test_list_and_filters(self, api, admin):
        matching = AuditService.record(
            action="TEST_ACTION", entity_type="test", entity_id=None
        )
        AuditService.record(action="OTHER_ACTION", entity_type="other", entity_id=None)
        api.force_authenticate(user=admin)
        res = api.get(
            "/api/v1/audit-logs/",
            {"action": "TEST", "entityType": "test", "page": 1, "pageSize": 1},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["meta"]["total"] == 1
        assert body["meta"]["pageSize"] == 1
        assert body["data"][0]["id"] == str(matching.id)

    def test_audit_permission_can_view_logs(self, api):
        from apps.accounts.models import (
            Permission,
            Role,
            RolePermission,
            RoleScope,
            UserRole,
        )

        user = User.objects.create_user(
            email="auditor@example.com",
            university_id="AUDIT1",
            password="StrongPass123!",
            first_name="Audit",
            last_name="User",
            status="ACTIVE",
        )
        role, _ = Role.objects.get_or_create(code="AUDITOR", defaults={"name": "Auditor"})
        permission, _ = Permission.objects.get_or_create(
            code="audit.view", defaults={"name": "View audit logs", "module": "audit"}
        )
        RolePermission.objects.get_or_create(role=role, permission=permission)
        UserRole.objects.create(user=user, role=role, scope_type=RoleScope.GLOBAL)
        api.force_authenticate(user=user)

        assert api.get("/api/v1/audit-logs/").status_code == 200


class TestDashboards:
    def test_student_dashboard(self, api, student):
        api.force_authenticate(user=student)
        res = api.get("/api/v1/dashboards/student/")
        assert res.status_code == 200
        assert "courses" in res.json()["data"]

    def test_lecturer_dashboard(self, api, student):
        api.force_authenticate(user=student)
        res = api.get("/api/v1/dashboards/lecturer/")
        assert res.status_code == 200
        assert "stats" in res.json()["data"]

    def test_admin_dashboard_requires_admin(self, api, student):
        api.force_authenticate(user=student)
        res = api.get("/api/v1/dashboards/admin/")
        assert res.status_code == 403

    def test_admin_dashboard(self, api, admin):
        api.force_authenticate(user=admin)
        res = api.get("/api/v1/dashboards/admin/")
        assert res.status_code == 200
        assert "totals" in res.json()["data"]
