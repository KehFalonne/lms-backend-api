from django.contrib import admin

from .models import (
    Course,
    CourseInstructor,
    CoursePrerequisite,
    CourseOffering,
    CourseEnrollment,
)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "department", "level", "credits", "status")
    list_filter = ("status", "level", "department")
    search_fields = ("code", "title")
    autocomplete_fields = ("department",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CoursePrerequisite)
class CoursePrerequisiteAdmin(admin.ModelAdmin):
    list_display = ("course", "prerequisite_course", "minimum_grade")
    search_fields = ("course__code", "prerequisite_course__code")
    autocomplete_fields = ("course", "prerequisite_course")
    readonly_fields = ("id", "created_at")


@admin.register(CourseOffering)
class CourseOfferingAdmin(admin.ModelAdmin):
    list_display = ("course", "semester", "programme", "section", "capacity", "status")
    list_filter = ("status", "semester", "programme")
    search_fields = ("course__code", "course__title")
    autocomplete_fields = ("course", "semester", "programme")
    readonly_fields = ("id", "published_at", "created_at", "updated_at")


@admin.register(CourseInstructor)
class CourseInstructorAdmin(admin.ModelAdmin):
    list_display = ("user", "course_offering", "teaching_role", "can_grade")
    list_filter = ("teaching_role", "can_grade", "can_manage_content")
    search_fields = ("user__university_id", "course_offering__course__code")
    autocomplete_fields = ("user", "course_offering", "assigned_by")
    readonly_fields = ("id", "assigned_at")


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course_offering", "status", "enrolled_at")
    list_filter = ("status",)
    search_fields = ("student__university_id", "course_offering__course__code")
    autocomplete_fields = ("student", "course_offering")
    readonly_fields = ("id", "enrolled_at", "created_at", "updated_at")
