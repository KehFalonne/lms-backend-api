from django.contrib import admin

from .models import Department, Faculty, Programme


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "dean", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("code", "name")
    autocomplete_fields = ("dean",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "faculty", "hod", "status")
    list_filter = ("status", "faculty")
    search_fields = ("code", "name")
    autocomplete_fields = ("faculty", "hod")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "department",
        "degree_type",
        "duration_years",
        "status",
    )
    list_filter = ("status", "degree_type", "department")
    search_fields = ("code", "name")
    autocomplete_fields = ("department",)
    readonly_fields = ("id", "created_at", "updated_at")
