import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import (
    Permission,
    Role,
    RolePermission,
    UserRole,
)
from apps.audit.models import AuditLog
from apps.audit.services.audit_service import AuditService

User = get_user_model()
pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/audit-logs/"
FACETS_URL = "/api/v1/audit-logs/facets/"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def superuser():
    return User.objects.create_superuser(
        email="root@x.y",
        university_id="GU0001",
        password="p",
        first_name="Root",
        last_name="Admin",
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        email="s@x.y",
        university_id="GU2026001",
        password="p",
        first_name="Sam",
        last_name="Student",
        status="ACTIVE",
    )


@pytest.fixture
def auditor(student):
    """A regular user granted the audit.view permission via a GLOBAL role."""
    perm = Permission.objects.create(
        code="audit.view", name="View audit logs", module="audit"
    )
    role = Role.objects.create(code="AUDITOR", name="Auditor", is_system_role=True)
    RolePermission.objects.create(role=role, permission=perm)
    UserRole.objects.create(user=student, role=role)
    return student


class TestAuditLogListPermissions:
    def test_anonymous_rejected(self, api):
        assert api.get(LIST_URL).status_code in (401, 403)

    def test_user_without_permission_rejected(self, api, student):
        api.force_authenticate(user=student)
        assert api.get(LIST_URL).status_code == 403

    def test_superuser_allowed(self, api, superuser):
        api.force_authenticate(user=superuser)
        assert api.get(LIST_URL).status_code == 200

    def test_permission_holder_allowed(self, api, auditor):
        api.force_authenticate(user=auditor)
        res = api.get(LIST_URL)
        assert res.status_code == 200
        assert res.json()["success"] is True


class TestAuditLogListFilters:
    @pytest.fixture
    def logs(self, superuser):
        AuditService.record(
            action="USER_CREATED",
            entity_type="User",
            entity_id=superuser.id,
            new_values={"email": "a@b.c"},
        )
        AuditService.record(
            action="GRADE_PUBLISHED",
            entity_type="Grade",
            new_values={"score": "88.5"},
        )
        AuditService.record(
            action="USER_DELETED",
            entity_type="User",
            old_values={"email": "old@b.c"},
        )

    def test_filter_by_action(self, api, superuser, logs):
        api.force_authenticate(user=superuser)
        res = api.get(LIST_URL, {"action": "GRADE"})
        data = res.json()["data"]
        assert res.status_code == 200
        assert len(data) == 1
        assert data[0]["action"] == "GRADE_PUBLISHED"

    def test_entity_type_is_case_insensitive(self, api, superuser, logs):
        api.force_authenticate(user=superuser)
        res = api.get(LIST_URL, {"entityType": "grade"})
        data = res.json()["data"]
        assert len(data) == 1
        assert data[0]["entityType"] == "Grade"

    def test_filter_by_actor(self, api, superuser, logs):
        AuditService.record(
            action="AUTH_LOGIN",
            actor=superuser,
            entity_type="User",
            entity_id=superuser.id,
        )
        api.force_authenticate(user=superuser)
        res = api.get(LIST_URL, {"actor": "GU0001"})
        assert all(
            log["actor"] and log["actor"]["universityId"] == "GU0001"
            for log in res.json()["data"]
        )

    def test_date_range_filter(self, api, superuser):
        AuditService.record(action="TEST_OLD", entity_type="X")
        api.force_authenticate(user=superuser)
        res = api.get(
            LIST_URL,
            {"createdFrom": "2999-01-01", "createdTo": "2999-12-31"},
        )
        assert res.json()["data"] == []
        assert res.json()["meta"]["total"] == 0

    def test_invalid_date_rejected(self, api, superuser):
        api.force_authenticate(user=superuser)
        res = api.get(LIST_URL, {"createdFrom": "not-a-date"})
        assert res.status_code == 400

    def test_pagination_meta(self, api, superuser):
        for i in range(5):
            AuditService.record(action=f"BULK_{i}", entity_type="X")
        api.force_authenticate(user=superuser)
        res = api.get(LIST_URL, {"page": 1, "pageSize": 2})
        body = res.json()
        assert len(body["data"]) == 2
        assert body["meta"]["total"] >= 5
        assert body["meta"]["totalPages"] >= 3


