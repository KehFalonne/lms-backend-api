import pytest

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from apps.accounts.models import StudentProfile
from apps.academics.models import AcademicYear, Semester
from apps.courses.models import (
    Course,
    CourseEnrollment,
    CourseInstructor,
    CourseOffering,
    EnrollmentStatus,
    OfferingStatus,
    TeachingRole,
)
from apps.notifications.models import Notification
from apps.university.models import Department, Faculty, Programme

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin():
    return User.objects.create_user(
        email="admin@x.y",
        university_id="GU1",
        password="p",
        first_name="A",
        last_name="D",
        status="ACTIVE",
        is_staff=True,
    )


@pytest.fixture
def lecturer():
    return User.objects.create_user(
        email="lec@x.y",
        university_id="GU2",
        password="p",
        first_name="J",
        last_name="L",
        status="ACTIVE",
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        email="stu@x.y",
        university_id="GU3",
        password="p",
        first_name="S",
        last_name="S",
        status="ACTIVE",
    )


@pytest.fixture
def setup(lecturer, student):
    f = Faculty.objects.create(code="FOC", name="Computing")
    d = Department.objects.create(faculty=f, code="CS", name="CS")
    prog_a = Programme.objects.create(department=d, code="BSC-CS", name="BSc CS")
    prog_b = Programme.objects.create(department=d, code="BSC-IT", name="BSc IT")
    c = Course.objects.create(
        department=d, code="CSC101", title="Intro", credits=3, level=100
    )
    y = AcademicYear.objects.create(
        name="2026/2027", start_date="2026-09-01", end_date="2027-07-31"
    )
    s = Semester.objects.create(
        academic_year=y,
        name="S1",
        code="S1",
        sequence=1,
        start_date="2026-09-01",
        end_date="2027-01-31",
        is_current=True,
    )
    o = CourseOffering.objects.create(
        course=c,
        semester=s,
        programme=prog_a,
        section="A",
        capacity=100,
        status=OfferingStatus.ACTIVE,
    )
    CourseInstructor.objects.create(
        course_offering=o,
        user=lecturer,
        teaching_role=TeachingRole.PRIMARY_INSTRUCTOR,
        can_manage_content=True,
        can_grade=True,
    )
    StudentProfile.objects.create(
        user=student,
        matricule_number="GU-2026-0001",
        programme=prog_a,
        current_level=100,
        admission_year=2026,
    )
    return {
        "offering": o,
        "programme_a": prog_a,
        "programme_b": prog_b,
        "lecturer": lecturer,
        "student": student,
    }


