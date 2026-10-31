from rest_framework import serializers

from .models import ContentItem, ContentType, CourseModule


class CourseModuleSerializer(serializers.ModelSerializer):
    course_offering_id = serializers.UUIDField(read_only=True)
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
    course_module_id = serializers.UUIDField(read_only=True)

    def validate(self, attrs):
        content_type = attrs.get("content_type", getattr(self.instance, "content_type", None))
        external_url = attrs.get("external_url", getattr(self.instance, "external_url", ""))
        file_id = attrs.get("file_id", getattr(self.instance, "file_id", None))
        if content_type in (ContentType.VIDEO, ContentType.AUDIO, ContentType.LINK, ContentType.EMBED):
            if content_type != ContentType.VIDEO and not external_url:
                raise serializers.ValidationError(
                    {"external_url": "A URL is required for this content type."}
                )
            if content_type == ContentType.VIDEO and not external_url and not file_id:
                raise serializers.ValidationError(
                    {"external_url": "Provide a video URL or upload a video file."}
                )
            if external_url and not external_url.startswith(("http://", "https://")):
                raise serializers.ValidationError(
                    {"external_url": "Only HTTP and HTTPS URLs are supported."}
                )
        return attrs

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
