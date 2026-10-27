from django.contrib import admin

from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "course_offering", "status", "is_pinned", "created_at")
    list_filter = ("status", "is_pinned")
    search_fields = ("title", "body", "course_offering__course__code")
    autocomplete_fields = ("course_offering", "created_by")
    readonly_fields = ("id", "created_at", "updated_at")
