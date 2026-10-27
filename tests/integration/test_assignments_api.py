import pytest
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
        university_id="GU2",
        password="p",
        first_name="Jane",
        last_name="L",
        status="ACTIVE",
    )


@pytest.fixture
def student():
    return User.objects.create_user(
        email="stu@x.y",
        university_id="GU3",
        password="p",
        first_name="John",
        last_name="S",
        status="ACTIVE",
    )


@pytest.fixture
def other_student():
    return User.objects.create_user(
        email="s2@x.y",
        university_id="GU4",
        password="p",
        first_name="Mary",
        last_name="T",
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


class TestAssignmentCRUD:
    def _url(self, oid):
        return f"/api/v1/course-offerings/{oid}/assignments/"

    def test_lecturer_creates(self, api, lecturer, setup):
        api.force_authenticate(user=lecturer)
        due = (timezone.now() + timedelta(days=7)).isoformat()
        res = api.post(
            self._url(setup["offering"].id),
            {
                "title": "Essay 1",
                "description": "Write 500 words.",
                "maxScore": "20.00",
                "dueAt": due,
                "submissionType": "TEXT_ENTRY",
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.json()["data"]["status"] == "DRAFT"

    def test_publish_flow(self, api, lecturer, setup):
        api.force_authenticate(user=lecturer)
        a = Assignment.objects.create(
            course_offering=setup["offering"],
            title="Test",
            due_at=timezone.now() + timedelta(days=7),
            submission_type=SubmissionType.TEXT_ENTRY,
            created_by=lecturer,
        )
        res = api.post(f"/api/v1/assignments/{a.id}/publish/")
        assert res.status_code == 200
        a.refresh_from_db()
        assert a.status == AssignmentStatus.PUBLISHED

    def test_student_cannot_create(self, api, student, setup):
        api.force_authenticate(user=student)
        res = api.post(
            self._url(setup["offering"].id),
            {
                "title": "Nope",
                "dueAt": (timezone.now() + timedelta(days=1)).isoformat(),
            },
            format="json",
        )
        assert res.status_code == 403


class TestSubmission:
    def _submission_url(self, aid):
        return f"/api/v1/assignments/{aid}/submissions/"

    def test_student_submits(self, api, student, setup):
        a = Assignment.objects.create(
            course_offering=setup["offering"],
            title="Essay",
            due_at=timezone.now() + timedelta(days=1),
            submission_type=SubmissionType.TEXT_ENTRY,
            status=AssignmentStatus.PUBLISHED,
            max_attempts=1,
        )
        api.force_authenticate(user=student)
        res = api.post(
            self._submission_url(a.id),
            {"textContent": "Here is my essay."},
            format="json",
        )
        assert res.status_code == 201
        body = res.json()["data"]
        assert body["status"] == "SUBMITTED"
        assert body["textContent"] == "Here is my essay."

    def test_non_enrolled_blocked(self, api, other_student, setup):
        a = Assignment.objects.create(
            course_offering=setup["offering"],
            title="Essay",
            due_at=timezone.now() + timedelta(days=1),
            submission_type=SubmissionType.TEXT_ENTRY,
            status=AssignmentStatus.PUBLISHED,
        )
        api.force_authenticate(user=other_student)
        res = api.post(
            self._submission_url(a.id),
            {"textContent": "hello"},
            format="json",
        )
        assert res.status_code == 400
        assert "not enrolled" in res.json()["message"].lower()

    def test_max_attempts_enforced(self, api, student, setup):
        a = Assignment.objects.create(
            course_offering=setup["offering"],
            title="Essay",
            due_at=timezone.now() + timedelta(days=1),
            submission_type=SubmissionType.TEXT_ENTRY,
            status=AssignmentStatus.PUBLISHED,
            max_attempts=1,
        )
        AssignmentSubmission.objects.create(
            assignment=a,
            student=student,
            attempt_number=1,
            status=SubmissionStatus.SUBMITTED,
            submitted_at=timezone.now(),
            text_content="first",
        )
        api.force_authenticate(user=student)
        res = api.post(
            self._submission_url(a.id),
            {"textContent": "second"},
            format="json",
        )
        assert res.status_code == 400

    def test_late_blocked_when_disallowed(self, api, student, setup):
        a = Assignment.objects.create(
            course_offering=setup["offering"],
            title="Essay",
            due_at=timezone.now() - timedelta(days=1),
            allow_late_submission=False,
            submission_type=SubmissionType.TEXT_ENTRY,
            status=AssignmentStatus.PUBLISHED,
        )
        api.force_authenticate(user=student)
        res = api.post(
            self._submission_url(a.id),
            {"textContent": "x"},
            format="json",
        )
        assert res.status_code == 400

    def test_my_submission(self, api, student, setup):
        a = Assignment.objects.create(
            course_offering=setup["offering"],
            title="Essay",
            due_at=timezone.now() + timedelta(days=1),
            submission_type=SubmissionType.TEXT_ENTRY,
            status=AssignmentStatus.PUBLISHED,
        )
        AssignmentSubmission.objects.create(
            assignment=a,
            student=student,
            status=SubmissionStatus.SUBMITTED,
            submitted_at=timezone.now(),
            text_content="hi",
        )
        api.force_authenticate(user=student)
        res = api.get(f"/api/v1/assignments/{a.id}/submission/")
        assert res.status_code == 200
        assert res.json()["data"]["textContent"] == "hi"


class TestGrading:
    def test_lecturer_grades(self, api, lecturer, student, setup):
        a = Assignment.objects.create(
            course_offering=setup["offering"],
            title="Essay",
            due_at=timezone.now() + timedelta(days=1),
            submission_type=SubmissionType.TEXT_ENTRY,
            status=AssignmentStatus.PUBLISHED,
            max_score=20,
        )
        s = AssignmentSubmission.objects.create(
            assignment=a,
            student=student,
            status=SubmissionStatus.SUBMITTED,
            submitted_at=timezone.now(),
            text_content="hi",
        )
        api.force_authenticate(user=lecturer)
        res = api.patch(
            f"/api/v1/assignment-submissions/{s.id}/grade/",
            {"score": "18.00", "feedback": "Great work!"},
            format="json",
        )
        assert res.status_code == 200
        s.refresh_from_db()
        assert s.status == SubmissionStatus.GRADED
        assert str(s.score) == "18.00"
        assert s.feedback == "Great work!"

    def test_score_out_of_range(self, api, lecturer, student, setup):
        a = Assignment.objects.create(
            course_offering=setup["offering"],
            title="Essay",
            due_at=timezone.now() + timedelta(days=1),
            submission_type=SubmissionType.TEXT_ENTRY,
            status=AssignmentStatus.PUBLISHED,
            max_score=20,
        )
        s = AssignmentSubmission.objects.create(
            assignment=a,
            student=student,
            status=SubmissionStatus.SUBMITTED,
            submitted_at=timezone.now(),
            text_content="x",
        )
        api.force_authenticate(user=lecturer)
        res = api.patch(
            f"/api/v1/assignment-submissions/{s.id}/grade/",
            {"score": "25.00"},
            format="json",
        )
        assert res.status_code == 400

    def test_student_cannot_grade(self, api, student, setup):
        a = Assignment.objects.create(
            course_offering=setup["offering"],
            title="Essay",
            due_at=timezone.now() + timedelta(days=1),
            submission_type=SubmissionType.TEXT_ENTRY,
            status=AssignmentStatus.PUBLISHED,
        )
        s = AssignmentSubmission.objects.create(
            assignment=a,
            student=student,
            status=SubmissionStatus.SUBMITTED,
            submitted_at=timezone.now(),
            text_content="x",
        )
        api.force_authenticate(user=student)
        res = api.patch(
            f"/api/v1/assignment-submissions/{s.id}/grade/",
            {"score": "18"},
            format="json",
        )
        assert res.status_code == 403
