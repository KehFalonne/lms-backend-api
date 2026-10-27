"""
Admin reports — aggregated data for the admin analytics dashboard.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from apps.assignments.models import Assignment, AssignmentSubmission, SubmissionStatus
from apps.assessments.models import Assessment, AssessmentAttempt, AttemptStatus
from apps.common.responses import success_response
from apps.courses.models import CourseEnrollment, CourseOffering, EnrollmentStatus
from apps.grading.models import Grade
from apps.university.models import Department, Faculty, Programme

User = get_user_model()


class ReportsOverviewView(APIView):
    """GET /api/v1/admin/reports/overview/"""

    serializer_class = None
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()
        six_months_ago = now - timedelta(days=180)

        # ── Enrollment trend (last 6 months, per month) ──────────
        trend_rows = (
            CourseEnrollment.objects.filter(enrolled_at__gte=six_months_ago)
            .annotate(month=TruncMonth("enrolled_at"))
            .values("month")
            .annotate(enrollments=Count("id"))
            .order_by("month")
        )

        enrollment_trend = []
        for row in trend_rows:
            month = row["month"]
            label = month.strftime("%b") if month else ""
            unique_students = (
                CourseEnrollment.objects.filter(
                    enrolled_at__year=month.year,
                    enrolled_at__month=month.month,
                )
                .values("student_id")
                .distinct()
                .count()
            )
            enrollment_trend.append(
                {
                    "period": label,
                    "enrollments": row["enrollments"],
                    "students": unique_students,
                }
            )

        # ── Course activity (top 8 by enrolled students) ─────────
        course_activity = []
        for offering in (
            CourseOffering.objects.annotate(
                active_students=Count(
                    "enrollments",
                    filter=__import__("django.db.models", fromlist=["Q"]).Q(
                        enrollments__status=EnrollmentStatus.ACTIVE
                    ),
                    distinct=True,
                ),
            )
            .select_related("course")
            .order_by("-active_students")[:8]
        ):
            subs_count = AssignmentSubmission.objects.filter(
                assignment__course_offering=offering,
            ).count()
            avg_pct = Grade.objects.filter(
                grade_item__course_offering=offering
            ).aggregate(avg=Avg("percentage"))["avg"]
            course_activity.append(
                {
                    "courseCode": offering.course.code,
                    "activeStudents": offering.active_students,
                    "submissions": subs_count,
                    "averageScore": float(avg_pct or 0),
                }
            )

        # ── Programme distribution ───────────────────────────────
        programme_distribution = []
        for prog in Programme.objects.annotate(
            student_count=Count("course_offerings__enrollments", distinct=True)
        ).order_by("-student_count")[:6]:
            programme_distribution.append(
                {
                    "programmeCode": prog.code,
                    "programmeName": prog.name,
                    "students": prog.student_count,
                }
            )

        # ── Faculty distribution ─────────────────────────────────
        faculty_distribution = []
        for fac in Faculty.objects.annotate(
            student_count=Count(
                "departments__courses__offerings__enrollments",
                distinct=True,
            ),
            staff_count=Count("departments__staff", distinct=True),
        ).order_by("code")[:8]:
            faculty_distribution.append(
                {
                    "facultyCode": fac.code,
                    "facultyName": fac.name,
                    "students": fac.student_count,
                    "staff": fac.staff_count,
                }
            )

        # ── Totals ───────────────────────────────────────────────
        totals = {
            "students": User.objects.filter(
                student_profile__isnull=False,
                is_active=True,
            ).count(),
            "staff": User.objects.filter(
                staff_profile__isnull=False,
                is_active=True,
            ).count(),
            "courses": CourseOffering.objects.filter(status="ACTIVE").count(),
            "programmes": Programme.objects.filter(status="ACTIVE").count(),
            "enrollments": CourseEnrollment.objects.filter(
                status=EnrollmentStatus.ACTIVE,
            ).count(),
        }

        return success_response(
            data={
                "totals": totals,
                "enrollmentTrend": enrollment_trend,
                "courseActivity": course_activity,
                "programmeDistribution": programme_distribution,
                "facultyDistribution": faculty_distribution,
            }
        )
