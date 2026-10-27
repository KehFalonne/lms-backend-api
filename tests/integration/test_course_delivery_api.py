import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

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
    return User.objects.create_user(
        email="stu@x.y",
        university_id="GU3",
        password="p",
        first_name="John",
        last_name="Student",
        status="ACTIVE",
    )


@pytest.fixture
def another_student():
    return User.objects.create_user(
        email="stu2@x.y",
        university_id="GU4",
        password="p",
        first_name="Mary",
        last_name="Learner",
        status="ACTIVE",
    )


@pytest.fixture
def offering_setup():
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
    o = CourseOffering.objects.create(
        course=c, semester=s, programme=p, section="A", capacity=2
    )
    return {"course": c, "semester": s, "programme": p, "offering": o}


class TestCourseOfferings:
    url = "/api/v1/course-offerings/"

    def test_list_requires_auth(self, api):
        assert api.get(self.url).status_code == 401

    def test_admin_can_create(self, api, admin, offering_setup):
        api.force_authenticate(user=admin)
        c = offering_setup["course"]
        s = offering_setup["semester"]
        p = offering_setup["programme"]
        res = api.post(
            self.url,
            {
                "courseId": str(c.id),
                "semesterId": str(s.id),
                "programmeId": str(p.id),
                "section": "B",
                "capacity": 50,
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"]["section"] == "B"

    def test_student_cannot_create(self, api, student, offering_setup):
        api.force_authenticate(user=student)
        res = api.post(
            self.url,
            {
                "courseId": str(offering_setup["course"].id),
                "semesterId": str(offering_setup["semester"].id),
                "programmeId": str(offering_setup["programme"].id),
                "section": "C",
            },
            format="json",
        )
        assert res.status_code == 403

    def test_publish_lifecycle(self, api, admin, offering_setup):
        api.force_authenticate(user=admin)
        o = offering_setup["offering"]
        res = api.post(f"{self.url}{o.id}/publish/")
        assert res.status_code == 200
        o.refresh_from_db()
        assert o.status == OfferingStatus.ACTIVE

    def test_publish_wrong_status_blocked(self, api, admin, offering_setup):
        api.force_authenticate(user=admin)
        o = offering_setup["offering"]
        o.status = OfferingStatus.COMPLETED
        o.save()
        res = api.post(f"{self.url}{o.id}/publish/")
        assert res.status_code == 400


class TestInstructors:
    def _url(self, offering_id):
        return f"/api/v1/course-offerings/{offering_id}/instructors/"

    def test_assign_instructor(self, api, admin, lecturer, offering_setup):
        api.force_authenticate(user=admin)
        o = offering_setup["offering"]
        res = api.post(
            self._url(o.id),
            {
                "userId": str(lecturer.id),
                "teachingRole": "PRIMARY_INSTRUCTOR",
                "canGrade": True,
                "canManageContent": True,
            },
            format="json",
        )
        assert res.status_code == 201
        assert CourseInstructor.objects.filter(
            course_offering=o, user=lecturer
        ).exists()

    def test_duplicate_instructor_blocked(self, api, admin, lecturer, offering_setup):
        api.force_authenticate(user=admin)
        o = offering_setup["offering"]
        CourseInstructor.objects.create(
            course_offering=o,
            user=lecturer,
            teaching_role=TeachingRole.INSTRUCTOR,
        )
        res = api.post(
            self._url(o.id),
            {"userId": str(lecturer.id), "teachingRole": "INSTRUCTOR"},
            format="json",
        )
        assert res.status_code == 409


class TestEnrollments:
    def _url(self, offering_id):
        return f"/api/v1/course-offerings/{offering_id}/enrollments/"

    def test_staff_can_enroll(self, api, admin, student, offering_setup):
        api.force_authenticate(user=admin)
        o = offering_setup["offering"]
        res = api.post(
            self._url(o.id),
            {"studentId": str(student.id)},
            format="json",
        )
        assert res.status_code == 201
        assert CourseEnrollment.objects.filter(
            course_offering=o, student=student
        ).exists()

    def test_student_cannot_enroll_others(
        self, api, student, another_student, offering_setup
    ):
        api.force_authenticate(user=student)
        o = offering_setup["offering"]
        res = api.post(
            self._url(o.id),
            {"studentId": str(another_student.id)},
            format="json",
        )
        assert res.status_code == 403

    def test_duplicate_enrollment_blocked(self, api, admin, student, offering_setup):
        api.force_authenticate(user=admin)
        o = offering_setup["offering"]
        CourseEnrollment.objects.create(course_offering=o, student=student)
        res = api.post(
            self._url(o.id),
            {"studentId": str(student.id)},
            format="json",
        )
        assert res.status_code == 409

    def test_bulk_enroll(self, api, admin, student, another_student, offering_setup):
        api.force_authenticate(user=admin)
        o = offering_setup["offering"]
        o.capacity = 10
        o.save()
        res = api.post(
            f"{self._url(o.id)}bulk/",
            {"studentIds": [str(student.id), str(another_student.id)]},
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"]["created"] == 2

    def test_my_courses(self, api, student, offering_setup):
        api.force_authenticate(user=student)
        o = offering_setup["offering"]
        CourseEnrollment.objects.create(course_offering=o, student=student)
        res = api.get("/api/v1/my/courses/")
        assert res.status_code == 200
        assert len(res.json()["data"]) == 1


class TestModulesAndContent:
    def test_create_module_and_content(self, api, admin, offering_setup):
        api.force_authenticate(user=admin)
        o = offering_setup["offering"]
        res = api.post(
            f"/api/v1/course-offerings/{o.id}/modules/",
            {"title": "Introduction", "position": 1, "isPublished": True},
            format="json",
        )
        assert res.status_code == 201
        module_id = res.json()["data"]["id"]

        res = api.post(
            f"/api/v1/modules/{module_id}/content/",
            {
                "title": "Week 1 lecture",
                "contentType": "TEXT",
                "body": "Welcome.",
                "isPublished": True,
            },
            format="json",
        )
        assert res.status_code == 201

        res = api.get(f"/api/v1/modules/{module_id}/content/")
        assert res.status_code == 200
        assert len(res.json()["data"]) == 1
