from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    course_offering_id = serializers.UUIDField(write_only=True, required=False)
    created_by = UserSerializer(read_only=True)

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
        ]
        read_only_fields = [
            "id",
            "publish_at",
            "created_by",
            "created_at",
            "updated_at",
        ]
