from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import success_response
from apps.courses.models import Course, CoursePrerequisite
from apps.courses.serializers import CoursePrerequisiteSerializer, CourseSerializer
from apps.university.models import Department


class CourseViewSet(viewsets.ModelViewSet):
    queryset = (
        Course.objects.select_related("department", "department__faculty")
        .annotate(prerequisite_count=Count("prerequisites", distinct=True))
        .filter(deleted_at__isnull=True)
    )
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticatedAndActive]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["department", "status", "level", "course_type"]
    search_fields = ["code", "title", "description"]
    ordering_fields = ["code", "level", "credits", "created_at"]
    ordering = ["code"]

    def get_permissions(self):
        if self.action in (
            "create",
            "update",
            "partial_update",
            "destroy",
            "prerequisites",
            "delete_prerequisite",
        ):
            return [IsAdminUser()]
        return super().get_permissions()

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(
                self.get_serializer(page, many=True).data
            )
        return success_response(data=self.get_serializer(qs, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        department_id = serializer.validated_data.pop("department_id")
        try:
            department = Department.objects.get(
                pk=department_id, deleted_at__isnull=True
            )
        except Department.DoesNotExist:
            return success_response(
                message="Department not found.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = Course.objects.create(
            department=department, **serializer.validated_data
        )
        fresh = self.get_queryset().get(pk=instance.pk)
        return success_response(
            data=self.get_serializer(fresh).data,
            message="Course created successfully.",
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        department_id = serializer.validated_data.pop("department_id", None)
        if department_id:
            try:
                instance.department = Department.objects.get(
                    pk=department_id,
                    deleted_at__isnull=True,
                )
            except Department.DoesNotExist:
                return success_response(
                    message="Department not found.",
                    status=status.HTTP_400_BAD_REQUEST,
                )
        for k, v in serializer.validated_data.items():
            setattr(instance, k, v)
        instance.save()
        fresh = self.get_queryset().get(pk=instance.pk)
        return success_response(
            data=self.get_serializer(fresh).data,
            message="Course updated successfully.",
        )

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return success_response(message="Course deleted successfully.")

    # ── /courses/{id}/prerequisites/ ─────────────────────────────────

    @action(detail=True, methods=["get", "post"], url_path="prerequisites")
    def prerequisites(self, request, pk=None):
        course = self.get_object()

        if request.method == "GET":
            qs = course.prerequisites.select_related("prerequisite_course")
            return success_response(
                data=CoursePrerequisiteSerializer(qs, many=True).data
            )

        # POST
        serializer = CoursePrerequisiteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        prereq_id = serializer.validated_data["prerequisite_course_id"]

        if str(prereq_id) == str(course.id):
            return success_response(
                message="A course cannot be a prerequisite of itself.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            prerequisite = Course.objects.get(pk=prereq_id, deleted_at__isnull=True)
        except Course.DoesNotExist:
            return success_response(
                message="Prerequisite course not found.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        if CoursePrerequisite.objects.filter(
            course=course, prerequisite_course=prerequisite
        ).exists():
            return success_response(
                message="This prerequisite already exists.",
                status=status.HTTP_409_CONFLICT,
            )
        instance = CoursePrerequisite.objects.create(
            course=course,
            prerequisite_course=prerequisite,
            minimum_grade=serializer.validated_data.get("minimum_grade", ""),
        )
        return success_response(
            data=CoursePrerequisiteSerializer(instance).data,
            message="Prerequisite added.",
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"prerequisites/(?P<prereq_id>[^/.]+)",
    )
    @extend_schema(
        parameters=[
            OpenApiParameter("prereq_id", OpenApiTypes.UUID, OpenApiParameter.PATH)
        ]
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path=r"prerequisites/(?P<prereq_id>[^/.]+)",
    )
    def delete_prerequisite(self, request, pk=None, prereq_id=None):
        course = self.get_object()
        deleted, _ = CoursePrerequisite.objects.filter(
            course=course, pk=prereq_id
        ).delete()
        if not deleted:
            return success_response(message="Prerequisite not found.", status=404)
        return success_response(message="Prerequisite removed.")
