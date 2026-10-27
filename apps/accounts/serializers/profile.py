from rest_framework import serializers

from apps.accounts.models import StaffProfile, StudentProfile


class StudentProfileSerializer(serializers.ModelSerializer):
    programme_id = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "matricule_number",
            "programme",
            "programme_id",
            "current_level",
            "admission_year",
            "admission_date",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "matricule_number",
            "programme",
            "programme_id",
            "created_at",
            "updated_at",
        ]

    def get_programme_id(self, obj) -> str | None:
        return str(obj.programme_id) if obj.programme_id else None


class StaffProfileSerializer(serializers.ModelSerializer):
    department_id = serializers.SerializerMethodField()

    class Meta:
        model = StaffProfile
        fields = [
            "id",
            "staff_number",
            "department",
            "department_id",
            "job_title",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "staff_number",
            "department",
            "department_id",
            "created_at",
            "updated_at",
        ]

    def get_department_id(self, obj) -> str | None:
        return str(obj.department_id) if obj.department_id else None
