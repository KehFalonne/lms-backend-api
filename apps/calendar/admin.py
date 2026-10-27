from django.contrib import admin

from .models import CalendarEvent


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ("title", "event_type", "start_at", "course_offering", "created_by")
    list_filter = ("event_type", "is_all_day")
    search_fields = ("title", "description", "course_offering__course__code")
    autocomplete_fields = ("course_offering", "created_by")
    readonly_fields = ("id", "created_at", "updated_at")
