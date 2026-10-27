from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from .models import CalendarEvent


class CalendarEventSerializer(serializers.ModelSerializer):
    course_offering_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    course_offering = serializers.SerializerMethodField()
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = CalendarEvent
        fields = [
            "id",
            "course_offering",
            "course_offering_id",
            "title",
            "description",
            "event_type",
            "start_at",
            "end_at",
            "is_all_day",
            "location",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "course_offering",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_course_offering(self, obj):
        if not obj.course_offering_id:
            return None
        o = obj.course_offering
        return {
            "id": str(o.id),
            "courseCode": o.course.code,
            "courseTitle": o.course.title,
        }
