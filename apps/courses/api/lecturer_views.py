"""
Lecturer-facing endpoints.
"""

from django.db.models import Count
from django.utils import timezone
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.assignments.models import (
    Assignment,
    AssignmentSubmission,
    SubmissionStatus,
)
from apps.assessments.models import Assessment, AssessmentStatus
from apps.common.responses import success_response
from apps.courses.models import (
    CourseEnrollment,
    CourseInstructor,
    CourseOffering,
    EnrollmentStatus,
)


class MyTeachingCoursesView(APIView):
    """GET /api/v1/my/teaching-courses/"""

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        links = (
            CourseInstructor.objects.filter(user=request.user)
            .select_related(
                "course_offering",
                "course_offering__course",
                "course_offering__semester",
                "course_offering__programme",
            )
            .order_by("course_offering__course__code")
        )

        data = []
        for link in links:
            o = link.course_offering
            data.append(
                {
                    "id": str(o.id),
                    "course": {
                        "id": str(o.course_id),
                        "code": o.course.code,
                        "title": o.course.title,
                        "credits": o.course.credits,
                        "level": o.course.level,
                    },
                    "semester": {
                        "id": str(o.semester_id),
                        "name": o.semester.name,
                    },
                    "programme": {
                        "id": str(o.programme_id),
                        "name": o.programme.name,
                    },
                    "section": o.section,
                    "status": o.status,
                    "teachingRole": link.teaching_role,
                    "canGrade": link.can_grade,
                    "canManageContent": link.can_manage_content,
                    "studentCount": CourseEnrollment.objects.filter(
                        course_offering=o,
                        status=EnrollmentStatus.ACTIVE,
                    ).count(),
                    "assignmentCount": Assignment.objects.filter(
                        course_offering=o,
                    ).count(),
                    "assessmentCount": Assessment.objects.filter(
                        course_offering=o,
                    ).count(),
                    "pendingSubmissions": AssignmentSubmission.objects.filter(
                        assignment__course_offering=o,
                        status__in=[SubmissionStatus.SUBMITTED, SubmissionStatus.LATE],
                    ).count(),
                }
            )

        return success_response(data=data)


class LecturerDashboardStatsView(APIView):
    """GET /api/v1/lecturer/dashboard/stats/"""

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        offering_ids = list(
            CourseInstructor.objects.filter(user=request.user).values_list(
                "course_offering_id", flat=True
            )
        )

        active_courses = CourseOffering.objects.filter(
            id__in=offering_ids,
            status="ACTIVE",
        ).count()

        total_students = (
            CourseEnrollment.objects.filter(
                course_offering_id__in=offering_ids,
                status=EnrollmentStatus.ACTIVE,
            )
            .values("student_id")
            .distinct()
            .count()
        )

        pending_submissions = AssignmentSubmission.objects.filter(
            assignment__course_offering_id__in=offering_ids,
            status__in=[SubmissionStatus.SUBMITTED, SubmissionStatus.LATE],
        ).count()

        upcoming = (
            Assessment.objects.filter(
                course_offering_id__in=offering_ids,
                status=AssessmentStatus.PUBLISHED,
                available_from__gte=timezone.now(),
            )
            .select_related("course_offering__course")
            .order_by("available_from")[:5]
        )

        recent_subs = (
            AssignmentSubmission.objects.filter(
                assignment__course_offering_id__in=offering_ids,
                status__in=[SubmissionStatus.SUBMITTED, SubmissionStatus.LATE],
            )
            .select_related(
                "student",
                "assignment",
                "assignment__course_offering__course",
            )
            .order_by("-submitted_at")[:10]
        )

        # ── CRITICAL: return the correct shape, NOT an array ──
        return success_response(
            data={
                "stats": {
                    "activeCourses": active_courses,
                    "totalStudents": total_students,
                    "pendingSubmissions": pending_submissions,
                },
                "upcomingAssessments": [
                    {
                        "id": str(a.id),
                        "title": a.title,
                        "availableFrom": (
                            a.available_from.isoformat() if a.available_from else None
                        ),
                        "courseOfferingId": str(a.course_offering_id),
                        "courseCode": a.course_offering.course.code,
                    }
                    for a in upcoming
                ],
                "recentSubmissions": [
                    {
                        "id": str(s.id),
                        "studentName": (
                            f"{s.student.first_name} {s.student.last_name}"
                        ),
                        "studentId": str(s.student_id),
                        "assignmentTitle": s.assignment.title,
                        "assignmentId": str(s.assignment_id),
                        "courseCode": s.assignment.course_offering.course.code,
                        "submittedAt": (
                            s.submitted_at.isoformat() if s.submitted_at else None
                        ),
                        "isLate": s.is_late,
                        "status": s.status,
                    }
                    for s in recent_subs
                ],
            }
        )
