import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class DiscussionForum(models.Model):
    """Database doc §15.1."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course_offering = models.ForeignKey(
        "courses.CourseOffering",
        on_delete=models.CASCADE,
        related_name="forums",
    )
    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    is_locked = models.BooleanField(_("locked"), default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="forums_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("discussion forum")
        verbose_name_plural = _("discussion forums")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.course_offering_id} — {self.title}"


class DiscussionTopic(models.Model):
    """Database doc §15.2."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    forum = models.ForeignKey(
        DiscussionForum,
        on_delete=models.CASCADE,
        related_name="topics",
    )
    title = models.CharField(_("title"), max_length=200)
    body = models.TextField(_("body"))

    is_pinned = models.BooleanField(_("pinned"), default=False, db_index=True)
    is_locked = models.BooleanField(_("locked"), default=False)
    is_edited = models.BooleanField(_("edited"), default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="topics_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    class Meta:
        verbose_name = _("discussion topic")
        verbose_name_plural = _("discussion topics")
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self) -> str:
        return self.title


class DiscussionPost(models.Model):
    """Database doc §15.3 — supports threaded replies via parent_post."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    topic = models.ForeignKey(
        DiscussionTopic,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    parent_post = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    body = models.TextField(_("body"))

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discussion_posts",
    )

    is_edited = models.BooleanField(_("edited"), default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    class Meta:
        verbose_name = _("discussion post")
        verbose_name_plural = _("discussion posts")
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["topic", "created_at"]),
            models.Index(fields=["parent_post"]),
        ]

    def __str__(self) -> str:
        return f"Post {self.id} by {self.author_id}"
