from django.contrib import admin

from .models import File


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = (
        "original_name",
        "mime_type",
        "human_size",
        "status",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("status", "storage_provider", "mime_type")
    search_fields = ("original_name", "storage_key", "uploaded_by__email")
    readonly_fields = ("id", "storage_key", "checksum", "created_at", "updated_at")
