from django.contrib import admin

from .models import AcademicYear, Semester


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "status", "is_current")
    list_filter = ("status", "is_current")
    search_fields = ("name",)
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ("name", "academic_year", "sequence", "status", "is_current")
    list_filter = ("status", "is_current", "academic_year")
    search_fields = ("name", "code", "academic_year__name")
    autocomplete_fields = ("academic_year",)
    readonly_fields = ("id", "created_at", "updated_at")
