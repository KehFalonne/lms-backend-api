from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import error_response, success_response
from apps.courses.models import CourseInstructor, CourseOffering
from apps.courses.permissions import IsCourseInstructor
from apps.courses.serializers import CourseInstructorSerializer


class OfferingInstructorListCreateView(APIView):
    """
    GET  /api/v1/course-offerings/{offering_id}/instructors/
    POST /api/v1/course-offerings/{offering_id}/instructors/
    """

    serializer_class = CourseInstructorSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticatedAndActive(), IsCourseInstructor()]
        return super().get_permissions()

    def get(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        qs = offering.instructors.select_related("user").all()
        return success_response(data=CourseInstructorSerializer(qs, many=True).data)

    def post(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        self.check_object_permissions(request, offering)

        serializer = CourseInstructorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data.pop("user_id")
        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return error_response("User not found.", status_code=400)

        if CourseInstructor.objects.filter(
            course_offering=offering,
            user=user,
            teaching_role=serializer.validated_data["teaching_role"],
        ).exists():
            return error_response(
                "This instructor is already assigned with the same role.",
                status_code=409,
            )

        instructor = CourseInstructor.objects.create(
            course_offering=offering,
            user=user,
            assigned_by=request.user,
            **serializer.validated_data,
        )
        return success_response(
            data=CourseInstructorSerializer(instructor).data,
            message="Instructor assigned.",
            status=status.HTTP_201_CREATED,
        )


class InstructorDetailView(APIView):
    """
    PATCH  /api/v1/course-offerings/{offering_id}/instructors/{instructor_id}/
    DELETE /api/v1/course-offerings/{offering_id}/instructors/{instructor_id}/
    """

    serializer_class = CourseInstructorSerializer
    permission_classes = [IsAuthenticatedAndActive, IsCourseInstructor]

    def _get(self, offering_id, instructor_id):
        return get_object_or_404(
            CourseInstructor,
            pk=instructor_id,
            course_offering_id=offering_id,
        )

    def patch(self, request, offering_id, instructor_id):
        instructor = self._get(offering_id, instructor_id)
        self.check_object_permissions(request, instructor.course_offering)
        serializer = CourseInstructorSerializer(
            instructor,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("user_id", None)
        serializer.save()
        return success_response(
            data=CourseInstructorSerializer(instructor).data,
            message="Instructor updated.",
        )

    def delete(self, request, offering_id, instructor_id):
        instructor = self._get(offering_id, instructor_id)
        self.check_object_permissions(request, instructor.course_offering)
        instructor.delete()
        return success_response(message="Instructor removed.")
