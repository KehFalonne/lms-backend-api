"""
Per-course-offering analytics for instructors.

Aggregates grades, submissions, assessment attempts, content progress and
learning events into chart-ready payloads.
"""

from datetime import timedelta

from django.db.models import Avg, Count, Max, Min
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.analytics.models import LearningEvent, StudentCourseProgress
from apps.assignments.models import Assignment, AssignmentSubmission, SubmissionStatus
from apps.assessments.models import Assessment, AssessmentAttempt, AttemptStatus
from apps.courses.models import (
    CourseEnrollment,
    CourseInstructor,
    CourseOffering,
    EnrollmentStatus,
)
from apps.grading.models import Grade, GradeStatus

GRADE_BUCKETS = [
    ("0-49", 0, 50),
    ("50-59", 50, 60),
    ("60-69", 60, 70),
    ("70-79", 70, 80),
    ("80-100", 80, 101),
]

EVENT_LABELS = {
    "COURSE_VIEWED": "Course viewed",
    "MODULE_VIEWED": "Module viewed",
    "CONTENT_VIEWED": "Content viewed",
    "CONTENT_COMPLETED": "Content completed",
    "PDF_OPENED": "PDF opened",
    "PDF_DOWNLOADED": "PDF downloaded",
    "ASSIGNMENT_OPENED": "Assignment opened",
    "ASSIGNMENT_SUBMITTED": "Assignment submitted",
    "ASSESSMENT_STARTED": "Assessment started",
    "ASSESSMENT_SUBMITTED": "Assessment submitted",
    "DISCUSSION_VIEWED": "Discussion viewed",
    "LOGIN": "Login",
}

SUBMITTED_ATTEMPT_STATUSES = (
    AttemptStatus.SUBMITTED,
    AttemptStatus.AUTO_GRADED,
    AttemptStatus.MANUAL_GRADING,
    AttemptStatus.GRADED,
)


def _pct(numerator, denominator, digits=2):
    if not denominator:
        return 0
    return round(numerator * 100 / denominator, digits)


