import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, Semester
from apps.accounts.models import Role, RoleScope, StudentProfile, UserRole
from apps.courses.models import Course, CourseInstructor, CourseOffering, TeachingRole
from apps.university.models import Department, Faculty, Programme

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin():
    return User.objects.create_superuser(
        email="root@x.y",
        university_id="GU0001",
        password="p",
        first_name="A",
        last_name="B",
    )


@pytest.fixture
def lecturer():
    return User.objects.create_user(
        email="lec@x.y",
        university_id="GU0002",
        password="p",
        first_name="Jane",
        last_name="Lecturer",
        status="ACTIVE",
    )


@pytest.fixture
def student():
    u = User.objects.create_user(
        email="stu@x.y",
        university_id="GU3",
        password="p",
        first_name="John",
        last_name="Student",
        status="ACTIVE",
    )
    StudentProfile.objects.create(
        user=u,
        matricule_number="GU-2026-009999",
        current_level=100,
        admission_year=2026,
    )
    return u


@pytest.fixture
def offering():
    f = Faculty.objects.create(code="FOC", name="Computing")
    d = Department.objects.create(faculty=f, code="CS", name="CS")
    p = Programme.objects.create(department=d, code="BSC-CS", name="BSc CS")
    c = Course.objects.create(
        department=d, code="CSC101", title="Intro", credits=3, level=100
    )
    y = AcademicYear.objects.create(
        name="2026/2027", start_date="2026-09-01", end_date="2027-07-31"
    )
    s = Semester.objects.create(
        academic_year=y,
        name="Semester 1",
        code="S1",
        sequence=1,
        start_date="2026-09-01",
        end_date="2027-01-31",
    )
    return CourseOffering.objects.create(
        course=c, semester=s, programme=p, section="A", capacity=50
    )


def _assign_payload(user, role="INSTRUCTOR"):
    return {
        "userId": str(user.id),
        "teachingRole": role,
        "canGrade": True,
        "canManageContent": True,
    }


class TestInstructorAssignmentRestrictions:
    def test_student_cannot_be_assigned_teaching_role(self, api, admin, student, offering):
        api.force_authenticate(user=admin)
        res = api.post(
            f"/api/v1/course-offerings/{offering.id}/instructors/",
            _assign_payload(student),
            format="json",
        )
        assert res.status_code == 400
        assert not CourseInstructor.objects.filter(
            course_offering=offering, user=student
        ).exists()

    def test_lecturer_can_still_be_assigned(self, api, admin, lecturer, offering):
        api.force_authenticate(user=admin)
        res = api.post(
            f"/api/v1/course-offerings/{offering.id}/instructors/",
            _assign_payload(lecturer),
            format="json",
        )
        assert res.status_code == 201

    def test_direct_create_is_blocked_by_model(self, student, offering):
        with pytest.raises(ValidationError):
            CourseInstructor.objects.create(
                course_offering=offering,
                user=student,
                teaching_role=TeachingRole.INSTRUCTOR,
            )

    def test_staff_user_without_student_profile_passes_model(self, lecturer, offering):
        CourseInstructor.objects.create(
            course_offering=offering,
            user=lecturer,
            teaching_role=TeachingRole.INSTRUCTOR,
        )
        assert CourseInstructor.objects.filter(user=lecturer).exists()


class TestRbacTeachingRoleRestrictions:
    def test_student_cannot_get_lecturer_role(self, api, admin, student):
        api.force_authenticate(user=admin)
        role = Role.objects.create(
            code="LECTURER", name="Lecturer", is_system_role=True
        )
        res = api.post(
            f"/api/v1/users/{student.id}/assign-role/",
            {"roleId": str(role.id), "scopeType": "GLOBAL"},
            format="json",
        )
        assert res.status_code == 400
        assert not UserRole.objects.filter(user=student, role=role).exists()

    def test_student_can_get_non_teaching_role(self, api, admin, student):
        api.force_authenticate(user=admin)
        role = Role.objects.create(code="STUDENT", name="Student", is_system_role=True)
        res = api.post(
            f"/api/v1/users/{student.id}/assign-role/",
            {"roleId": str(role.id), "scopeType": "GLOBAL"},
            format="json",
        )
        assert res.status_code == 201

    def test_lecturer_can_get_lecturer_role(self, api, admin, lecturer):
        api.force_authenticate(user=admin)
        role = Role.objects.create(
            code="LECTURER", name="Lecturer", is_system_role=True
        )
        res = api.post(
            f"/api/v1/users/{lecturer.id}/assign-role/",
            {"roleId": str(role.id), "scopeType": "GLOBAL"},
            format="json",
        )
        assert res.status_code == 201


class TestProfileConversionRestrictions:
    def test_instructor_cannot_become_student_profile(self, api, admin, lecturer, offering):
        api.force_authenticate(user=admin)
        CourseInstructor.objects.create(
            course_offering=offering,
            user=lecturer,
            teaching_role=TeachingRole.INSTRUCTOR,
        )
        res = api.patch(
            f"/api/v1/users/{lecturer.id}/",
            {"profileType": "student", "matriculeNumber": "GU-2026-010000"},
            format="json",
        )
        assert res.status_code == 400
        assert not StudentProfile.objects.filter(user=lecturer).exists()

    def test_lecturer_role_holder_cannot_become_student_profile(self, api, admin, lecturer):
        api.force_authenticate(user=admin)
        role = Role.objects.create(
            code="LECTURER", name="Lecturer", is_system_role=True
        )
        UserRole.objects.create(
            user=lecturer, role=role, scope_type=RoleScope.GLOBAL, assigned_by=admin
        )
        res = api.patch(
            f"/api/v1/users/{lecturer.id}/",
            {"profileType": "student", "matriculeNumber": "GU-2026-010001"},
            format="json",
        )
        assert res.status_code == 400
        assert not StudentProfile.objects.filter(user=lecturer).exists()
