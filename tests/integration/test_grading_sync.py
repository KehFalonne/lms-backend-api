import pytest
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, Semester
from apps.assignments.models import (
    Assignment,
    AssignmentStatus,
    AssignmentSubmission,
    SubmissionStatus,
    SubmissionType,
)
from apps.assignments.services.submission_service import SubmissionService
from apps.assessments.models import Assessment, AssessmentAttempt, AttemptStatus
from apps.courses.models import (
    Course,
    CourseEnrollment,
    CourseInstructor,
    CourseOffering,
    EnrollmentStatus,
    TeachingRole,
)
from apps.grading.models import Grade, GradeItem, GradeSourceType, GradeStatus
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
    )
    CourseEnrollment.objects.create(
        course_offering=o,
        student=student,
        status=EnrollmentStatus.ACTIVE,
    )
    return {"offering": o, "lecturer": lecturer, "student": student}


def _graded_submission(offering, lecturer, student, *, title="Essay", max_score=20, score="18.00"):
    a = Assignment.objects.create(
        course_offering=offering,
        title=title,
        due_at=timezone.now() + timedelta(days=7),
        submission_type=SubmissionType.TEXT_ENTRY,
        status=AssignmentStatus.PUBLISHED,
        max_score=max_score,
        created_by=lecturer,
    )
    sub = AssignmentSubmission.objects.create(
        assignment=a,
        student=student,
        status=SubmissionStatus.SUBMITTED,
        submitted_at=timezone.now(),
        text_content="hi",
    )
    SubmissionService.grade_submission(
        submission=sub, grader=lecturer, score=Decimal(score), feedback="Good"
    )
    return a, sub


class TestAssignmentGradeSync:
    def test_grading_creates_linked_item_and_published_grade(
        self, setup, lecturer, student
    ):
        a, sub = _graded_submission(setup["offering"], lecturer, student)

        item = GradeItem.objects.get(
            source_type=GradeSourceType.ASSIGNMENT, source_id=a.id
        )
        assert item.course_offering_id == a.course_offering_id
        assert item.name == "Essay"
        assert item.max_score == Decimal("20.00")
        assert item.is_published is True

        grade = Grade.objects.get(grade_item=item, student=student)
        assert grade.score == Decimal("18.00")
        assert grade.percentage == Decimal("90.00")
        assert grade.status == GradeStatus.PUBLISHED
        assert grade.published_at is not None

    def test_regrading_reuses_item(self, setup, lecturer, student):
        a, sub = _graded_submission(setup["offering"], lecturer, student)
        SubmissionService.grade_submission(
            submission=sub, grader=lecturer, score=Decimal("10.00")
        )
        assert GradeItem.objects.filter(
            source_type=GradeSourceType.ASSIGNMENT, source_id=a.id
        ).count() == 1
        grade = Grade.objects.get(
            grade_item__source_id=a.id, student=student
        )
        assert grade.score == Decimal("10.00")

    def test_item_max_score_follows_assignment_edit(self, setup, lecturer, student):
        a, _sub = _graded_submission(setup["offering"], lecturer, student)
        a.max_score = 50
        a.save(update_fields=["max_score"])
        _graded_submission(
            setup["offering"],
            lecturer,
            student,
            title="Other",
            max_score=10,
            score="5.00",
        )
        SubmissionService.grade_submission(
            submission=_sub, grader=lecturer, score=Decimal("40.00")
        )
        item = GradeItem.objects.get(
            source_type=GradeSourceType.ASSIGNMENT, source_id=a.id
        )
        assert item.max_score == Decimal("50.00")


class TestMyGradesWithoutCategories:
    def _my_grades(self, api, student):
        api.force_authenticate(user=student)
        return api.get("/api/v1/my/grades/")

    def test_single_assignment_average(self, api, setup, lecturer, student):
        _graded_submission(setup["offering"], lecturer, student)
        res = self._my_grades(api, student)
        assert res.status_code == 200
        entry = res.json()["data"][0]
        assert entry["percentage"] == "90.00"
        assert entry["letterGrade"] == "A"

    def test_multiple_items_average(self, api, setup, lecturer, student):
        _graded_submission(setup["offering"], lecturer, student)  # 18/20 = 90
        _graded_submission(
            setup["offering"],
            lecturer,
            student,
            title="Quiz",
            max_score=10,
            score="5.00",
        )  # 50
        res = self._my_grades(api, student)
        assert res.status_code == 200
        entry = res.json()["data"][0]
        assert entry["percentage"] == "70.00"
        assert entry["letterGrade"] == "C"

    def test_ungraded_course_stays_zero(self, api, setup, lecturer, student):
        Assignment.objects.create(
            course_offering=setup["offering"],
            title="No grades yet",
            due_at=timezone.now() + timedelta(days=7),
            submission_type=SubmissionType.TEXT_ENTRY,
            status=AssignmentStatus.PUBLISHED,
            created_by=lecturer,
        )
        res = self._my_grades(api, student)
        assert res.status_code == 200
        assert Decimal(res.json()["data"][0]["percentage"]) == Decimal("0.00")


class TestAttemptGradeSync:
    def test_attempt_creates_linked_item_and_grade(self, setup, student):
        from apps.grading.services.grade_service import GradeService

        a = Assessment.objects.create(
            course_offering=setup["offering"],
            title="CA 1",
            total_points=10,
        )
        attempt = AssessmentAttempt.objects.create(
            assessment=a,
            student=student,
            status=AttemptStatus.AUTO_GRADED,
            total_score=Decimal("8.00"),
        )
        GradeService.sync_from_attempt(attempt=attempt)

        item = GradeItem.objects.get(
            source_type=GradeSourceType.ASSESSMENT, source_id=a.id
        )
        assert item.name == "CA 1"
        assert item.max_score == Decimal("10.00")
        assert item.is_published is True

        grade = Grade.objects.get(grade_item=item, student=student)
        assert grade.score == Decimal("8.00")
        assert grade.status == GradeStatus.PUBLISHED
