from rest_framework import serializers

from apps.files.models import File

from .models import ContentItem, ContentItemVersion, ContentType, CourseModule


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
    file_name = serializers.SerializerMethodField()
    file_size_bytes = serializers.SerializerMethodField()
    file_mime_type = serializers.SerializerMethodField()
    pdf_version_count = serializers.SerializerMethodField()
    pdf_accessibility_warning = serializers.SerializerMethodField()
    pdf_versions = serializers.SerializerMethodField()

    def _file(self, obj):
        if not obj.file_id:
            return None
        return File.objects.filter(id=obj.file_id, status="READY").first()

    def get_file_name(self, obj):
        file = self._file(obj)
        return file.original_name if file else None

    def get_file_size_bytes(self, obj):
        file = self._file(obj)
        return file.size_bytes if file else None

    def get_file_mime_type(self, obj):
        file = self._file(obj)
        return file.mime_type if file else None

    def get_pdf_version_count(self, obj):
        return obj.versions.count() if obj.content_type == ContentType.PDF else 0

    def get_pdf_accessibility_warning(self, obj):
        if obj.content_type != ContentType.PDF or not obj.file_id:
            return None
        file = self._file(obj)
        if not file:
            return None
        return (
            "Confirm this PDF contains selectable text and document structure. "
            "Scanned image-only PDFs may not be accessible to screen readers."
        )

    def get_pdf_versions(self, obj):
        if obj.content_type != ContentType.PDF:
            return []
        return [
            {
                "versionNumber": version.version_number,
                "fileName": version.file_name,
                "fileSizeBytes": version.file_size_bytes,
                "createdAt": version.created_at.isoformat(),
            }
            for version in obj.versions.all()
        ]

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
        if content_type == ContentType.PDF and not external_url and not file_id:
            raise serializers.ValidationError(
                {"file_id": "Upload a PDF file or provide a PDF URL."}
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
            "file_name",
            "file_size_bytes",
            "file_mime_type",
            "pdf_version_count",
            "pdf_accessibility_warning",
            "pdf_versions",
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
