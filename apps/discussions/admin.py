from django.contrib import admin

from .models import DiscussionForum, DiscussionPost, DiscussionTopic


@admin.register(DiscussionForum)
class DiscussionForumAdmin(admin.ModelAdmin):
    list_display = ("title", "course_offering", "is_locked", "created_at")
    search_fields = ("title", "course_offering__course__code")
    autocomplete_fields = ("course_offering", "created_by")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(DiscussionTopic)
class DiscussionTopicAdmin(admin.ModelAdmin):
    list_display = ("title", "forum", "is_pinned", "is_locked", "created_at")
    list_filter = ("is_pinned", "is_locked")
    search_fields = ("title", "body")
    autocomplete_fields = ("forum", "created_by")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(DiscussionPost)
class DiscussionPostAdmin(admin.ModelAdmin):
    list_display = ("id", "topic", "author", "parent_post", "created_at")
    search_fields = ("body", "topic__title")
    autocomplete_fields = ("topic", "parent_post", "author")
    readonly_fields = ("id", "created_at", "updated_at")
