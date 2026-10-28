from django.contrib import admin

from .models import Announcement, AnnouncementRead


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "course_offering", "status", "is_pinned", "created_at")
    list_filter = ("status", "is_pinned")
    search_fields = ("title", "body", "course_offering__course__code")
    autocomplete_fields = ("course_offering", "created_by")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AnnouncementRead)
class AnnouncementReadAdmin(admin.ModelAdmin):
    list_display = ("announcement", "student", "read_at")
    search_fields = ("student__university_id", "announcement__title")
    autocomplete_fields = ("announcement", "student")
    readonly_fields = ("id", "read_at")
