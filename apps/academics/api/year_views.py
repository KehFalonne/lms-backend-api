from django.db.models import Count
from django.db import transaction
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import success_response
from apps.academics.models import AcademicYear, AcademicYearStatus
from apps.academics.serializers import AcademicYearSerializer


class AcademicYearViewSet(viewsets.ModelViewSet):
    queryset = AcademicYear.objects.annotate(
        semester_count=Count("semesters", distinct=True)
    ).all()
    serializer_class = AcademicYearSerializer
    permission_classes = [IsAuthenticatedAndActive]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "start_date", "created_at"]
    ordering = ["-start_date"]

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
        instance = serializer.save()
        fresh = self.get_queryset().get(pk=instance.pk)
        return success_response(
            data=self.get_serializer(fresh).data,
            message="Academic year created successfully.",
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        fresh = self.get_queryset().get(pk=instance.pk)
        return success_response(
            data=self.get_serializer(fresh).data,
            message="Academic year updated successfully.",
        )

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return success_response(message="Academic year deleted successfully.")

    @action(detail=True, methods=["post"], url_path="set-current")
    @transaction.atomic
    def set_current(self, request, pk=None):
        """POST /academic-years/{id}/set-current/"""
        year = self.get_object()
        AcademicYear.objects.filter(is_current=True).update(
            is_current=False,
            status=AcademicYearStatus.COMPLETED,
        )
        year.is_current = True
        year.status = AcademicYearStatus.ACTIVE
        year.save(update_fields=["is_current", "status", "updated_at"])
        fresh = self.get_queryset().get(pk=year.pk)
        return success_response(
            data=self.get_serializer(fresh).data,
            message=f"{year.name} is now the current academic year.",
        )
