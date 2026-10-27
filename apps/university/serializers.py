from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from .models import Department, Faculty, Programme

# ── Faculty ──────────────────────────────────────────────────────────


class FacultySerializer(serializers.ModelSerializer):
    department_count = serializers.IntegerField(read_only=True)
    dean = UserSerializer(read_only=True)

    class Meta:
        model = Faculty
        fields = [
            "id",
            "code",
            "name",
            "description",
            "dean",
            "status",
            "department_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "dean",
            "department_count",
            "created_at",
            "updated_at",
        ]

    def validate_code(self, value: str) -> str:
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Code is required.")
        return value


# ── Department ───────────────────────────────────────────────────────


class DepartmentSerializer(serializers.ModelSerializer):
    faculty = FacultySerializer(read_only=True)
    faculty_id = serializers.UUIDField(write_only=True, required=True)  # ← explicit
    hod = UserSerializer(read_only=True)
    programme_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = [
            "id",
            "faculty",
            "faculty_id",
            "code",
            "name",
            "description",
            "hod",
            "status",
            "programme_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "faculty",
            "hod",
            "programme_count",
            "created_at",
            "updated_at",
        ]
        # ← extra_kwargs removed entirely


# ── Programme ────────────────────────────────────────────────────────


class ProgrammeSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer(read_only=True)
    department_id = serializers.UUIDField(write_only=True, required=True)  # ← explicit

    class Meta:
        model = Programme
        fields = [
            "id",
            "department",
            "department_id",
            "code",
            "name",
            "degree_type",
            "duration_years",
            "total_credits",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "department", "created_at", "updated_at"]
        # ← extra_kwargs removed entirely
