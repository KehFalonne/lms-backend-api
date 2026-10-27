from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.permissions import IsAdminUser

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import success_response
from apps.university.models import Department, Faculty
from apps.university.serializers import DepartmentSerializer


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = (
        Department.objects.select_related("faculty", "hod")
        .annotate(programme_count=Count("programmes", distinct=True))
        .filter(deleted_at__isnull=True)
    )
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticatedAndActive]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["faculty", "status"]
    search_fields = ["code", "name", "faculty__code", "faculty__name"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["faculty__code", "code"]

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
        return success_response(data=self.get_serializer(qs, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        faculty_id = serializer.validated_data.pop("faculty_id", None)
        try:
            faculty = Faculty.objects.get(pk=faculty_id, deleted_at__isnull=True)
        except Faculty.DoesNotExist:
            return success_response(
                message="Faculty not found.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance = Department.objects.create(
            faculty=faculty, **serializer.validated_data
        )
        fresh = self.get_queryset().get(pk=instance.pk)
        return success_response(
            data=self.get_serializer(fresh).data,
            message="Department created successfully.",
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        faculty_id = serializer.validated_data.pop("faculty_id", None)
        if faculty_id:
            try:
                instance.faculty = Faculty.objects.get(
                    pk=faculty_id, deleted_at__isnull=True
                )
            except Faculty.DoesNotExist:
                return success_response(
                    message="Faculty not found.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

        for k, v in serializer.validated_data.items():
            setattr(instance, k, v)
        instance.save()

        fresh = self.get_queryset().get(pk=instance.pk)
        return success_response(
            data=self.get_serializer(fresh).data,
            message="Department updated successfully.",
        )

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return success_response(message="Department deleted successfully.")
