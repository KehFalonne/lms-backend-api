from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.analytics.services.course_analytics_service import CourseAnalyticsService
from apps.common.responses import error_response, success_response
from apps.courses.models import CourseInstructor


class CourseAnalyticsView(APIView):
    """
    GET /api/v1/course-offerings/{offering_id}/analytics/

    Performance and engagement insights for the instructors of an offering.
    """

    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, offering_id):
        instructor = CourseInstructor.objects.filter(
            course_offering_id=offering_id,
            user=request.user,
        ).exists()
        if not instructor and not request.user.is_staff:
            return error_response(
                "You are not an instructor for this course.",
                status_code=403,
            )

        data = CourseAnalyticsService.course_analytics(offering_id)
        return success_response(data=data)


class LecturerAnalyticsView(APIView):
    """
    GET /api/v1/lecturer/analytics/

    Analytics aggregated across every offering the lecturer teaches.
    """

    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        if not CourseInstructor.objects.filter(user=request.user).exists() and not request.user.is_staff:
            return error_response(
                "You are not teaching any courses.",
                status_code=403,
            )

        data = CourseAnalyticsService.lecturer_analytics(request.user)
        return success_response(data=data)
