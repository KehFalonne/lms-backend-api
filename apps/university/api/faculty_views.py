from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.permissions import IsAdminUser

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import error_response, success_response
from apps.university.models import Faculty
from apps.university.serializers import FacultySerializer


class FacultyViewSet(viewsets.ModelViewSet):
    queryset = (
        Faculty.objects.select_related("dean")
        .annotate(department_count=Count("departments", distinct=True))
        .filter(deleted_at__isnull=True)
    )
    serializer_class = FacultySerializer
    permission_classes = [IsAuthenticatedAndActive]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status"]
    search_fields = ["code", "name", "description"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["code"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAdminUser()]
        return super().get_permissions()

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return success_response(
            data=self.get_serializer(qs, many=True).data,
            message="Faculties retrieved successfully.",
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return success_response(data=self.get_serializer(instance).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        # re-fetch to include annotations
        fresh = self.get_queryset().get(pk=instance.pk)
        return success_response(
            data=self.get_serializer(fresh).data,
            message="Faculty created successfully.",
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
            message="Faculty updated successfully.",
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return success_response(message="Faculty deleted successfully.")
