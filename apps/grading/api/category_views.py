from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import error_response, success_response
from apps.courses.models import CourseOffering
from apps.courses.permissions import CanGradeCourse
from apps.grading.models import GradeCategory
from apps.grading.serializers import (
    GradeCategorySerializer,
    SetWeightsSerializer,
)
from apps.grading.services.category_service import CategoryService


class OfferingCategoryListCreateView(APIView):
    """GET/POST /api/v1/course-offerings/{offering_id}/grade-categories/"""

    serializer_class = GradeCategorySerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticatedAndActive(), CanGradeCourse()]
        return super().get_permissions()

    def get(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        qs = offering.grade_categories.all()
        return success_response(data=GradeCategorySerializer(qs, many=True).data)

    def post(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        self.check_object_permissions(request, offering)
        serializer = GradeCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("course_offering", None)
        cat = GradeCategory.objects.create(
            course_offering=offering, **serializer.validated_data
        )
        return success_response(
            data=GradeCategorySerializer(cat).data,
            message="Grade category created.",
            status=status.HTTP_201_CREATED,
        )


class SetCategoryWeightsView(APIView):
    """PUT /api/v1/course-offerings/{offering_id}/grade-categories/set-weights/"""

    serializer_class = SetWeightsSerializer
    permission_classes = [IsAuthenticatedAndActive, CanGradeCourse]

    def put(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        self.check_object_permissions(request, offering)

        serializer = SetWeightsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            cats = CategoryService.set_weights(
                course_offering_id=offering.id,
                weights=serializer.validated_data["weights"],
            )
        except Exception as exc:
            detail = getattr(exc, "detail", str(exc))
            if isinstance(detail, dict):
                detail = "; ".join(
                    f"{k}: {', '.join(v) if isinstance(v, list) else v}"
                    for k, v in detail.items()
                )
            return error_response(str(detail), status_code=400)

        return success_response(
            data=GradeCategorySerializer(cats, many=True).data,
            message="Category weights set.",
        )


class GradeCategoryDetailView(APIView):
    """PATCH/DELETE /api/v1/grade-categories/{id}/"""

    serializer_class = GradeCategorySerializer
    permission_classes = [IsAuthenticatedAndActive, CanGradeCourse]

    def _get(self, pk):
        return get_object_or_404(GradeCategory, pk=pk)

    def patch(self, request, pk):
        cat = self._get(pk)
        self.check_object_permissions(request, cat.course_offering)
        serializer = GradeCategorySerializer(cat, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("course_offering", None)
        serializer.save()
        return success_response(data=GradeCategorySerializer(cat).data)

    def delete(self, request, pk):
        cat = self._get(pk)
        self.check_object_permissions(request, cat.course_offering)
        cat.delete()
        return success_response(message="Grade category deleted.")
