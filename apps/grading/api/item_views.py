from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import success_response
from apps.courses.models import CourseOffering
from apps.courses.permissions import CanGradeCourse
from apps.grading.models import GradeItem
from apps.grading.serializers import GradeItemSerializer
from apps.grading.services.grade_service import GradeService


class OfferingGradeItemListCreateView(APIView):
    """GET/POST /api/v1/course-offerings/{offering_id}/grade-items/"""

    serializer_class = GradeItemSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticatedAndActive(), CanGradeCourse()]
        return super().get_permissions()

    def get(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        qs = offering.grade_items.select_related("category").all()
        return success_response(data=GradeItemSerializer(qs, many=True).data)

    def post(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        self.check_object_permissions(request, offering)
        serializer = GradeItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("course_offering", None)
        item = GradeItem.objects.create(
            course_offering=offering, **serializer.validated_data
        )
        return success_response(
            data=GradeItemSerializer(item).data,
            message="Grade item created.",
            status=status.HTTP_201_CREATED,
        )


class GradeItemDetailView(APIView):
    """PATCH/DELETE /api/v1/grade-items/{id}/"""

    serializer_class = GradeItemSerializer
    permission_classes = [IsAuthenticatedAndActive, CanGradeCourse]

    def _get(self, pk):
        return get_object_or_404(GradeItem, pk=pk)

    def patch(self, request, pk):
        item = self._get(pk)
        self.check_object_permissions(request, item.course_offering)
        serializer = GradeItemSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("course_offering", None)
        serializer.save()
        return success_response(data=GradeItemSerializer(item).data)

    def delete(self, request, pk):
        item = self._get(pk)
        self.check_object_permissions(request, item.course_offering)
        item.delete()
        return success_response(message="Grade item deleted.")


class PublishGradeItemView(APIView):
    """POST /api/v1/grade-items/{id}/publish/"""

    serializer_class = GradeItemSerializer
    permission_classes = [IsAuthenticatedAndActive, CanGradeCourse]

    def _get(self, pk):
        return get_object_or_404(GradeItem, pk=pk)

    def post(self, request, pk):
        item = self._get(pk)
        self.check_object_permissions(request, item.course_offering)
        count = GradeService.publish_grade_item(grade_item=item, by=request.user)
        return success_response(
            data={"published": count, "gradeItemId": str(item.id)},
            message=f"{count} grade(s) published.",
        )


class PublishOfferingGradesView(APIView):
    """POST /api/v1/course-offerings/{offering_id}/grades/publish/"""

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive, CanGradeCourse]

    def post(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        self.check_object_permissions(request, offering)
        count = GradeService.publish_all_for_offering(
            course_offering_id=offering.id,
            by=request.user,
        )
        return success_response(
            data={"published": count},
            message=f"{count} grade(s) published.",
        )
