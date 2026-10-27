"""
Roles & permissions endpoints — backend doc §16.
"""

from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from apps.common.responses import error_response, success_response
from apps.accounts.models import Permission, Role
from apps.accounts.serializers import (
    PermissionSerializer,
    RoleDetailSerializer,
    RolePermissionSetSerializer,
    RoleSerializer,
)
from apps.accounts.selectors import role_with_counts, roles_with_counts
from apps.accounts.services import RBACError, RBACService

User = get_user_model()


class RoleViewSet(viewsets.ViewSet):
    """CRUD for roles + role-permission management."""

    serializer_class = RoleSerializer
    permission_classes = [IsAdminUser]

    def list(self, request):
        qs = roles_with_counts()
        serializer = RoleSerializer(qs, many=True)
        return success_response(
            data=serializer.data, message="Roles retrieved successfully."
        )

    def create(self, request):
        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            role = RBACService.create_role(
                code=serializer.validated_data["code"],
                name=serializer.validated_data["name"],
                description=serializer.validated_data.get("description", ""),
            )
        except RBACError as exc:
            return error_response(
                exc.args[0], status_code=400, errors={"code": [exc.code]}
            )
        return success_response(
            data=RoleDetailSerializer(role_with_counts(role.id)).data,
            message="Role created successfully.",
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, pk=None):
        role = role_with_counts(pk)
        if not role:
            return error_response("Role not found.", status_code=404)
        return success_response(data=RoleDetailSerializer(role).data)

    def partial_update(self, request, pk=None):
        role = Role.objects.filter(pk=pk).first()
        if not role:
            return error_response("Role not found.", status_code=404)
        serializer = RoleSerializer(role, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            RBACService.update_role(
                role=role,
                name=serializer.validated_data.get("name", role.name),
                description=serializer.validated_data.get(
                    "description", role.description
                ),
            )
        except RBACError as exc:
            return error_response(exc.args[0], status_code=400)
        return success_response(
            data=RoleDetailSerializer(role_with_counts(role.id)).data,
            message="Role updated successfully.",
        )

    def destroy(self, request, pk=None):
        role = Role.objects.filter(pk=pk).first()
        if not role:
            return error_response("Role not found.", status_code=404)
        try:
            RBACService.delete_role(role=role)
        except RBACError as exc:
            return error_response(
                exc.args[0], status_code=400, errors={"code": [exc.code]}
            )
        return success_response(message="Role deleted successfully.")

    # ── /roles/{id}/permissions/ ─────────────────────────────────────

    @action(detail=True, methods=["get", "put"], url_path="permissions")
    def permissions(self, request, pk=None):
        role = Role.objects.filter(pk=pk).first()
        if not role:
            return error_response("Role not found.", status_code=404)

        if request.method == "GET":
            perms = Permission.objects.filter(permission_roles__role=role).order_by(
                "module", "code"
            )
            return success_response(
                data=PermissionSerializer(perms, many=True).data,
                message="Role permissions retrieved successfully.",
            )

        # PUT
        serializer = RolePermissionSetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RBACService.set_role_permissions(
                role=role, permission_ids=serializer.validated_data["permission_ids"]
            )
        except RBACError as exc:
            return error_response(
                exc.args[0], status_code=400, errors={"code": [exc.code]}
            )

        perms = Permission.objects.filter(permission_roles__role=role).order_by(
            "module", "code"
        )
        return success_response(
            data=PermissionSerializer(perms, many=True).data,
            message="Role permissions updated successfully.",
        )


class PermissionListView(APIView):
    """Flat list of all permissions (backend doc §16)."""

    serializer_class = PermissionSerializer
    permission_classes = [IsAdminUser]

    def get(self, request):
        module = request.query_params.get("module")
        search = request.query_params.get("search")

        qs = Permission.objects.all().order_by("module", "code")
        if module:
            qs = qs.filter(module=module)
        if search:
            qs = qs.filter(code__icontains=search) | qs.filter(name__icontains=search)

        return success_response(
            data=PermissionSerializer(qs, many=True).data,
            message="Permissions retrieved successfully.",
        )
