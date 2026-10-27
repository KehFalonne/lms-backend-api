from rest_framework import serializers

from .models import AcademicYear, Semester


class SemesterSerializer(serializers.ModelSerializer):
    academic_year_id = serializers.UUIDField(write_only=True, required=True)
    academic_year = serializers.SerializerMethodField()

    class Meta:
        model = Semester
        fields = [
            "id",
            "academic_year",
            "academic_year_id",
            "name",
            "code",
            "sequence",
            "start_date",
            "end_date",
            "status",
            "is_current",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "academic_year",
            "is_current",
            "created_at",
            "updated_at",
        ]

    def get_academic_year(self, obj):
        return {"id": str(obj.academic_year_id), "name": obj.academic_year.name}


class AcademicYearSerializer(serializers.ModelSerializer):
    semester_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = AcademicYear
        fields = [
            "id",
            "name",
            "start_date",
            "end_date",
            "status",
            "is_current",
            "semester_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_current",
            "semester_count",
            "created_at",
            "updated_at",
        ]
