"""
User management endpoints — per backend doc §15.

Filtering (documented):
    /api/v1/users/?status=ACTIVE
    /api/v1/users/?search=John
"""

from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAdminUser

from apps.common.responses import error_response, success_response
from apps.accounts.serializers import (
    AssignRoleSerializer,
    UserCreateSerializer,
    UserRoleSerializer,
    UserMeSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from apps.accounts.services import RBACError, RBACService, UserService

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """
    CRUD + activate / deactivate. Restricted to staff (RBAC-scoped
    permissions land in Sprint 3).
    """

    queryset = User.objects.select_related("student_profile", "staff_profile").all()
    permission_classes = [IsAdminUser]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "is_active", "is_staff"]
    search_fields = ["first_name", "last_name", "email", "university_id"]
    ordering_fields = ["created_at", "updated_at", "last_name"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        if self.action == "me":
            return UserMeSerializer
        return UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return success_response(
            data=UserSerializer(user).data,
            message="User created successfully.",
            status=status.HTTP_201_CREATED,
        )

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return success_response(
            data=serializer.data, message="Users retrieved successfully."
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return success_response(data=self.get_serializer(instance).data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(
            data=UserSerializer(instance).data,
            message="User updated successfully.",
        )

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete: deactivate instead of hard delete so academic history
        remains intact (per database doc §5).
        """
        instance = self.get_object()
        UserService.deactivate(instance)
        return success_response(message="User deactivated successfully.")

    # ── Custom actions ──────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        user = self.get_object()
        UserService.activate(user)
        return success_response(
            data=UserSerializer(user).data,
            message="User activated successfully.",
        )

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        user = self.get_object()
        UserService.deactivate(user)
        return success_response(
            data=UserSerializer(user).data,
            message="User deactivated successfully.",
        )

    @action(detail=True, methods=["get"], url_path="roles")
    def list_roles(self, request, pk=None):
        """GET /api/v1/users/{id}/roles/ — list role assignments."""
        from apps.accounts.models import UserRole
        from apps.accounts.serializers.rbac import UserRoleSerializer

        user = self.get_object()
        assignments = (
            UserRole.objects.filter(user=user)
            .select_related("role", "assigned_by")
            .order_by("-assigned_at")
        )
        return success_response(data=UserRoleSerializer(assignments, many=True).data)

    @action(detail=True, methods=["post"], url_path="assign-role")
    def assign_role(self, request, pk=None):
        """
        POST /api/v1/users/{id}/assign-role/   (backend doc §15)

        Body:
            {
                "roleId": "uuid",
                "scopeType": "GLOBAL|FACULTY|DEPARTMENT|COURSE",
                "facultyId": "uuid|null",
                "departmentId": "uuid|null",
                "courseOfferingId": "uuid|null"
            }
        """
        user = self.get_object()
        serializer = AssignRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            assignment = RBACService.assign_role(
                user=user,
                role_id=serializer.validated_data["role_id"],
                scope_type=serializer.validated_data["scope_type"],
                faculty_id=serializer.validated_data.get("faculty_id"),
                department_id=serializer.validated_data.get("department_id"),
                course_offering_id=serializer.validated_data.get("course_offering_id"),
                assigned_by=request.user,
            )
        except RBACError as exc:
            return error_response(
                exc.args[0], status_code=400, errors={"code": [exc.code]}
            )

        return success_response(
            data=UserRoleSerializer(assignment).data,
            message="Role assigned successfully.",
            status=201,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"roles/(?P<assignment_id>[^/.]+)",
    )
    @extend_schema(
        parameters=[
            OpenApiParameter("assignment_id", OpenApiTypes.UUID, OpenApiParameter.PATH)
        ]
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path=r"roles/(?P<assignment_id>[^/.]+)",
    )
    def revoke_role(self, request, pk=None, assignment_id=None):
        """
        DELETE /api/v1/users/{id}/roles/{assignment_id}/   (backend doc §15)
        """
        user = self.get_object()
        try:
            RBACService.revoke_role(user=user, assignment_id=assignment_id)
        except RBACError as exc:
            return error_response(
                exc.args[0], status_code=400, errors={"code": [exc.code]}
            )
        return success_response(message="Role revoked successfully.")
