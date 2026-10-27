from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import success_response
from apps.academics.models import AcademicYear, Semester, SemesterStatus
from apps.academics.serializers import SemesterSerializer


class SemesterViewSet(viewsets.ModelViewSet):
    queryset = Semester.objects.select_related("academic_year").all()
    serializer_class = SemesterSerializer
    permission_classes = [IsAuthenticatedAndActive]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["academic_year", "status", "is_current"]
    search_fields = ["name", "code", "academic_year__name"]
    ordering = ["academic_year__name", "sequence"]

    def get_permissions(self):
        if self.action in (
            "create",
            "update",
            "partial_update",
            "destroy",
            "set_current",
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
        year_id = serializer.validated_data.pop("academic_year_id")
        try:
            year = AcademicYear.objects.get(pk=year_id)
        except AcademicYear.DoesNotExist:
            return success_response(
                message="Academic year not found.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance = Semester.objects.create(
            academic_year=year, **serializer.validated_data
        )
        return success_response(
            data=self.get_serializer(instance).data,
            message="Semester created successfully.",
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        year_id = serializer.validated_data.pop("academic_year_id", None)
        if year_id:
            try:
                instance.academic_year = AcademicYear.objects.get(pk=year_id)
            except AcademicYear.DoesNotExist:
                return success_response(
                    message="Academic year not found.",
                    status=status.HTTP_400_BAD_REQUEST,
                )
        for k, v in serializer.validated_data.items():
            setattr(instance, k, v)
        instance.save()
        return success_response(
            data=self.get_serializer(instance).data,
            message="Semester updated successfully.",
        )

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return success_response(message="Semester deleted successfully.")

    @action(detail=True, methods=["post"], url_path="set-current")
    @transaction.atomic
    def set_current(self, request, pk=None):
        """POST /semesters/{id}/set-current/"""
        semester = self.get_object()
        Semester.objects.filter(
            academic_year=semester.academic_year, is_current=True
        ).update(is_current=False, status=SemesterStatus.COMPLETED)

        semester.is_current = True
        semester.status = SemesterStatus.ACTIVE
        semester.save(update_fields=["is_current", "status", "updated_at"])
        return success_response(
            data=self.get_serializer(semester).data,
            message=f"{semester.name} is now the current semester.",
        )
