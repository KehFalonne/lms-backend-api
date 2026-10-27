import pytest
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, Semester
from apps.assessments.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentQuestion,
    AssessmentStatus,
    AttemptStatus,
    Question,
    QuestionBank,
    QuestionOption,
    QuestionType,
    StudentAnswer,
)
from apps.courses.models import (
    Course,
    CourseEnrollment,
    CourseInstructor,
    CourseOffering,
    EnrollmentStatus,
    TeachingRole,
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


def _make_mcq(bank, text="What is 2+2?", correct_index=0):
    q = Question.objects.create(
        question_bank=bank,
        question_type=QuestionType.MULTIPLE_CHOICE,
        text=text,
        default_points=Decimal("2.00"),
        created_by=bank.owner,
    )
    options = ["4", "3", "5", "22"]
    for idx, opt in enumerate(options):
        QuestionOption.objects.create(
            question=q,
            text=opt,
            is_correct=(idx == correct_index),
            position=idx + 1,
        )
    return q


class TestQuestionBank:
    url = "/api/v1/question-banks/"

    def test_create_bank(self, api, lecturer):
        api.force_authenticate(user=lecturer)
        res = api.post(
            self.url, {"title": "Q1 Bank", "visibility": "PRIVATE"}, format="json"
        )
        assert res.status_code == 201
        assert res.json()["data"]["title"] == "Q1 Bank"

    def test_create_question(self, api, lecturer):
        api.force_authenticate(user=lecturer)
        bank = QuestionBank.objects.create(title="B", owner=lecturer)

        res = api.post(
            f"{self.url}{bank.id}/questions/",
            {
                "questionType": "MULTIPLE_CHOICE",
                "text": "What is 2+2?",
                "defaultPoints": "2.00",
                "options": [
                    {"text": "4", "isCorrect": True, "position": 1},
                    {"text": "3", "isCorrect": False, "position": 2},
                    {"text": "5", "isCorrect": False, "position": 3},
                ],
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"]["options"][0]["isCorrect"] is True


class TestAssessmentLifecycle:
    def test_create_assessment(self, api, lecturer, setup):
        api.force_authenticate(user=lecturer)
        res = api.post(
            f"/api/v1/course-offerings/{setup['offering'].id}/assessments/",
            {
                "courseOfferingId": str(setup["offering"].id),
                "title": "Quiz 1",
                "assessmentType": "QUIZ",
                "maxAttempts": 1,
                "timeLimitMinutes": 30,
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"]["status"] == "DRAFT"

    def test_publish_requires_questions(self, api, lecturer, setup):
        api.force_authenticate(user=lecturer)
        a = Assessment.objects.create(
            course_offering=setup["offering"],
            title="Empty",
            created_by=lecturer,
        )
        res = api.post(f"/api/v1/assessments/{a.id}/publish/")
        assert res.status_code == 400

    def test_add_question_and_publish(self, api, lecturer, setup):
        api.force_authenticate(user=lecturer)
        a = Assessment.objects.create(
            course_offering=setup["offering"],
            title="Quiz",
            created_by=lecturer,
            available_from=timezone.now() - timedelta(hours=1),
            available_until=timezone.now() + timedelta(days=1),
        )
        bank = QuestionBank.objects.create(title="B", owner=lecturer)
        q = _make_mcq(bank)

        res = api.post(
            f"/api/v1/assessments/{a.id}/questions/",
            {"questionId": str(q.id), "position": 1, "points": "2.00"},
            format="json",
        )
        assert res.status_code == 201

        res = api.post(f"/api/v1/assessments/{a.id}/publish/")
        assert res.status_code == 200
        assert res.json()["data"]["status"] == "PUBLISHED"


class TestAttemptFlow:
    def _make_assessment(self, setup, lecturer, *, time_limit=30):
        a = Assessment.objects.create(
            course_offering=setup["offering"],
            title="Quiz",
            assessment_type="QUIZ",
            created_by=lecturer,
            max_attempts=1,
            time_limit_minutes=time_limit,
            available_from=timezone.now() - timedelta(hours=1),
            available_until=timezone.now() + timedelta(days=1),
            status=AssessmentStatus.PUBLISHED,
            total_points=Decimal("2.00"),
        )
        bank = QuestionBank.objects.create(title="B", owner=lecturer)
        q = _make_mcq(bank)
        aq = AssessmentQuestion.objects.create(
            assessment=a, question=q, position=1, points=Decimal("2.00")
        )
        return a, aq, q

    def test_student_starts_and_submits(self, api, student, lecturer, setup):
        a, aq, q = self._make_assessment(setup, lecturer)

        api.force_authenticate(user=student)
        res = api.post(f"/api/v1/assessments/{a.id}/attempts/start/")
        assert res.status_code == 201
        attempt_id = res.json()["data"]["id"]

        # Save correct answer
        correct = q.options.filter(is_correct=True).first()
        res = api.put(
            f"/api/v1/assessment-attempts/{attempt_id}/answers/{aq.id}/",
            {"selectedOptionIds": [str(correct.id)]},
            format="json",
        )
        assert res.status_code == 200

        # Submit
        res = api.post(f"/api/v1/assessment-attempts/{attempt_id}/submit/")
        assert res.status_code == 200
        body = res.json()["data"]
        assert body["status"] == "AUTO_GRADED"
        assert Decimal(body["totalScore"]) == Decimal("2.00")
        assert Decimal(body["percentage"]) == Decimal("100.00")

    def test_wrong_answer_scores_zero(self, api, student, lecturer, setup):
        a, aq, q = self._make_assessment(setup, lecturer)

        api.force_authenticate(user=student)
        attempt_id = api.post(f"/api/v1/assessments/{a.id}/attempts/start/").json()[
            "data"
        ]["id"]
        wrong = q.options.filter(is_correct=False).first()
        api.put(
            f"/api/v1/assessment-attempts/{attempt_id}/answers/{aq.id}/",
            {"selectedOptionIds": [str(wrong.id)]},
            format="json",
        )
        body = api.post(f"/api/v1/assessment-attempts/{attempt_id}/submit/").json()[
            "data"
        ]
        assert Decimal(body["totalScore"]) == Decimal("0.00")

    def test_max_attempts_enforced(self, api, student, lecturer, setup):
        a, aq, q = self._make_assessment(setup, lecturer)

        api.force_authenticate(user=student)
        api.post(f"/api/v1/assessments/{a.id}/attempts/start/")
        res = api.post(f"/api/v1/assessments/{a.id}/attempts/start/")
        assert res.status_code == 400

    def test_student_cannot_see_other_attempt(self, api, student, lecturer, setup):
        # Create an attempt owned by the lecturer (not student)
        a, aq, q = self._make_assessment(setup, lecturer)
        from apps.assessments.services.attempt_service import AttemptService

        CourseEnrollment.objects.get_or_create(
            course_offering=setup["offering"],
            student=lecturer,
            defaults={"status": EnrollmentStatus.ACTIVE},
        )
        attempt = AttemptService.start_attempt(assessment=a, student=lecturer)

        api.force_authenticate(user=student)
        res = api.get(f"/api/v1/assessment-attempts/{attempt.id}/")
        assert res.status_code == 403


class TestMyAssessments:
    def test_list(self, api, student, lecturer, setup):
        a, aq, q = self._make_assessment_for_test(setup, lecturer)
        api.force_authenticate(user=student)
        res = api.get("/api/v1/my/assessments/")
        assert res.status_code == 200
        assert len(res.json()["data"]) == 1

    def _make_assessment_for_test(self, setup, lecturer):
        a = Assessment.objects.create(
            course_offering=setup["offering"],
            title="Quiz",
            created_by=lecturer,
            status=AssessmentStatus.PUBLISHED,
            available_from=timezone.now() - timedelta(hours=1),
            available_until=timezone.now() + timedelta(days=1),
        )
        return a, None, None
