import pytest
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, Semester
from apps.courses.models import (
    Course,
    CourseEnrollment,
    CourseInstructor,
    CourseOffering,
    EnrollmentStatus,
    TeachingRole,
)
from apps.grading.models import (
    Grade,
    GradeCategory,
    GradeHistory,
    GradeItem,
    GradeSourceType,
    GradeStatus,
)
from apps.university.models import Department, Faculty, Programme

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


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
    p = Programme.objects.create(department=d, code="BSC-CS", name="BSc")
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
    )
    o = CourseOffering.objects.create(course=c, semester=s, programme=p, section="A")
    CourseInstructor.objects.create(
        course_offering=o,
        user=lecturer,
        teaching_role=TeachingRole.PRIMARY_INSTRUCTOR,
        can_manage_content=True,
        can_grade=True,
        can_manage_assessments=True,
    )
    CourseEnrollment.objects.create(
        course_offering=o,
        student=student,
        status=EnrollmentStatus.ACTIVE,
    )
    return {"offering": o, "lecturer": lecturer, "student": student}


class TestCategories:
    def test_set_weights_must_sum_100(self, api, lecturer, setup):
        api.force_authenticate(user=lecturer)
        res = api.put(
            f"/api/v1/course-offerings/{setup['offering'].id}/grade-categories/set-weights/",
            {
                "weights": [
                    {"name": "Assignments", "weight": "40.00"},
                    {"name": "Final", "weight": "50.00"},
                ]
            },
            format="json",
        )
        assert res.status_code == 400

    def test_set_weights_success(self, api, lecturer, setup):
        api.force_authenticate(user=lecturer)
        res = api.put(
            f"/api/v1/course-offerings/{setup['offering'].id}/grade-categories/set-weights/",
            {
                "weights": [
                    {"name": "Assignments", "weight": "40.00"},
                    {"name": "Final", "weight": "60.00"},
                ]
            },
            format="json",
        )
        assert res.status_code == 200
        assert len(res.json()["data"]) == 2


class TestGradeItems:
    def test_create_item(self, api, lecturer, setup):
        api.force_authenticate(user=lecturer)
        cat = GradeCategory.objects.create(
            course_offering=setup["offering"],
            name="Assignments",
            weight=100,
            position=1,
        )
        res = api.post(
            f"/api/v1/course-offerings/{setup['offering'].id}/grade-items/",
            {
                "name": "Essay 1",
                "category": str(cat.id),
                "maxScore": "20.00",
                "sourceType": "MANUAL",
                "position": 1,
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"]["name"] == "Essay 1"


class TestGrades:
    def test_set_grade_creates_history(self, api, lecturer, student, setup):
        api.force_authenticate(user=lecturer)
        item = GradeItem.objects.create(
            course_offering=setup["offering"],
            name="Essay",
            max_score=20,
            source_type=GradeSourceType.MANUAL,
        )

        res = api.patch(
            f"/api/v1/grade-items/{item.id}/grades/{student.id}/",
            {"score": "15.00", "feedback": "Good work", "reason": "Initial grading"},
            format="json",
        )
        assert res.status_code == 200
        grade = Grade.objects.get(grade_item=item, student=student)
        assert grade.score == Decimal("15.00")
        assert grade.percentage == Decimal("75.00")

        # Update → history entry created
        res = api.patch(
            f"/api/v1/grade-items/{item.id}/grades/{student.id}/",
            {"score": "17.00", "reason": "After review"},
            format="json",
        )
        assert res.status_code == 200
        grade.refresh_from_db()
        assert grade.score == Decimal("17.00")

        history = grade.history.all()
        assert history.count() == 1
        assert history.first().previous_score == Decimal("15.00")
        assert history.first().new_score == Decimal("17.00")
        assert history.first().reason == "After review"

    def test_score_out_of_range(self, api, lecturer, student, setup):
        api.force_authenticate(user=lecturer)
        item = GradeItem.objects.create(
            course_offering=setup["offering"],
            name="Essay",
            max_score=20,
        )
        res = api.patch(
            f"/api/v1/grade-items/{item.id}/grades/{student.id}/",
            {"score": "25.00"},
            format="json",
        )
        assert res.status_code == 400


class TestPublish:
    def test_publish_item(self, api, lecturer, student, setup):
        api.force_authenticate(user=lecturer)
        item = GradeItem.objects.create(
            course_offering=setup["offering"],
            name="Essay",
            max_score=20,
        )
        Grade.objects.create(
            grade_item=item,
            student=student,
            score=Decimal("15.00"),
            status=GradeStatus.DRAFT,
        )
        res = api.post(f"/api/v1/grade-items/{item.id}/publish/")
        assert res.status_code == 200
        assert res.json()["data"]["published"] == 1

        g = Grade.objects.get(grade_item=item, student=student)
        assert g.status == GradeStatus.PUBLISHED
        assert g.published_at is not None

    def test_student_cannot_see_draft(self, api, student, lecturer, setup):
        item = GradeItem.objects.create(
            course_offering=setup["offering"],
            name="Essay",
            max_score=20,
            is_published=False,
        )
        Grade.objects.create(
            grade_item=item,
            student=student,
            score=Decimal("15.00"),
            status=GradeStatus.DRAFT,
        )
        api.force_authenticate(user=student)
        res = api.get(f"/api/v1/my/course-offerings/{setup['offering'].id}/grades/")
        assert res.status_code == 200
        body = res.json()["data"]
        assert len(body["items"]) == 0


class TestFinalGrade:
    def test_weighted_calculation(self, api, lecturer, student, setup):
        api.force_authenticate(user=lecturer)

        cat_a = GradeCategory.objects.create(
            course_offering=setup["offering"],
            name="Assignments",
            weight=40,
            position=1,
        )
        cat_f = GradeCategory.objects.create(
            course_offering=setup["offering"],
            name="Final",
            weight=60,
            position=2,
        )

        item_a = GradeItem.objects.create(
            course_offering=setup["offering"],
            category=cat_a,
            name="Essay",
            max_score=100,
        )
        item_f = GradeItem.objects.create(
            course_offering=setup["offering"],
            category=cat_f,
            name="Exam",
            max_score=100,
        )

        # Student scored 90 on assignments, 70 on final
        Grade.objects.create(grade_item=item_a, student=student, score=90)
        Grade.objects.create(grade_item=item_f, student=student, score=70)

        # 90 * 0.40 + 70 * 0.60 = 36 + 42 = 78
        api.force_authenticate(user=student)
        res = api.get("/api/v1/my/grades/")
        assert res.status_code == 200
        entry = res.json()["data"][0]
        assert entry["percentage"] == "78.00"
        assert entry["letterGrade"] == "C"

    def test_letter_grade_boundaries(self):
        from apps.grading.services.grade_service import GradeService

        assert GradeService._letter_grade(Decimal("95")) == "A"
        assert GradeService._letter_grade(Decimal("85")) == "B"
        assert GradeService._letter_grade(Decimal("75")) == "C"
        assert GradeService._letter_grade(Decimal("65")) == "D"
        assert GradeService._letter_grade(Decimal("55")) == "E"
        assert GradeService._letter_grade(Decimal("45")) == "F"