class CourseAnalyticsService:

    @staticmethod
    def course_analytics(offering_id) -> dict:
        enrolled_students = list(
            CourseEnrollment.objects.filter(
                course_offering_id=offering_id,
                status=EnrollmentStatus.ACTIVE,
            ).values_list("student_id", flat=True)
        )
        enrolled_count = len(enrolled_students)

        # ── Overview ────────────────────────────────────────────────
        assignments = list(
            Assignment.objects.filter(
                course_offering_id=offering_id,
                status="PUBLISHED",
            )
        )
        assignment_ids = [a.id for a in assignments]

        submissions = AssignmentSubmission.objects.filter(
            assignment_id__in=assignment_ids,
        )
        submitted_count = submissions.filter(
            status__in=[SubmissionStatus.SUBMITTED, SubmissionStatus.LATE]
        ).count()
        expected_submissions = len(assignment_ids) * enrolled_count
        graded_submissions = submissions.filter(
            status__in=[SubmissionStatus.GRADED, SubmissionStatus.RETURNED]
        ).count()

        grades = Grade.objects.filter(
            grade_item__course_offering_id=offering_id,
            status=GradeStatus.PUBLISHED,
            percentage__isnull=False,
        )
        avg_grade = grades.aggregate(avg=Avg("percentage"))["avg"]

        attempts = AssessmentAttempt.objects.filter(
            assessment__course_offering_id=offering_id,
        )
        total_attempts = attempts.count()
        completed_attempts = attempts.filter(
            status__in=SUBMITTED_ATTEMPT_STATUSES
        ).count()

        progress_agg = StudentCourseProgress.objects.filter(
            course_offering_id=offering_id,
            student_id__in=enrolled_students,
        ).aggregate(avg=Avg("progress_percentage"))
        avg_progress = progress_agg["avg"] or 0

        thirty_days_ago = timezone.now() - timedelta(days=30)
        active_learner_ids = LearningEvent.objects.filter(
            course_offering_id=offering_id,
            student_id__in=enrolled_students,
            occurred_at__gte=thirty_days_ago,
        ).values_list("student_id", flat=True).distinct()

        overview = {
            "enrolledCount": enrolled_count,
            "assignmentCount": len(assignment_ids),
            "submittedCount": submitted_count,
            "expectedSubmissions": expected_submissions,
            "submissionRate": _pct(submitted_count, expected_submissions),
            "gradedCount": graded_submissions,
            "averageGradePct": round(float(avg_grade), 2) if avg_grade is not None else None,
            "assessmentAttempts": total_attempts,
            "completedAssessmentAttempts": completed_attempts,
            "assessmentCompletionRate": _pct(completed_attempts, total_attempts),
            "avgContentProgress": round(float(avg_progress), 2),
            "activeLearners30d": len(active_learner_ids),
        }

        # ── Grade distribution ──────────────────────────────────────
        grade_rows = list(grades.values_list("percentage", flat=True))
        distribution = []
        total_graded = len(grade_rows)
        for label, low, high in GRADE_BUCKETS:
            count = sum(1 for g in grade_rows if low <= float(g) < high)
            distribution.append(
                {
                    "bucket": label,
                    "count": count,
                    "share": _pct(count, total_graded),
                }
            )

        # ── Engagement ──────────────────────────────────────────────
        offering_events = LearningEvent.objects.filter(
            course_offering_id=offering_id,
        )
        events_by_type = [
            {
                "type": row["event_type"],
                "label": EVENT_LABELS.get(row["event_type"], row["event_type"]),
                "count": row["count"],
            }
            for row in offering_events.values("event_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        ]

        fourteen_days_ago = timezone.now() - timedelta(days=14)
        daily = (
            offering_events.filter(occurred_at__gte=fourteen_days_ago)
            .annotate(day=TruncDate("occurred_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )
        activity_by_day = [
            {"date": row["day"].isoformat(), "count": row["count"]} for row in daily
        ]

        # ── Recent activity feed ────────────────────────────────────
        recent_events = offering_events.select_related("student").order_by(
            "-occurred_at"
        )[:10]
        recent_activity = [
            {
                "id": str(e.id),
                "studentId": str(e.student_id) if e.student_id else None,
                "studentName": (
                    f"{e.student.first_name} {e.student.last_name}".strip()
                    if e.student_id
                    else "Unknown"
                ),
                "eventType": e.event_type,
                "label": EVENT_LABELS.get(e.event_type, e.event_type),
                "entityType": e.entity_type,
                "occurredAt": e.occurred_at.isoformat(),
            }
            for e in recent_events
        ]

        # ── Per-assessment performance ──────────────────────────────
        assessments = (
            Assessment.objects.filter(course_offering_id=offering_id)
            .order_by("available_from", "created_at")
        )
        assessment_performance = []
        for assessment in assessments:
            attempt_rows = AssessmentAttempt.objects.filter(
                assessment=assessment,
                status__in=SUBMITTED_ATTEMPT_STATUSES,
                percentage__gt=0,
            )
            stats = attempt_rows.aggregate(
                avg=Avg("percentage"),
                best=Max("percentage"),
                worst=Min("percentage"),
                graded_count=Count("id"),
            )
            total_for_assessment = attempts.filter(assessment=assessment).count()
            assessment_performance.append(
                {
                    "id": str(assessment.id),
                    "title": assessment.title,
                    "attempts": total_for_assessment,
                    "completed": stats["graded_count"],
                    "completionRate": _pct(
                        stats["graded_count"], total_for_assessment
                    ),
                    "avgPercentage": (
                        round(float(stats["avg"]), 2)
                        if stats["avg"] is not None
                        else None
                    ),
                    "bestPercentage": (
                        round(float(stats["best"]), 2)
                        if stats["best"] is not None
                        else None
                    ),
                    "worstPercentage": (
                        round(float(stats["worst"]), 2)
                        if stats["worst"] is not None
                        else None
                    ),
                }
            )

        return {
            "overview": overview,
            "gradeDistribution": distribution,
            "engagement": {
                "eventsByType": events_by_type,
                "activityByDay": activity_by_day,
            },
            "recentActivity": recent_activity,
            "assessments": assessment_performance,
        }

    @staticmethod
    def lecturer_analytics(user) -> dict:
        """Aggregates analytics across every offering a lecturer teaches."""
        offering_ids = list(
            CourseInstructor.objects.filter(user=user).values_list(
                "course_offering_id", flat=True
            )
        )
        offerings = list(
            CourseOffering.objects.filter(id__in=offering_ids)
            .select_related("course", "semester")
            .order_by("course__code", "section")
        )

        courses = []
        submitted_total = 0
        expected_total = 0
        attempts_total = 0
        completed_attempts_total = 0
        grade_counts = {label: 0 for label, _, _ in GRADE_BUCKETS}
        grade_total = 0
        activity_map = {}
        recent = []

        for offering in offerings:
            data = CourseAnalyticsService.course_analytics(offering.id)
            overview = data["overview"]
            courses.append(
                {
                    "id": str(offering.id),
                    "code": offering.course.code,
                    "title": offering.course.title,
                    "section": offering.section,
                    "semester": offering.semester.name,
                    "overview": overview,
                }
            )
            submitted_total += overview["submittedCount"]
            expected_total += overview["expectedSubmissions"]
            attempts_total += overview["assessmentAttempts"]
            completed_attempts_total += overview["completedAssessmentAttempts"]
            for bucket in data["gradeDistribution"]:
                grade_counts[bucket["bucket"]] += bucket["count"]
                grade_total += bucket["count"]
            for row in data["engagement"]["activityByDay"]:
                activity_map[row["date"]] = (
                    activity_map.get(row["date"], 0) + row["count"]
                )
            recent.extend(data["recentActivity"])

        avg_grade = Grade.objects.filter(
            grade_item__course_offering_id__in=offering_ids,
            status=GradeStatus.PUBLISHED,
            percentage__isnull=False,
        ).aggregate(avg=Avg("percentage"))["avg"]

        avg_progress = StudentCourseProgress.objects.filter(
            course_offering_id__in=offering_ids,
        ).aggregate(avg=Avg("progress_percentage"))["avg"]

        thirty_days_ago = timezone.now() - timedelta(days=30)
        active_learners = (
            LearningEvent.objects.filter(
                course_offering_id__in=offering_ids,
                occurred_at__gte=thirty_days_ago,
            )
            .values_list("student_id", flat=True)
            .distinct()
            .count()
        )

        recent.sort(key=lambda e: e["occurredAt"], reverse=True)

        return {
            "courses": courses,
            "totals": {
                "courseCount": len(courses),
                "enrolledCount": sum(
                    course["overview"]["enrolledCount"] for course in courses
                ),
                "submissionRate": _pct(submitted_total, expected_total),
                "averageGradePct": (
                    round(float(avg_grade), 2) if avg_grade is not None else None
                ),
                "assessmentCompletionRate": _pct(
                    completed_attempts_total, attempts_total
                ),
                "avgContentProgress": round(float(avg_progress), 2),
                "activeLearners30d": active_learners,
            },
            "gradeDistribution": [
                {
                    "bucket": label,
                    "count": grade_counts[label],
                    "share": _pct(grade_counts[label], grade_total),
                }
                for label, _, _ in GRADE_BUCKETS
            ],
            "activityByDay": [
                {"date": day, "count": count}
                for day, count in sorted(activity_map.items())
            ],
            "recentActivity": recent[:10],
        }
