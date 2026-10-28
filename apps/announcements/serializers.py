from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    course_offering_id = serializers.UUIDField(write_only=True, required=False)
    created_by = UserSerializer(read_only=True)
    is_read = serializers.SerializerMethodField()
    read_count = serializers.SerializerMethodField()

    def get_is_read(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.reads.filter(student=request.user).exists()

    def get_read_count(self, obj) -> int:
        return obj.reads.count()

    class Meta:
        model = Announcement
        fields = [
            "id",
            "course_offering_id",
            "title",
            "body",
            "is_pinned",
            "publish_at",
            "expires_at",
            "status",
            "created_by",
            "created_at",
            "updated_at",
            "read_count",
            "is_read",
        ]
        read_only_fields = [
            "id",
            "publish_at",
            "created_by",
            "created_at",
            "updated_at",
        ]


class AnnouncementReaderSerializer(serializers.Serializer):
    """Compact student info for the readers list."""

    id = serializers.UUIDField()
    universityId = serializers.CharField(source="university_id")
    firstName = serializers.CharField(source="first_name")
    lastName = serializers.CharField(source="last_name")
