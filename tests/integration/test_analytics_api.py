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
    def test_redacts_sensitive_keys(self):
        log = AuditService.record(
            action="USER_CREATED",
            new_values={"email": "x@y.z", "password": "secret"},
        )
        assert log is not None
        assert log.new_values["password"] == "***REDACTED***"
        assert log.new_values["email"] == "x@y.z"

    def test_list_requires_admin(self, api, student):
        api.force_authenticate(user=student)
        res = api.get("/api/v1/audit-logs/")
        assert res.status_code == 403

    def test_list(self, api, admin):
        AuditService.record(action="TEST_ACTION", entity_type="test", entity_id=None)
        api.force_authenticate(user=admin)
        res = api.get("/api/v1/audit-logs/")
        assert res.status_code == 200
        assert res.json()["success"] is True


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