class TestAuditLogFacets:
    def test_facets_require_permission(self, api, student):
        api.force_authenticate(user=student)
        assert api.get(FACETS_URL).status_code == 403

    def test_facets_return_distinct_values(self, api, superuser):
        AuditService.record(action="AAA_ONE", entity_type="Foo")
        AuditService.record(action="AAA_ONE", entity_type="Bar")
        AuditService.record(action="BBB_TWO", entity_type="Foo")
        api.force_authenticate(user=superuser)
        res = api.get(FACETS_URL)
        assert res.status_code == 200
        data = res.json()["data"]
        assert "AAA_ONE" in data["actions"]
        assert "BBB_TWO" in data["actions"]
        assert "Foo" in data["entityTypes"]
        assert "Bar" in data["entityTypes"]


class TestAuditLogImmutability:
    def test_update_blocked(self):
        log = AuditService.record(action="X", entity_type="Y")
        log.action = "HACKED"
        with pytest.raises(ValidationError):
            log.save()

    def test_delete_blocked(self):
        log = AuditService.record(action="X", entity_type="Y")
        with pytest.raises(ValidationError):
            log.delete()


class TestAuditServiceRedaction:
    def test_sensitive_keys_redacted(self):
        log = AuditService.record(
            action="TEST",
            entity_type="X",
            new_values={
                "email": "a@b.c",
                "password": "hunter2",
                "nested": {"api_key": "sekret", "ok": 1},
                "items": [{"token": "abc", "v": 2}],
            },
            metadata={"authorization": "Bearer x", "note": "hi"},
        )
        assert log is not None
        assert log.new_values["email"] == "a@b.c"
        assert log.new_values["password"] == "***REDACTED***"
        assert log.new_values["nested"]["api_key"] == "***REDACTED***"
        assert log.new_values["nested"]["ok"] == 1
        assert log.new_values["items"][0]["token"] == "***REDACTED***"
        assert log.metadata["authorization"] == "***REDACTED***"
        assert log.metadata["note"] == "hi"


class TestAuditSignals:
    def test_user_create_is_audited(self):
        before = AuditLog.objects.filter(action="USER_CREATED").count()
        User.objects.create_user(
            email="new@x.y",
            university_id="GU9",
            password="p",
            first_name="N",
            last_name="U",
        )
        assert (
            AuditLog.objects.filter(action="USER_CREATED").count() == before + 1
        )

    def test_user_update_diffs_old_and_new(self):
        user = User.objects.create_user(
            email="chg@x.y",
            university_id="GU10",
            password="p",
            first_name="C",
            last_name="U",
        )
        user.status = "SUSPENDED"
        user.save(update_fields=["status", "updated_at"])
        log = AuditLog.objects.filter(
            action="USER_UPDATED", entity_id=user.id
        ).latest("created_at")
        assert log.old_values["status"] == "ACTIVE" or log.old_values[
            "status"
        ] in ("PENDING", "ACTIVE")
        assert log.new_values["status"] == "SUSPENDED"

    def test_skip_flag_suppresses_signal(self):
        from apps.academics.models import AcademicYear

        import datetime

        year = AcademicYear.objects.create(
            name="2099-2100",
            start_date=datetime.date(2099, 9, 1),
            end_date=datetime.date(2100, 6, 30),
        )
        year._skip_audit_log = True
        year.status = "ACTIVE"
        year.save(update_fields=["status", "updated_at"])
        assert not AuditLog.objects.filter(
            action="ACADEMIC_YEAR_UPDATED", entity_id=year.id
        ).exists()

    def test_generic_crud_coverage(self):
        from apps.courses.models import Course
        from apps.university.models import Department, Faculty

        faculty = Faculty.objects.create(code="TST", name="Test Faculty")
        assert AuditLog.objects.filter(
            action="FACULTY_CREATED", entity_id=faculty.id
        ).exists()

        department = Department.objects.create(
            faculty=faculty, code="TST", name="Test Dept"
        )
        assert AuditLog.objects.filter(
            action="DEPARTMENT_CREATED", entity_id=department.id
        ).exists()

        course = Course.objects.create(
            department=department, code="TST101", title="Test Course"
        )
        assert AuditLog.objects.filter(
            action="COURSE_CREATED", entity_id=course.id
        ).exists()

        course.title = "Renamed"
        course.save(update_fields=["title", "updated_at"])
        update_log = AuditLog.objects.filter(
            action="COURSE_UPDATED", entity_id=course.id
        ).latest("created_at")
        assert update_log.old_values["title"] == "Test Course"
        assert update_log.new_values["title"] == "Renamed"
