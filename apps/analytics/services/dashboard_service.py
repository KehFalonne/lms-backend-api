"""
Aggregates metrics for the three dashboards.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from datetime import timedelta

from apps.analytics.models import LearningEvent, StudentCourseProgress
from apps.assignments.models import Assignment, AssignmentSubmission, SubmissionStatus
from apps.assessments.models import Assessment, AssessmentAttempt
from apps.courses.models import CourseEnrollment, CourseOffering, EnrollmentStatus
from apps.grading.models import Grade, GradeStatus

User = get_user_model()


class DashboardService:

    # ────────────────────────────────────────────────────────────────
    # Student
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def student_dashboard(user) -> dict:
        enrollments = CourseEnrollment.objects.filter(
            student=user,
            status=EnrollmentStatus.ACTIVE,
        ).select_related("course_offering__course", "course_offering__semester")
        offering_ids = [e.course_offering_id for e in enrollments]

        assignments_due = Assignment.objects.filter(
            course_offering_id__in=offering_ids,
            status="PUBLISHED",
            due_at__gte=timezone.now(),
        ).order_by("due_at")[:5]

        recent_grades = Grade.objects.filter(
            student=user,
            status=GradeStatus.PUBLISHED,
        ).order_by("-published_at")[:5]

        progress = StudentCourseProgress.objects.filter(
            student=user,
            course_offering_id__in=offering_ids,
        )

        return {
            "courses": [
                {
                    "courseOfferingId": str(e.course_offering_id),
                    "courseCode": e.course_offering.course.code,
                    "courseTitle": e.course_offering.course.title,
                    "semester": e.course_offering.semester.name,
                }
                for e in enrollments
            ],
            "upcomingAssignments": [
                {
                    "id": str(a.id),
                    "title": a.title,
                    "dueAt": a.due_at.isoformat(),
                    "courseOfferingId": str(a.course_offering_id),
                }
                for a in assignments_due
            ],
            "recentGrades": [
                {
                    "gradeItemId": str(g.grade_item_id),
                    "score": str(g.score),
                    "maxScore": str(g.grade_item.max_score),
                    "percentage": str(g.percentage),
                }
                for g in recent_grades
            ],
            "progress": [
                {
                    "courseOfferingId": str(p.course_offering_id),
                    "percentage": str(p.progress_percentage),
                    "completed": p.content_completed,
                    "total": p.content_total,
                }
                for p in progress
            ],
        }

    # ────────────────────────────────────────────────────────────────
    # Lecturer
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def lecturer_dashboard(user) -> dict:
        from apps.courses.models import CourseInstructor

        offering_ids = CourseInstructor.objects.filter(user=user).values_list(
            "course_offering_id", flat=True
        )

        offerings = CourseOffering.objects.filter(id__in=offering_ids).select_related(
            "course",
            "semester",
        )

        enrollments_count = CourseEnrollment.objects.filter(
            course_offering_id__in=offering_ids,
            status=EnrollmentStatus.ACTIVE,
        ).count()

        pending_submissions = AssignmentSubmission.objects.filter(
            assignment__course_offering_id__in=offering_ids,
            status__in=[SubmissionStatus.SUBMITTED, SubmissionStatus.LATE],
        ).count()

        upcoming_assessments = Assessment.objects.filter(
            course_offering_id__in=offering_ids,
            status="PUBLISHED",
            available_from__gte=timezone.now(),
        ).order_by("available_from")[:5]

        return {
            "courses": [
                {
                    "id": str(o.id),
                    "courseCode": o.course.code,
                    "courseTitle": o.course.title,
                    "semester": o.semester.name,
                    "enrolled": CourseEnrollment.objects.filter(
                        course_offering=o, status=EnrollmentStatus.ACTIVE
                    ).count(),
                }
                for o in offerings
            ],
            "stats": {
                "activeCourses": offerings.count(),
                "students": enrollments_count,
                "pendingSubmissions": pending_submissions,
                "pendingGrades": pending_submissions,  # approximation
            },
            "upcomingAssessments": [
                {
                    "id": str(a.id),
                    "title": a.title,
                    "availableFrom": (
                        a.available_from.isoformat() if a.available_from else None
                    ),
                    "courseOfferingId": str(a.course_offering_id),
                }
                for a in upcoming_assessments
            ],
        }

    # ────────────────────────────────────────────────────────────────
    # Administrator
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def admin_dashboard() -> dict:
        return {
            "totals": {
                "students": User.objects.filter(
                    student_profile__isnull=False,
                    is_active=True,
                ).count(),
                "staff": User.objects.filter(
                    staff_profile__isnull=False,
                    is_active=True,
                ).count(),
                "activeCourses": CourseOffering.objects.filter(
                    status="ACTIVE",
                ).count(),
                "activeProgrammes": __import__(
                    "apps.university.models", fromlist=["Programme"]
                )
                .Programme.objects.filter(status="ACTIVE")
                .count(),
            },
        }
