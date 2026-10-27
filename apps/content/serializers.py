from rest_framework import serializers

from .models import ContentItem, ContentType, CourseModule


class CourseModuleSerializer(serializers.ModelSerializer):
    course_offering_id = serializers.UUIDField(write_only=True, required=False)
    content_count = serializers.SerializerMethodField()

    class Meta:
        model = CourseModule
        fields = [
            "id",
            "course_offering_id",
            "title",
            "description",
            "position",
            "availability_start",
            "availability_end",
            "is_published",
            "content_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "content_count",
            "created_at",
            "updated_at",
        ]

    def get_content_count(self, obj) -> int:
        return obj.content_items.filter(deleted_at__isnull=True).count()


class ContentItemSerializer(serializers.ModelSerializer):
    course_module_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = ContentItem
        fields = [
            "id",
            "course_module_id",
            "title",
            "content_type",
            "description",
            "body",
            "external_url",
            "file_id",
            "position",
            "is_required",
            "availability_start",
            "availability_end",
            "is_published",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]
