"""
Gradebook grid — one call returns students × grade items × grades.
"""

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import error_response, success_response
from apps.courses.models import (
    CourseEnrollment,
    CourseInstructor,
    CourseOffering,
    EnrollmentStatus,
)
from apps.grading.models import Grade, GradeItem


class GradebookView(APIView):
    """GET /api/v1/course-offerings/{offering_id}/gradebook/"""

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)

        # Only instructors (or admin) can fetch the gradebook
        is_instructor = CourseInstructor.objects.filter(
            course_offering=offering,
            user=request.user,
        ).exists()
        if not is_instructor and not request.user.is_staff:
            return error_response(
                "You are not an instructor for this course.",
                status_code=403,
            )

        enrollments = (
            CourseEnrollment.objects.filter(
                course_offering=offering, status=EnrollmentStatus.ACTIVE
            )
            .select_related("student")
            .order_by("student__last_name", "student__first_name")
        )
        student_ids = [e.student_id for e in enrollments]

        items = (
            GradeItem.objects.filter(course_offering=offering)
            .select_related("category")
            .order_by("category__position", "position")
        )
        item_ids = [i.id for i in items]

        grades = Grade.objects.filter(
            grade_item_id__in=item_ids,
            student_id__in=student_ids,
        )
        grade_map = {
            (g.grade_item_id, g.student_id): {
                "id": str(g.id),
                "score": str(g.score) if g.score is not None else None,
                "percentage": str(g.percentage) if g.percentage is not None else None,
                "status": g.status,
                "letterGrade": g.letter_grade,
                "feedback": g.feedback,
            }
            for g in grades
        }

        # Build rows
        rows = []
        for enr in enrollments:
            student_grades = {}
            scores_by_item = {}
            for item in items:
                key = (item.id, enr.student_id)
                student_grades[str(item.id)] = grade_map.get(
                    key,
                    {
                        "id": None,
                        "score": None,
                        "percentage": None,
                        "status": "MISSING",
                        "letterGrade": "",
                        "feedback": "",
                    },
                )
                if grade_map.get(key):
                    scores_by_item[str(item.id)] = grade_map[key]

            rows.append(
                {
                    "studentId": str(enr.student_id),
                    "studentName": f"{enr.student.first_name} {enr.student.last_name}",
                    "studentNumber": enr.student.university_id,
                    "grades": student_grades,
                }
            )

        return success_response(
            data={
                "items": [
                    {
                        "id": str(i.id),
                        "name": i.name,
                        "maxScore": str(i.max_score),
                        "categoryId": str(i.category_id) if i.category_id else None,
                        "categoryName": i.category.name if i.category else None,
                        "isPublished": i.is_published,
                        "position": i.position,
                    }
                    for i in items
                ],
                "students": rows,
            }
        )
