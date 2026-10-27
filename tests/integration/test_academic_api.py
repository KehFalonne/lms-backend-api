import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, Semester
from apps.courses.models import Course, CoursePrerequisite
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
def hierarchy():
    """Faculty → Department → Programme → Course."""
    f = Faculty.objects.create(code="FOC", name="Faculty of Computing")
    d = Department.objects.create(faculty=f, code="CS", name="Computer Science")
    p = Programme.objects.create(department=d, code="BSC-CS", name="BSc CS")
    c = Course.objects.create(
        department=d, code="CSC101", title="Intro", credits=3, level=100
    )
    c2 = Course.objects.create(
        department=d, code="CSC201", title="Data Structures", credits=3, level=200
    )
    return {"faculty": f, "department": d, "programme": p, "course": c, "course2": c2}


class TestFaculties:
    url = "/api/v1/faculties/"

    def test_list_requires_auth(self, api):
        assert api.get(self.url).status_code == 401

    def test_list_authenticated(self, api, student, hierarchy):
        api.force_authenticate(user=student)
        res = api.get(self.url)
        assert res.status_code == 200
        assert res.json()["success"] is True
        assert len(res.json()["data"]) == 1
        assert res.json()["data"][0]["code"] == "FOC"

    def test_create_requires_admin(self, api, student):
        api.force_authenticate(user=student)
        res = api.post(self.url, {"code": "FOS", "name": "Science"}, format="json")
        assert res.status_code == 403

    def test_admin_can_create(self, api, admin):
        api.force_authenticate(user=admin)
        res = api.post(self.url, {"code": "fos", "name": "Science"}, format="json")
        assert res.status_code == 201
        assert res.json()["data"]["code"] == "FOS"


class TestDepartments:
    url = "/api/v1/departments/"

    def test_create_under_faculty(self, api, admin, hierarchy):
        api.force_authenticate(user=admin)
        res = api.post(
            self.url,
            {
                "facultyId": str(hierarchy["faculty"].id),
                "code": "SE",
                "name": "Software Engineering",
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"]["code"] == "SE"
        assert res.json()["data"]["faculty"]["code"] == "FOC"

    def test_filter_by_faculty(self, api, student, hierarchy):
        api.force_authenticate(user=student)
        res = api.get(f"{self.url}?faculty={hierarchy['faculty'].id}")
        assert res.status_code == 200
        assert len(res.json()["data"]) == 1


class TestProgrammes:
    url = "/api/v1/programmes/"

    def test_create(self, api, admin, hierarchy):
        api.force_authenticate(user=admin)
        res = api.post(
            self.url,
            {
                "departmentId": str(hierarchy["department"].id),
                "code": "BSC-SE",
                "name": "BSc Software Engineering",
                "degreeType": "BSC",
                "durationYears": 4,
            },
            format="json",
        )
        assert res.status_code == 201


class TestAcademicYears:
    url = "/api/v1/academic-years/"

    def test_create(self, api, admin):
        api.force_authenticate(user=admin)
        res = api.post(
            self.url,
            {"name": "2026/2027", "startDate": "2026-09-01", "endDate": "2027-07-31"},
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"]["isCurrent"] is False

    def test_set_current(self, api, admin):
        api.force_authenticate(user=admin)
        y1 = AcademicYear.objects.create(
            name="2025/2026",
            start_date="2025-09-01",
            end_date="2026-07-31",
            is_current=True,
        )
        y2 = AcademicYear.objects.create(
            name="2026/2027", start_date="2026-09-01", end_date="2027-07-31"
        )
        res = api.post(f"{self.url}{y2.id}/set-current/")
        assert res.status_code == 200
        y1.refresh_from_db()
        y2.refresh_from_db()
        assert y1.is_current is False
        assert y2.is_current is True


class TestSemesters:
    def test_create_and_set_current(self, api, admin):
        api.force_authenticate(user=admin)
        y = AcademicYear.objects.create(
            name="2026/2027", start_date="2026-09-01", end_date="2027-07-31"
        )
        res = api.post(
            "/api/v1/semesters/",
            {
                "academicYearId": str(y.id),
                "name": "Semester 1",
                "code": "S1",
                "sequence": 1,
                "startDate": "2026-09-01",
                "endDate": "2027-01-31",
            },
            format="json",
        )
        assert res.status_code == 201
        s_id = res.json()["data"]["id"]

        res = api.post(f"/api/v1/semesters/{s_id}/set-current/")
        assert res.status_code == 200
        assert res.json()["data"]["isCurrent"] is True


class TestCourses:
    url = "/api/v1/courses/"

    def test_create(self, api, admin, hierarchy):
        api.force_authenticate(user=admin)
        res = api.post(
            self.url,
            {
                "departmentId": str(hierarchy["department"].id),
                "code": "CSC301",
                "title": "Database Systems",
                "credits": 3,
                "level": 300,
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"]["code"] == "CSC301"

    def test_add_prerequisite(self, api, admin, hierarchy):
        api.force_authenticate(user=admin)
        c = hierarchy["course"]
        c2 = hierarchy["course2"]
        res = api.post(
            f"{self.url}{c2.id}/prerequisites/",
            {"prerequisiteCourseId": str(c.id), "minimumGrade": "C"},
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"]["prerequisiteCourse"]["code"] == "CSC101"

    def test_self_prerequisite_blocked(self, api, admin, hierarchy):
        api.force_authenticate(user=admin)
        c = hierarchy["course"]
        res = api.post(
            f"{self.url}{c.id}/prerequisites/",
            {"prerequisiteCourseId": str(c.id)},
            format="json",
        )
        assert res.status_code == 400

    def test_duplicate_prerequisite_blocked(self, api, admin, hierarchy):
        api.force_authenticate(user=admin)
        c, c2 = hierarchy["course"], hierarchy["course2"]
        CoursePrerequisite.objects.create(course=c2, prerequisite_course=c)
        res = api.post(
            f"{self.url}{c2.id}/prerequisites/",
            {"prerequisiteCourseId": str(c.id)},
            format="json",
        )
        assert res.status_code == 409

    def test_delete_prerequisite(self, api, admin, hierarchy):
        api.force_authenticate(user=admin)
        c, c2 = hierarchy["course"], hierarchy["course2"]
        p = CoursePrerequisite.objects.create(course=c2, prerequisite_course=c)
        res = api.delete(f"{self.url}{c2.id}/prerequisites/{p.id}/")
        assert res.status_code == 200
        assert not CoursePrerequisite.objects.filter(pk=p.id).exists()
