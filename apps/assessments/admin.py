from django.contrib import admin

from .models import (
    Assessment,
    AssessmentAttempt,
    AssessmentQuestion,
    Question,
    QuestionBank,
    QuestionOption,
    StudentAnswer,
    AssessmentProctoringEvent,
)


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "visibility", "created_at")
    list_filter = ("visibility",)
    search_fields = ("title", "description")
    autocomplete_fields = ("owner", "course", "department")
    readonly_fields = ("id", "created_at", "updated_at")


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 1


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "question_type", "difficulty", "status", "question_bank")
    list_filter = ("question_type", "difficulty", "status")
    search_fields = ("text",)
    autocomplete_fields = ("question_bank", "created_by")
    inlines = [QuestionOptionInline]
    readonly_fields = ("id", "current_version", "created_at", "updated_at")


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course_offering",
        "assessment_type",
        "status",
        "total_points",
    )
    list_filter = ("assessment_type", "status")
    search_fields = ("title",)
    autocomplete_fields = ("course_offering", "created_by")
    readonly_fields = ("id", "published_at", "created_at", "updated_at")


@admin.register(AssessmentQuestion)
class AssessmentQuestionAdmin(admin.ModelAdmin):
    list_display = ("assessment", "question", "position", "points")
    search_fields = ("assessment__title", "question__text")
    autocomplete_fields = ("assessment", "question")


@admin.register(AssessmentAttempt)
class AssessmentAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "assessment",
        "attempt_number",
        "status",
        "total_score",
        "percentage",
    )
    list_filter = ("status",)
    search_fields = ("student__university_id", "assessment__title")
    autocomplete_fields = ("student", "assessment")
    readonly_fields = ("id", "started_at", "created_at", "updated_at")


@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ("attempt", "assessment_question", "score", "is_correct")
    autocomplete_fields = ("attempt", "assessment_question")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(AssessmentProctoringEvent)
class AssessmentProctoringEventAdmin(admin.ModelAdmin):
    list_display = ("attempt", "event_type", "ip_address", "created_at")
    list_filter = ("event_type",)
    search_fields = ("attempt__student__university_id",)
    autocomplete_fields = ("attempt",)
    readonly_fields = (
        "id",
        "attempt",
        "event_type",
        "detail",
        "ip_address",
        "user_agent",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
