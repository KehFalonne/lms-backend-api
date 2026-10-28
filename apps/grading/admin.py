from django.contrib import admin

from .models import Grade, GradeCategory, GradeHistory, GradeItem, GradeAppeal


@admin.register(GradeCategory)
class GradeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "course_offering", "weight", "position")
    search_fields = ("name", "course_offering__course__code")
    autocomplete_fields = ("course_offering",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(GradeItem)
class GradeItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "course_offering",
        "category",
        "max_score",
        "source_type",
        "is_published",
    )
    list_filter = ("source_type", "is_published")
    search_fields = ("name", "course_offering__course__code")
    autocomplete_fields = ("course_offering", "category")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("student", "grade_item", "score", "percentage", "status")
    list_filter = ("status",)
    search_fields = ("student__university_id", "grade_item__name")
    autocomplete_fields = ("student", "grade_item", "graded_by")
    readonly_fields = ("id", "graded_at", "published_at", "created_at", "updated_at")


@admin.register(GradeHistory)
class GradeHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "grade",
        "previous_score",
        "new_score",
        "previous_status",
        "new_status",
        "changed_at",
    )
    search_fields = ("grade__student__university_id",)
    autocomplete_fields = ("grade", "changed_by")
    readonly_fields = ("id", "changed_at")


@admin.register(GradeAppeal)
class GradeAppealAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "student",
        "grade",
        "status",
        "original_score",
        "resolved_score",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("student__university_id", "reason", "reviewer_notes")
    autocomplete_fields = ("grade", "student", "reviewer")
    readonly_fields = (
        "id",
        "created_at",
        "resolved_at",
        "original_score",
        "resolved_score",
    )
