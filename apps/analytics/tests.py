from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.analytics.api.analytics_views import CourseAnalyticsView, LecturerAnalyticsView
from apps.analytics.api.progress_views import ContentProgressView
from apps.analytics.models import ContentProgress, LearningEvent, StudentCourseProgress
from apps.academics.models import AcademicYear, Semester
from apps.assignments.models import Assignment, AssignmentSubmission
from apps.assessments.models import Assessment, AssessmentAttempt
from apps.content.models import ContentItem, CourseModule, ContentType
from apps.courses.models import (
    Course,
    CourseEnrollment,
    CourseInstructor,
    CourseOffering,
    EnrollmentStatus,
)
from apps.grading.models import Grade, GradeItem
from apps.university.models import Department, Faculty, Programme


class ContentProgressGradingIsolationTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.student = User.objects.create_user(
            email="student@example.com",
            university_id="GU2026001",
            password="test-password",
            first_name="Test",
            last_name="Student",
            status="ACTIVE",
        )
        faculty = Faculty.objects.create(code="SCI", name="Science")
        department = Department.objects.create(
            faculty=faculty, code="CS", name="Computer Science"
        )
        programme = Programme.objects.create(
            department=department, code="BSC-CS", name="Computer Science"
        )
        academic_year = AcademicYear.objects.create(
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 8, 31),
            is_current=True,
        )
        semester = Semester.objects.create(
            academic_year=academic_year,
            name="First Semester",
            code="S1",
            sequence=1,
            start_date=date(2026, 9, 1),
            end_date=date(2027, 1, 31),
            is_current=True,
        )
        course = Course.objects.create(
            department=department,
            code="CSC101",
            title="Introduction to Computing",
        )
        self.offering = CourseOffering.objects.create(
            course=course,
            semester=semester,
            programme=programme,
            status="ACTIVE",
        )
        CourseEnrollment.objects.create(
            student=self.student,
            course_offering=self.offering,
            status=EnrollmentStatus.ACTIVE,
        )
        module = CourseModule.objects.create(
            course_offering=self.offering,
            title="Module 1",
            position=1,
            is_published=True,
            created_by=self.student,
        )
        self.required_video = ContentItem.objects.create(
            course_module=module,
            title="Required video",
            content_type=ContentType.VIDEO,
            external_url="https://example.com/video.mp4",
            is_required=True,
            is_published=True,
            position=1,
            created_by=self.student,
        )
        self.optional_video = ContentItem.objects.create(
            course_module=module,
            title="Optional video",
            content_type=ContentType.VIDEO,
            external_url="https://example.com/optional.mp4",
            is_required=False,
            is_published=True,
            position=2,
            created_by=self.student,
        )

    def put_progress(self, item, **payload):
        request = self.factory.put(
            f"/api/v1/content/{item.id}/progress/",
            payload,
            format="json",
        )
        force_authenticate(request, user=self.student)
        return ContentProgressView.as_view()(request, content_id=item.id)

    def test_completion_does_not_create_academic_grade(self):
        response = self.put_progress(
            self.required_video,
            status="COMPLETED",
            progressPercent=90,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ContentProgress.objects.get(
                student=self.student, content_item=self.required_video
            ).status,
            "COMPLETED",
        )
        self.assertEqual(Grade.objects.count(), 0)
        self.assertEqual(GradeItem.objects.count(), 0)

    def test_required_video_cannot_complete_below_ninety_percent(self):
        response = self.put_progress(
            self.required_video,
            status="COMPLETED",
            progressPercent=89,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            ContentProgress.objects.filter(
                student=self.student, content_item=self.required_video
            ).exists()
        )
        self.assertEqual(Grade.objects.count(), 0)

    def test_optional_video_can_complete_without_academic_mark(self):
        response = self.put_progress(
            self.optional_video,
            status="COMPLETED",
            progressPercent=1,
        )

        self.assertEqual(response.status_code, 200)
        progress = ContentProgress.objects.get(
            student=self.student, content_item=self.optional_video
        )
        self.assertEqual(progress.status, "COMPLETED")
        self.assertEqual(progress.progress_percent, 1)
        self.assertEqual(Grade.objects.count(), 0)


class CourseAnalyticsViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.lecturer = User.objects.create_user(
            email="lecturer@example.com",
            university_id="GU2026100",
            password="test-password",
            first_name="Ada",
            last_name="Lecturer",
            status="ACTIVE",
        )
        self.student = User.objects.create_user(
            email="student@example.com",
            university_id="GU2026001",
            password="test-password",
            first_name="Test",
            last_name="Student",
            status="ACTIVE",
        )
        faculty = Faculty.objects.create(code="SCI", name="Science")
        department = Department.objects.create(
            faculty=faculty, code="CS", name="Computer Science"
        )
        programme = Programme.objects.create(
            department=department, code="BSC-CS", name="Computer Science"
        )
        academic_year = AcademicYear.objects.create(
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 8, 31),
            is_current=True,
        )
        semester = Semester.objects.create(
            academic_year=academic_year,
            name="First Semester",
            code="S1",
            sequence=1,
            start_date=date(2026, 9, 1),
            end_date=date(2027, 1, 31),
            is_current=True,
        )
        course = Course.objects.create(
            department=department,
            code="CSC101",
            title="Introduction to Computing",
        )
        self.offering = CourseOffering.objects.create(
            course=course,
            semester=semester,
            programme=programme,
            status="ACTIVE",
        )
        CourseInstructor.objects.create(
            course_offering=self.offering,
            user=self.lecturer,
            teaching_role="PRIMARY_INSTRUCTOR",
        )
        CourseEnrollment.objects.create(
            student=self.student,
            course_offering=self.offering,
            status=EnrollmentStatus.ACTIVE,
        )

        assignment = Assignment.objects.create(
            course_offering=self.offering,
            title="Assignment 1",
            max_score=20,
            due_at=timezone.now() + timedelta(days=3),
            status="PUBLISHED",
        )
        AssignmentSubmission.objects.create(
            assignment=assignment,
            student=self.student,
            status="SUBMITTED",
            score=16,
        )

        assessment = Assessment.objects.create(
            course_offering=self.offering,
            title="Midterm CA",
            status="PUBLISHED",
        )
        AssessmentAttempt.objects.create(
            assessment=assessment,
            student=self.student,
            status="GRADED",
            total_score=45,
            percentage=75,
        )

        grade_item = GradeItem.objects.create(
            course_offering=self.offering,
            name="Assignment 1",
            max_score=20,
        )
        Grade.objects.create(
            grade_item=grade_item,
            student=self.student,
            score=16,
            percentage=80,
            letter_grade="A",
            status="PUBLISHED",
        )

        StudentCourseProgress.objects.create(
            student=self.student,
            course_offering=self.offering,
            progress_percentage=60,
            content_completed=3,
            content_total=5,
        )
        LearningEvent.objects.create(
            student=self.student,
            course_offering=self.offering,
            event_type="CONTENT_VIEWED",
            entity_type="content_item",
        )

    def get_analytics(self, user):
        request = self.factory.get(
            f"/api/v1/course-offerings/{self.offering.id}/analytics/"
        )
        force_authenticate(request, user=user)
        return CourseAnalyticsView.as_view()(request, offering_id=self.offering.id)

    def test_instructor_receives_overview_and_distribution(self):
        response = self.get_analytics(self.lecturer)

        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        overview = data["overview"]
        self.assertEqual(overview["enrolledCount"], 1)
        self.assertEqual(overview["submissionRate"], 100.0)
        self.assertEqual(overview["averageGradePct"], 80.0)
        self.assertEqual(overview["assessmentCompletionRate"], 100.0)
        self.assertEqual(overview["avgContentProgress"], 60.0)
        self.assertEqual(overview["activeLearners30d"], 1)

        distribution = data["gradeDistribution"]
        self.assertEqual(len(distribution), 5)
        self.assertEqual(distribution[4]["count"], 1)  # 80-100 bucket
        self.assertEqual(distribution[4]["share"], 100.0)

        self.assertEqual(len(data["recentActivity"]), 1)
        self.assertEqual(
            data["recentActivity"][0]["studentName"], "Test Student"
        )
        self.assertEqual(len(data["assessments"]), 1)
        self.assertEqual(data["assessments"][0]["avgPercentage"], 75.0)

    def test_student_is_forbidden(self):
        response = self.get_analytics(self.student)

        self.assertEqual(response.status_code, 403)


class LecturerAnalyticsViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.lecturer = User.objects.create_user(
            email="lecturer@example.com",
            university_id="GU2026100",
            password="test-password",
            first_name="Ada",
            last_name="Lecturer",
            status="ACTIVE",
        )
        self.student = User.objects.create_user(
            email="student@example.com",
            university_id="GU2026001",
            password="test-password",
            first_name="Test",
            last_name="Student",
            status="ACTIVE",
        )
        faculty = Faculty.objects.create(code="SCI", name="Science")
        department = Department.objects.create(
            faculty=faculty, code="CS", name="Computer Science"
        )
        programme = Programme.objects.create(
            department=department, code="BSC-CS", name="Computer Science"
        )
        academic_year = AcademicYear.objects.create(
            name="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 8, 31),
            is_current=True,
        )
        semester = Semester.objects.create(
            academic_year=academic_year,
            name="First Semester",
            code="S1",
            sequence=1,
            start_date=date(2026, 9, 1),
            end_date=date(2027, 1, 31),
            is_current=True,
        )
        course = Course.objects.create(
            department=department,
            code="CSC101",
            title="Introduction to Computing",
        )
        self.offering = CourseOffering.objects.create(
            course=course,
            semester=semester,
            programme=programme,
            status="ACTIVE",
        )
        CourseInstructor.objects.create(
            course_offering=self.offering,
            user=self.lecturer,
            teaching_role="PRIMARY_INSTRUCTOR",
        )
        CourseEnrollment.objects.create(
            student=self.student,
            course_offering=self.offering,
            status=EnrollmentStatus.ACTIVE,
        )

        assignment = Assignment.objects.create(
            course_offering=self.offering,
            title="Assignment 1",
            max_score=20,
            due_at=timezone.now() + timedelta(days=3),
            status="PUBLISHED",
        )
        AssignmentSubmission.objects.create(
            assignment=assignment,
            student=self.student,
            status="SUBMITTED",
            score=16,
        )

        grade_item = GradeItem.objects.create(
            course_offering=self.offering,
            name="Assignment 1",
            max_score=20,
        )
        Grade.objects.create(
            grade_item=grade_item,
            student=self.student,
            score=16,
            percentage=80,
            letter_grade="A",
            status="PUBLISHED",
        )

        StudentCourseProgress.objects.create(
            student=self.student,
            course_offering=self.offering,
            progress_percentage=60,
            content_completed=3,
            content_total=5,
        )
        LearningEvent.objects.create(
            student=self.student,
            course_offering=self.offering,
            event_type="CONTENT_VIEWED",
            entity_type="content_item",
        )

    def get_lecturer_analytics(self, user):
        request = self.factory.get("/api/v1/lecturer/analytics/")
        force_authenticate(request, user=user)
        return LecturerAnalyticsView.as_view()(request)

    def test_lecturer_receives_aggregate_totals(self):
        response = self.get_lecturer_analytics(self.lecturer)

        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        totals = data["totals"]
        self.assertEqual(totals["courseCount"], 1)
        self.assertEqual(totals["enrolledCount"], 1)
        self.assertEqual(totals["submissionRate"], 100.0)
        self.assertEqual(totals["averageGradePct"], 80.0)
        self.assertEqual(totals["avgContentProgress"], 60.0)
        self.assertEqual(totals["activeLearners30d"], 1)

        self.assertEqual(len(data["courses"]), 1)
        self.assertEqual(data["courses"][0]["code"], "CSC101")
        self.assertEqual(data["courses"][0]["overview"]["enrolledCount"], 1)

        self.assertEqual(len(data["gradeDistribution"]), 5)
        self.assertEqual(data["gradeDistribution"][4]["count"], 1)
        self.assertEqual(len(data["activityByDay"]), 1)
        self.assertEqual(len(data["recentActivity"]), 1)
        self.assertEqual(
            data["recentActivity"][0]["studentName"], "Test Student"
        )

    def test_non_teacher_is_forbidden(self):
        response = self.get_lecturer_analytics(self.student)

        self.assertEqual(response.status_code, 403)
