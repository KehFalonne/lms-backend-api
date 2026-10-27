"""
Student-facing cross-course assignment list.
"""

from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.assignments.models import (
    Assignment,
    AssignmentStatus,
    AssignmentSubmission,
)
from apps.common.responses import success_response
from apps.courses.models import CourseEnrollment, EnrollmentStatus


class MyAssignmentsView(APIView):
    """GET /api/v1/my/assignments/"""

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        offering_ids = CourseEnrollment.objects.filter(
            student=request.user,
            status=EnrollmentStatus.ACTIVE,
        ).values_list("course_offering_id", flat=True)

        assignments = (
            Assignment.objects.filter(
                course_offering_id__in=offering_ids,
                status=AssignmentStatus.PUBLISHED,
            )
            .select_related("course_offering__course")
            .order_by("-due_at")
        )

        submissions = {
            s.assignment_id: s
            for s in AssignmentSubmission.objects.filter(
                student=request.user,
                assignment__in=assignments,
            )
        }

        data = []
        for a in assignments:
            sub = submissions.get(a.id)
            data.append(
                {
                    "id": str(a.id),
                    "title": a.title,
                    "courseOfferingId": str(a.course_offering_id),
                    "courseCode": a.course_offering.course.code,
                    "courseTitle": a.course_offering.course.title,
                    "maxScore": str(a.max_score),
                    "dueAt": a.due_at.isoformat(),
                    "allowLateSubmission": a.allow_late_submission,
                    "submissionType": a.submission_type,
                    "status": a.status,
                    "mySubmission": (
                        {
                            "id": str(sub.id),
                            "status": sub.status,
                            "submittedAt": (
                                sub.submitted_at.isoformat()
                                if sub.submitted_at
                                else None
                            ),
                            "isLate": sub.is_late,
                            "score": (
                                str(sub.score) if sub.score is not None else None
                            ),
                        }
                        if sub
                        else None
                    ),
                }
            )

        return success_response(data=data)
