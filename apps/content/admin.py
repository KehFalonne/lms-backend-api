from django.contrib import admin

from .models import ContentItem, CourseModule


@admin.register(CourseModule)
class CourseModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course_offering", "position", "is_published")
    list_filter = ("is_published",)
    search_fields = ("title", "course_offering__course__code")
    autocomplete_fields = ("course_offering", "created_by")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course_module",
        "content_type",
        "position",
        "is_published",
    )
    list_filter = ("content_type", "is_published")
    search_fields = ("title", "course_module__title")
    autocomplete_fields = ("course_module", "created_by")
    readonly_fields = ("id", "created_at", "updated_at")
