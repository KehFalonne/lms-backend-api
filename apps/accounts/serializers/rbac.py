from rest_framework import serializers

from apps.accounts.models import (
    Permission,
    Role,
    RolePermission,
    RoleScope,
    UserRole,
)


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "code", "name", "module", "description", "created_at"]
        read_only_fields = fields


class RoleSerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(read_only=True)
    permission_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "code",
            "name",
            "description",
            "is_system_role",
            "user_count",
            "permission_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_system_role",
            "created_at",
            "updated_at",
            "user_count",
            "permission_count",
        ]

    def validate_code(self, value: str) -> str:
        return value.strip().upper()

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        return value


class RoleDetailSerializer(RoleSerializer):
    permissions = PermissionSerializer(many=True, read_only=True)

    class Meta(RoleSerializer.Meta):
        fields = RoleSerializer.Meta.fields + ["permissions"]
        read_only_fields = RoleSerializer.Meta.read_only_fields + ["permissions"]


class RolePermissionSetSerializer(serializers.Serializer):
    """Payload for PUT /roles/{id}/permissions/."""

    permission_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
    )

    def validate_permission_ids(self, value):
        ids = list(set(value))
        existing = set(
            Permission.objects.filter(id__in=ids).values_list("id", flat=True)
        )
        missing = [str(i) for i in ids if i not in existing]
        if missing:
            raise serializers.ValidationError(
                f"Unknown permission IDs: {', '.join(missing)}"
            )
        return ids


class UserRoleSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    faculty_id = serializers.SerializerMethodField()
    department_id = serializers.SerializerMethodField()
    assigned_by = serializers.SerializerMethodField()

    class Meta:
        model = UserRole
        fields = [
            "id",
            "role",
            "scope_type",
            "faculty_id",
            "department_id",
            "course_offering_id",
            "assigned_at",
            "assigned_by",
        ]
        read_only_fields = fields

    def get_faculty_id(self, obj):
        return str(obj.faculty_id) if obj.faculty_id else None

    def get_department_id(self, obj):
        return str(obj.department_id) if obj.department_id else None

    def get_assigned_by(self, obj):
        if not obj.assigned_by_id:
            return None
        return {
            "id": str(obj.assigned_by_id),
            "universityId": obj.assigned_by.university_id,
            "firstName": obj.assigned_by.first_name,
            "lastName": obj.assigned_by.last_name,
        }


class AssignRoleSerializer(serializers.Serializer):
    role_id = serializers.UUIDField()
    scope_type = serializers.ChoiceField(
        choices=RoleScope.choices, default=RoleScope.GLOBAL
    )
    faculty_id = serializers.UUIDField(required=False, allow_null=True)
    department_id = serializers.UUIDField(required=False, allow_null=True)
    course_offering_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, data):
        scope = data["scope_type"]
        if scope == RoleScope.FACULTY and not data.get("faculty_id"):
            raise serializers.ValidationError(
                {"faculty_id": "Required for FACULTY scope."}
            )
        if scope == RoleScope.DEPARTMENT and not data.get("department_id"):
            raise serializers.ValidationError(
                {"department_id": "Required for DEPARTMENT scope."}
            )
        if scope == RoleScope.COURSE and not data.get("course_offering_id"):
            raise serializers.ValidationError(
                {"course_offering_id": "Required for COURSE scope."}
            )
        return data
