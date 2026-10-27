from django.contrib import admin

from .models import (
    Assignment,
    AssignmentSubmission,
    Feedback,
    SubmissionFile,
)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "course_offering", "status", "due_at", "max_score")
    list_filter = ("status", "submission_type", "late_penalty_type")
    search_fields = ("title", "course_offering__course__code")
    autocomplete_fields = ("course_offering", "created_by")
    readonly_fields = ("id", "published_at", "created_at", "updated_at")


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "assignment",
        "attempt_number",
        "status",
        "is_late",
        "score",
        "graded_at",
    )
    list_filter = ("status", "is_late")
    search_fields = ("student__university_id", "assignment__title")
    autocomplete_fields = ("assignment", "student", "graded_by")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SubmissionFile)
class SubmissionFileAdmin(admin.ModelAdmin):
    list_display = ("submission", "file", "created_at")
    autocomplete_fields = ("submission", "file")
    readonly_fields = ("id", "created_at")


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("submission", "author", "created_at")
    search_fields = ("content",)
    autocomplete_fields = ("submission", "author")
    readonly_fields = ("id", "created_at")
