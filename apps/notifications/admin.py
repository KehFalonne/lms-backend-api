from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "type", "title", "read_at", "created_at")
    list_filter = ("type", "read_at")
    search_fields = ("recipient__university_id", "title", "message")
    autocomplete_fields = ("recipient",)
    readonly_fields = ("id", "created_at")
