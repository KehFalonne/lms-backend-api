import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, Semester
from apps.assignments.models import AssignmentFile
from apps.courses.models import Course, CourseInstructor, CourseOffering, TeachingRole
from apps.files.models import File, FileStatus
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
        first_name="Jane",
        last_name="L",
        status="ACTIVE",
    )


@pytest.fixture
def other_lecturer():
    return User.objects.create_user(
        email="lec2@x.y",
        university_id="GU22",
        password="p",
        first_name="Bob",
        last_name="M",
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
def offering(lecturer):
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
    )
    return o


def make_file(uploader, *, status=FileStatus.READY, name="questions.pdf"):
    return File.objects.create(
        original_name=name,
        storage_key=f"materials/{name}-{File.objects.count()}",
        mime_type="application/pdf",
        extension="pdf",
        size_bytes=1024,
        status=status,
        uploaded_by=uploader,
    )


def assignment_payload(due=None):
    due = due or (timezone.now() + timedelta(days=7)).isoformat()
    return {
        "title": "Problem Set 1",
        "description": "1. Solve this.\n2. Solve that.",
        "maxScore": "20.00",
        "dueAt": due,
        "submissionType": "FILE_UPLOAD",
    }


class TestAssignmentAttachments:
    def test_create_with_attachment(self, api, lecturer, offering):
        api.force_authenticate(user=lecturer)
        f = make_file(lecturer)
        payload = assignment_payload()
        payload["attachmentFileIds"] = [str(f.id)]
        res = api.post(
            f"/api/v1/course-offerings/{offering.id}/assignments/",
            payload,
            format="json",
        )
        assert res.status_code == 201, res.content
        data = res.json()["data"]
        assert len(data["attachments"]) == 1
        assert data["attachments"][0]["fileId"] == str(f.id)
        assert data["attachments"][0]["originalName"] == "questions.pdf"
        assert AssignmentFile.objects.filter(file=f).exists()

    def test_rejects_file_uploaded_by_someone_else(self, api, lecturer, other_lecturer, offering):
        api.force_authenticate(user=lecturer)
        f = make_file(other_lecturer)
        payload = assignment_payload()
        payload["attachmentFileIds"] = [str(f.id)]
        res = api.post(
            f"/api/v1/course-offerings/{offering.id}/assignments/",
            payload,
            format="json",
        )
        assert res.status_code == 400
        assert not AssignmentFile.objects.filter(file=f).exists()

    def test_rejects_unready_file(self, api, lecturer, offering):
        api.force_authenticate(user=lecturer)
        f = make_file(lecturer, status=FileStatus.PENDING)
        payload = assignment_payload()
        payload["attachmentFileIds"] = [str(f.id)]
        res = api.post(
            f"/api/v1/course-offerings/{offering.id}/assignments/",
            payload,
            format="json",
        )
        assert res.status_code == 400
        assert not AssignmentFile.objects.filter(file=f).exists()

    def test_patch_adds_attachments_and_keeps_existing(self, api, lecturer, offering):
        api.force_authenticate(user=lecturer)
        f1 = make_file(lecturer, name="q1.pdf")
        payload = assignment_payload()
        payload["attachmentFileIds"] = [str(f1.id)]
        created = api.post(
            f"/api/v1/course-offerings/{offering.id}/assignments/",
            payload,
            format="json",
        )
        assignment_id = created.json()["data"]["id"]

        f2 = make_file(lecturer, name="q2.pdf")
        res = api.patch(
            f"/api/v1/assignments/{assignment_id}/",
            {"attachmentFileIds": [str(f2.id)]},
            format="json",
        )
        assert res.status_code == 200, res.content
        names = {a["originalName"] for a in res.json()["data"]["attachments"]}
        assert names == {"q1.pdf", "q2.pdf"}

    def test_student_sees_attachments_on_detail(self, api, lecturer, student, offering):
        api.force_authenticate(user=lecturer)
        f = make_file(lecturer)
        payload = assignment_payload()
        payload["attachmentFileIds"] = [str(f.id)]
        created = api.post(
            f"/api/v1/course-offerings/{offering.id}/assignments/",
            payload,
            format="json",
        )
        assignment_id = created.json()["data"]["id"]

        api.force_authenticate(user=student)
        res = api.get(f"/api/v1/assignments/{assignment_id}/")
        assert res.status_code == 200
        assert res.json()["data"]["attachments"][0]["originalName"] == "questions.pdf"
