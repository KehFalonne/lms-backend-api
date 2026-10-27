import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from apps.academics.models import AcademicYear, Semester
from apps.announcements.models import Announcement
from apps.courses.models import (
    Course,
    CourseInstructor,
    CourseOffering,
    TeachingRole,
)
from apps.discussions.models import DiscussionForum, DiscussionPost, DiscussionTopic
from apps.files.models import File
from apps.notifications.models import Notification
from apps.notifications.services.notification_service import NotificationService
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
        can_grade=True,
    )
    return o


class TestFiles:
    url = "/api/v1/files/upload-url/"

    def test_request_upload(self, api, student):
        api.force_authenticate(user=student)
        res = api.post(
            self.url,
            {"filename": "notes.pdf", "sizeBytes": 2048, "mimeType": "application/pdf"},
            format="json",
        )
        assert res.status_code == 200
        body = res.json()["data"]
        assert body["fileId"]
        assert body["uploadUrl"]
        assert File.objects.filter(id=body["fileId"]).exists()

    def test_reject_bad_extension(self, api, student):
        api.force_authenticate(user=student)
        res = api.post(
            self.url,
            {"filename": "malware.exe", "sizeBytes": 100},
            format="json",
        )
        assert res.status_code == 400

    def test_reject_oversize(self, api, student):
        api.force_authenticate(user=student)
        res = api.post(
            self.url,
            {"filename": "huge.pdf", "sizeBytes": 100 * 1024 * 1024},
            format="json",
        )
        assert res.status_code == 400


class TestAnnouncements:
    def _url(self, oid):
        return f"/api/v1/course-offerings/{oid}/announcements/"

    def test_lecturer_creates_announcement(self, api, lecturer, offering):
        api.force_authenticate(user=lecturer)
        res = api.post(
            self._url(offering.id),
            {"title": "Welcome", "body": "Let's get started.", "isPinned": True},
            format="json",
        )
        assert res.status_code == 201
        a_id = res.json()["data"]["id"]

        # Publish
        res = api.post(f"/api/v1/announcements/{a_id}/publish/")
        assert res.status_code == 200
        assert res.json()["data"]["status"] == "PUBLISHED"

    def test_student_sees_only_published(self, api, student, offering, lecturer):
        api.force_authenticate(user=lecturer)
        a1 = Announcement.objects.create(
            course_offering=offering,
            title="Draft",
            body="x",
            created_by=lecturer,
            status="DRAFT",
        )
        a2 = Announcement.objects.create(
            course_offering=offering,
            title="Live",
            body="y",
            created_by=lecturer,
            status="PUBLISHED",
        )
        api.force_authenticate(user=student)
        res = api.get(self._url(offering.id))
        assert res.status_code == 200
        ids = [a["id"] for a in res.json()["data"]]
        assert str(a2.id) in ids
        assert str(a1.id) not in ids


class TestDiscussions:
    def test_forum_topic_post_flow(self, api, lecturer, student, offering):
        api.force_authenticate(user=lecturer)
        # Create forum
        res = api.post(
            f"/api/v1/course-offerings/{offering.id}/forums/",
            {"title": "Q&A"},
            format="json",
        )
        assert res.status_code == 201
        forum_id = res.json()["data"]["id"]

        # Create topic
        api.force_authenticate(user=student)
        res = api.post(
            f"/api/v1/forums/{forum_id}/topics/",
            {"title": "Question about CSC101", "body": "Is the exam open book?"},
            format="json",
        )
        assert res.status_code == 201
        topic_id = res.json()["data"]["id"]

        # Reply
        res = api.post(
            f"/api/v1/topics/{topic_id}/posts/",
            {"body": "Yes, open book."},
            format="json",
        )
        assert res.status_code == 201

        # Threaded reply
        root_post_id = res.json()["data"]["id"]
        res = api.post(
            f"/api/v1/topics/{topic_id}/posts/",
            {"body": "Thanks!", "parentPost": root_post_id},
            format="json",
        )
        assert res.status_code == 201

        # Detail shows tree
        res = api.get(f"/api/v1/topics/{topic_id}/")
        assert res.status_code == 200
        assert "posts" in res.json()["data"]


class TestNotifications:
    def test_push_creates_and_lists(self, api, student):
        NotificationService.push(
            recipient=student,
            type="SYSTEM",
            title="Hello",
            message="Welcome to GU-LMS",
        )
        api.force_authenticate(user=student)
        res = api.get("/api/v1/notifications/")
        assert res.status_code == 200
        assert len(res.json()["data"]) == 1

    def test_mark_read(self, api, student):
        n = NotificationService.push(
            recipient=student,
            type="SYSTEM",
            title="x",
            message="y",
            broadcast=False,
        )
        api.force_authenticate(user=student)
        res = api.post(f"/api/v1/notifications/{n.id}/read/")
        assert res.status_code == 200
        n.refresh_from_db()
        assert n.read_at is not None

    def test_isolated_by_recipient(self, api, student, lecturer):
        NotificationService.push(
            recipient=student,
            type="SYSTEM",
            title="A",
            message="a",
            broadcast=False,
        )
        api.force_authenticate(user=lecturer)
        res = api.get("/api/v1/notifications/")
        assert len(res.json()["data"]) == 0
