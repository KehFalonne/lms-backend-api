from django.db.models import Count
from django.db import models
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import error_response, success_response
from apps.courses.models import (
    Course,
    CourseOffering,
    CourseEnrollment,
    OfferingStatus,
)
from apps.courses.serializers import (
    CourseOfferingListSerializer,
    CourseOfferingSerializer,
)
from apps.academics.models import Semester
from apps.university.models import Programme


class CourseOfferingViewSet(viewsets.GenericViewSet):
    serializer_class = CourseOfferingSerializer
    permission_classes = [IsAuthenticatedAndActive]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["semester", "programme", "course", "status", "section"]
    search_fields = ["course__code", "course__title"]
    ordering_fields = ["created_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return CourseOffering.objects.select_related(
            "course", "semester", "programme"
        ).annotate(
            enrolled_count=Count(
                "enrollments",
                filter=models.Q(enrollments__status="ACTIVE"),
                distinct=True,
            ),
            instructor_count=Count("instructors", distinct=True),
        )

    def get_permissions(self):
        if self.action in (
            "create",
            "update",
            "partial_update",
            "destroy",
            "publish",
            "complete",
            "archive",
            "cancel",
        ):
            return [IsAdminUser()]
        return super().get_permissions()

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        serializer_cls = (
            CourseOfferingListSerializer
            if request.query_params.get("compact") == "true"
            else CourseOfferingSerializer
        )
        if page is not None:
            return self.get_paginated_response(serializer_cls(page, many=True).data)
        return success_response(data=serializer_cls(qs, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return success_response(data=CourseOfferingSerializer(instance).data)

    def create(self, request, *args, **kwargs):
        serializer = CourseOfferingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        course_id = serializer.validated_data.pop("course_id")
        semester_id = serializer.validated_data.pop("semester_id")
        programme_id = serializer.validated_data.pop("programme_id")

        try:
            course = Course.objects.get(pk=course_id, deleted_at__isnull=True)
        except Course.DoesNotExist:
            return error_response("Course not found.", status_code=400)
        try:
            semester = Semester.objects.get(pk=semester_id)
        except Semester.DoesNotExist:
            return error_response("Semester not found.", status_code=400)
        try:
            programme = Programme.objects.get(pk=programme_id, deleted_at__isnull=True)
        except Programme.DoesNotExist:
            return error_response("Programme not found.", status_code=400)

        offering = CourseOffering.objects.create(
            course=course,
            semester=semester,
            programme=programme,
            **serializer.validated_data,
        )
        fresh = self.get_queryset().get(pk=offering.pk)
        return success_response(
            data=CourseOfferingSerializer(fresh).data,
            message="Course offering created successfully.",
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = CourseOfferingSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # course_id/semester_id/programme_id are required=False on update — ignore if not sent
        serializer.validated_data.pop("course_id", None)
        serializer.validated_data.pop("semester_id", None)
        serializer.validated_data.pop("programme_id", None)

        for k, v in serializer.validated_data.items():
            setattr(instance, k, v)
        instance.save()
        fresh = self.get_queryset().get(pk=instance.pk)
        return success_response(
            data=CourseOfferingSerializer(fresh).data,
            message="Course offering updated.",
        )

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return success_response(message="Course offering deleted.")

    # ── Lifecycle actions ────────────────────────────────────────────

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        offering = self.get_object()
        if offering.status != OfferingStatus.DRAFT:
            return error_response(
                f"Cannot publish from status {offering.status}.", status_code=400
            )
        offering.status = OfferingStatus.ACTIVE
        offering.published_at = timezone.now()
        offering.save(update_fields=["status", "published_at", "updated_at"])
        return success_response(
            data=CourseOfferingSerializer(offering).data,
            message="Course offering published.",
        )

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        offering = self.get_object()
        offering.status = OfferingStatus.COMPLETED
        offering.save(update_fields=["status", "updated_at"])
        return success_response(
            data=CourseOfferingSerializer(offering).data,
            message="Course offering completed.",
        )

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        offering = self.get_object()
        offering.status = OfferingStatus.ARCHIVED
        offering.save(update_fields=["status", "updated_at"])
        return success_response(
            data=CourseOfferingSerializer(offering).data,
            message="Course offering archived.",
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        offering = self.get_object()
        offering.status = OfferingStatus.CANCELLED
        offering.save(update_fields=["status", "updated_at"])
        return success_response(
            data=CourseOfferingSerializer(offering).data,
            message="Course offering cancelled.",
        )
