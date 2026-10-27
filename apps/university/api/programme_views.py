from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.permissions import IsAdminUser

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import success_response
from apps.university.models import Department, Programme
from apps.university.serializers import ProgrammeSerializer


class ProgrammeViewSet(viewsets.ModelViewSet):
    queryset = Programme.objects.select_related(
        "department", "department__faculty"
    ).filter(deleted_at__isnull=True)
    serializer_class = ProgrammeSerializer
    permission_classes = [IsAuthenticatedAndActive]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["department", "degree_type", "status"]
    search_fields = ["code", "name", "department__code"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["department__code", "code"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
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

        department_id = serializer.validated_data.pop("department_id", None)
        try:
            department = Department.objects.get(
                pk=department_id, deleted_at__isnull=True
            )
        except Department.DoesNotExist:
            return success_response(
                message="Department not found.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance = Programme.objects.create(
            department=department, **serializer.validated_data
        )
        return success_response(
            data=self.get_serializer(instance).data,
            message="Programme created successfully.",
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
        return success_response(
            data=self.get_serializer(instance).data,
            message="Programme updated successfully.",
        )

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return success_response(message="Programme deleted successfully.")
