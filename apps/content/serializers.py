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
    audio_version_count = serializers.SerializerMethodField()
    audio_versions = serializers.SerializerMethodField()

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

    def get_audio_version_count(self, obj):
        return obj.versions.count() if obj.content_type == ContentType.AUDIO else 0

    def get_audio_versions(self, obj):
        if obj.content_type != ContentType.AUDIO:
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
        body = attrs.get("body", getattr(self.instance, "body", ""))
        chapters = attrs.get("chapters", getattr(self.instance, "chapters", []))
        if chapters is None:
            chapters = []
        if not isinstance(chapters, list):
            raise serializers.ValidationError({"chapters": "Chapters must be a list."})
        previous_start = -1
        for chapter in chapters:
            if not isinstance(chapter, dict) or not str(chapter.get("title", "")).strip():
                raise serializers.ValidationError({"chapters": "Each chapter needs a title."})
            try:
                start_seconds = float(
                    chapter.get("startSeconds", chapter.get("start_seconds", -1))
                )
            except (TypeError, ValueError):
                start_seconds = -1
            if start_seconds < 0 or start_seconds < previous_start:
                raise serializers.ValidationError(
                    {"chapters": "Chapter start times must be increasing and non-negative."}
                )
            previous_start = start_seconds
        if file_id:
            file = File.objects.filter(id=file_id, status="READY").first()
            if not file:
                raise serializers.ValidationError(
                    {"file_id": "The selected file is not ready or does not exist."}
                )
            if content_type == ContentType.AUDIO:
                audio_extensions = {"mp3", "wav", "ogg", "m4a", "aac", "flac", "webm"}
                is_audio = file.mime_type.lower().startswith("audio/") or file.extension.lower() in audio_extensions
                if not is_audio:
                    raise serializers.ValidationError(
                        {"file_id": "Audio content must use an audio file."}
                    )
        attachment_ids = attrs.get(
            "attachment_ids", getattr(self.instance, "attachment_ids", [])
        ) or []
        if not isinstance(attachment_ids, list):
            raise serializers.ValidationError({"attachment_ids": "Attachments must be a list."})
        if attachment_ids:
            ready_ids = set(
                str(file_id)
                for file_id in File.objects.filter(
                    id__in=attachment_ids, status="READY"
                ).values_list("id", flat=True)
            )
            missing_ids = [str(file_id) for file_id in attachment_ids if str(file_id) not in ready_ids]
            if missing_ids:
                raise serializers.ValidationError(
                    {"attachment_ids": "Every attachment must be uploaded and ready."}
                )
        if content_type == ContentType.TEXT and not body.strip():
            raise serializers.ValidationError({"body": "Text content is required for a text lesson."})
        if content_type in (ContentType.AUDIO, ContentType.LINK, ContentType.EMBED):
            if content_type in (ContentType.LINK, ContentType.EMBED) and not external_url:
                raise serializers.ValidationError(
                    {"external_url": "A URL is required for this content type."}
                )
            if content_type == ContentType.AUDIO and not external_url and not file_id:
                raise serializers.ValidationError(
                    {"external_url": "Provide an audio URL or upload an audio file."}
                )
            if external_url and not external_url.startswith(("http://", "https://")):
                raise serializers.ValidationError(
                    {"external_url": "Only HTTP and HTTPS URLs are supported."}
                )
        if content_type == ContentType.VIDEO:
            if not external_url and not file_id:
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
            "transcript",
            "external_url",
            "allow_download",
            "chapters",
            "attachment_ids",
            "file_id",
            "file_name",
            "file_size_bytes",
            "file_mime_type",
            "pdf_version_count",
            "pdf_accessibility_warning",
            "pdf_versions",
            "audio_version_count",
            "audio_versions",
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
