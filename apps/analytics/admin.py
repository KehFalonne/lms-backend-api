from django.contrib import admin

from .models import ContentProgress, LearningEvent, StudentCourseProgress


@admin.register(LearningEvent)
class LearningEventAdmin(admin.ModelAdmin):
    list_display = ("student", "event_type", "course_offering", "occurred_at")
    list_filter = ("event_type",)
    search_fields = ("student__university_id",)
    autocomplete_fields = ("student", "course_offering")
    readonly_fields = ("id", "occurred_at")


@admin.register(StudentCourseProgress)
class StudentCourseProgressAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "course_offering",
        "progress_percentage",
        "calculated_at",
    )
    autocomplete_fields = ("student", "course_offering")
    readonly_fields = ("id", "calculated_at")


@admin.register(ContentProgress)
class ContentProgressAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "content_item",
        "status",
        "progress_percent",
        "last_accessed_at",
    )
    list_filter = ("status",)
    autocomplete_fields = ("student", "content_item")
    readonly_fields = ("id", "last_accessed_at")