class TestAutoApproval:
    def test_eligible_student_enrolled_immediately(
        self, api, admin, lecturer, student, setup
    ):
        api.force_authenticate(user=student)
        res = api.post(
            f"/api/v1/course-offerings/{setup['offering'].id}/enrollment-request/",
            {},
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"]["status"] == "ACTIVE"
        assert res.json()["message"] == "You have been enrolled."

        enrollment = CourseEnrollment.objects.get(
            course_offering=setup["offering"], student=student
        )
        assert enrollment.status == EnrollmentStatus.ACTIVE

    def test_notifies_instructor_and_admin(
        self, api, admin, lecturer, student, setup
    ):
        api.force_authenticate(user=student)
        res = api.post(
            f"/api/v1/course-offerings/{setup['offering'].id}/enrollment-request/",
            {},
            format="json",
        )
        assert res.status_code == 201

        instructor_note = Notification.objects.filter(
            recipient=lecturer, type="ENROLLMENT", title="Enrollment auto-approved"
        )
        admin_note = Notification.objects.filter(
            recipient=admin, type="ENROLLMENT", title="Enrollment auto-approved"
        )
        assert instructor_note.count() == 1
        assert admin_note.count() == 1

    def test_shared_course_eligible_programme(self, api, admin, lecturer, student, setup):
        setup["offering"].eligible_programmes.add(setup["programme_b"])
        student.student_profile.programme = setup["programme_b"]
        student.student_profile.save(update_fields=["programme"])

        api.force_authenticate(user=student)
        res = api.post(
            f"/api/v1/course-offerings/{setup['offering'].id}/enrollment-request/",
            {},
            format="json",
        )
        assert res.status_code == 201
        enrollment = CourseEnrollment.objects.get(
            course_offering=setup["offering"], student=student
        )
        assert enrollment.status == EnrollmentStatus.ACTIVE

    def test_wrong_programme_rejected(self, api, admin, lecturer, student, setup):
        student.student_profile.programme = setup["programme_b"]
        student.student_profile.save(update_fields=["programme"])

        api.force_authenticate(user=student)
        res = api.post(
            f"/api/v1/course-offerings/{setup['offering'].id}/enrollment-request/",
            {},
            format="json",
        )
        assert res.status_code == 403
        assert not CourseEnrollment.objects.filter(
            course_offering=setup["offering"], student=student
        ).exists()

    def test_wrong_level_rejected(self, api, admin, lecturer, student, setup):
        student.student_profile.current_level = 200
        student.student_profile.save(update_fields=["current_level"])

        api.force_authenticate(user=student)
        res = api.post(
            f"/api/v1/course-offerings/{setup['offering'].id}/enrollment-request/",
            {},
            format="json",
        )
        assert res.status_code == 403

    def test_full_offering_rejected(self, api, admin, lecturer, student, setup):
        other = User.objects.create_user(
            email="other@x.y",
            university_id="GU9",
            password="p",
            first_name="O",
            last_name="T",
            status="ACTIVE",
        )
        setup["offering"].capacity = 1
        setup["offering"].save(update_fields=["capacity"])
        CourseEnrollment.objects.create(
            course_offering=setup["offering"],
            student=other,
            status=EnrollmentStatus.ACTIVE,
        )

        api.force_authenticate(user=student)
        res = api.post(
            f"/api/v1/course-offerings/{setup['offering'].id}/enrollment-request/",
            {},
            format="json",
        )
        assert res.status_code == 409

    def test_already_enrolled_conflict(self, api, admin, lecturer, student, setup):
        api.force_authenticate(user=student)
        first = api.post(
            f"/api/v1/course-offerings/{setup['offering'].id}/enrollment-request/",
            {},
            format="json",
        )
        assert first.status_code == 201
        again = api.post(
            f"/api/v1/course-offerings/{setup['offering'].id}/enrollment-request/",
            {},
            format="json",
        )
        assert again.status_code == 409

    def test_student_without_profile_rejected(self, api, admin, lecturer, setup):
        ghost = User.objects.create_user(
            email="ghost@x.y",
            university_id="GU8",
            password="p",
            status="ACTIVE",
        )
        api.force_authenticate(user=ghost)
        res = api.post(
            f"/api/v1/course-offerings/{setup['offering'].id}/enrollment-request/",
            {},
            format="json",
        )
        assert res.status_code == 403


class TestSemesterScoping:
    def _non_current_offering(self, setup):
        s2 = Semester.objects.create(
            academic_year=setup["offering"].semester.academic_year,
            name="S2",
            code="S2",
            sequence=2,
            start_date="2027-02-01",
            end_date="2027-07-31",
            is_current=False,
        )
        o2 = CourseOffering.objects.create(
            course=setup["offering"].course,
            semester=s2,
            programme=setup["programme_a"],
            section="A",
            capacity=100,
            status=OfferingStatus.ACTIVE,
        )
        return o2

    def test_request_on_non_current_semester_rejected(
        self, api, admin, lecturer, student, setup
    ):
        o2 = self._non_current_offering(setup)
        api.force_authenticate(user=student)
        res = api.post(
            f"/api/v1/course-offerings/{o2.id}/enrollment-request/",
            {},
            format="json",
        )
        assert res.status_code == 400
        assert not CourseEnrollment.objects.filter(
            course_offering=o2, student=student
        ).exists()

    def test_catalogue_excludes_non_current_semester(
        self, api, admin, lecturer, student, setup
    ):
        o2 = self._non_current_offering(setup)
        api.force_authenticate(user=student)
        res = api.get("/api/v1/course-offerings/?status=ACTIVE")
        assert res.status_code == 200
        ids = [o["id"] for o in res.json()["data"]]
        assert str(setup["offering"].id) in ids
        assert str(o2.id) not in ids

    def test_catalogue_includes_shared_programme(
        self, api, admin, lecturer, student, setup
    ):
        setup["offering"].eligible_programmes.add(setup["programme_b"])
        student.student_profile.programme = setup["programme_b"]
        student.student_profile.save(update_fields=["programme"])

        api.force_authenticate(user=student)
        res = api.get("/api/v1/course-offerings/?status=ACTIVE")
        assert res.status_code == 200
        ids = [o["id"] for o in res.json()["data"]]
        assert str(setup["offering"].id) in ids


class TestMyCoursesProgrammes:
    def test_shared_course_lists_all_programmes(
        self, api, admin, lecturer, student, setup
    ):
        setup["offering"].eligible_programmes.add(setup["programme_b"])
        CourseEnrollment.objects.create(
            course_offering=setup["offering"],
            student=student,
            status=EnrollmentStatus.ACTIVE,
        )

        api.force_authenticate(user=student)
        res = api.get("/api/v1/my/courses/")
        assert res.status_code == 200
        entry = res.json()["data"][0]
        names = [p["name"] for p in entry["courseOffering"]["programmes"]]
        assert names == [setup["programme_a"].name, setup["programme_b"].name]
        assert entry["courseOffering"]["programme"]["name"] == setup["programme_a"].name

    def test_single_programme_course(self, api, admin, lecturer, student, setup):
        CourseEnrollment.objects.create(
            course_offering=setup["offering"],
            student=student,
            status=EnrollmentStatus.ACTIVE,
        )

        api.force_authenticate(user=student)
        res = api.get("/api/v1/my/courses/")
        assert res.status_code == 200
        entry = res.json()["data"][0]
        assert entry["courseOffering"]["programmes"] == [
            {"id": str(setup["programme_a"].id), "name": setup["programme_a"].name}
        ]
