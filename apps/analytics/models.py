import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class LearningEventType(models.TextChoices):
    COURSE_VIEWED = "COURSE_VIEWED", _("Course viewed")
    MODULE_VIEWED = "MODULE_VIEWED", _("Module viewed")
    CONTENT_VIEWED = "CONTENT_VIEWED", _("Content viewed")
    CONTENT_COMPLETED = "CONTENT_COMPLETED", _("Content completed")
    PDF_OPENED = "PDF_OPENED", _("PDF opened")
    PDF_DOWNLOADED = "PDF_DOWNLOADED", _("PDF downloaded")
    ASSIGNMENT_OPENED = "ASSIGNMENT_OPENED", _("Assignment opened")
    ASSIGNMENT_SUBMITTED = "ASSIGNMENT_SUBMITTED", _("Assignment submitted")
    ASSESSMENT_STARTED = "ASSESSMENT_STARTED", _("Assessment started")
    ASSESSMENT_SUBMITTED = "ASSESSMENT_SUBMITTED", _("Assessment submitted")
    DISCUSSION_VIEWED = "DISCUSSION_VIEWED", _("Discussion viewed")
    LOGIN = "LOGIN", _("Login")


class LearningEvent(models.Model):
    """
    Append-only event stream (database doc §24.1).

    Partitioned by occurred_at in production once it grows large.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_events",
    )
    course_offering = models.ForeignKey(
        "courses.CourseOffering",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="learning_events",
    )

    event_type = models.CharField(
        _("event type"),
        max_length=40,
        choices=LearningEventType.choices,
        db_index=True,
    )
    entity_type = models.CharField(_("entity type"), max_length=40, blank=True)
    entity_id = models.UUIDField(_("entity id"), null=True, blank=True)

    metadata = models.JSONField(_("metadata"), default=dict, blank=True)

    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("learning event")
        verbose_name_plural = _("learning events")
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["student", "-occurred_at"]),
            models.Index(fields=["course_offering", "-occurred_at"]),
            models.Index(fields=["event_type", "-occurred_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.student_id} — {self.event_type} @ {self.occurred_at}"


class StudentCourseProgress(models.Model):
    """
    Cached progress snapshot per (student, offering) (database doc §24.2).

    Recalculated asynchronously by Celery when content completion changes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_progress",
    )
    course_offering = models.ForeignKey(
        "courses.CourseOffering",
        on_delete=models.CASCADE,
        related_name="student_progress",
    )

    progress_percentage = models.DecimalField(
        _("progress %"),
        max_digits=5,
        decimal_places=2,
        default=0,
    )
    content_completed = models.PositiveIntegerField(default=0)
    content_total = models.PositiveIntegerField(default=0)

    last_activity_at = models.DateTimeField(null=True, blank=True)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("student course progress")
        verbose_name_plural = _("student course progress")
        constraints = [
            models.UniqueConstraint(
                fields=["student", "course_offering"],
                name="uniq_student_offering_progress",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student_id} → {self.course_offering_id}: {self.progress_percentage}%"


class ContentProgress(models.Model):
    """
    Per-content-item completion tracking (database doc §24).

    Added now that we're doing analytics — content was placeholder in Sprint 5.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="content_progress",
    )
    content_item = models.ForeignKey(
        "content.ContentItem",
        on_delete=models.CASCADE,
        related_name="progress_records",
    )

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=[
            ("NOT_STARTED", _("Not started")),
            ("IN_PROGRESS", _("In progress")),
            ("COMPLETED", _("Completed")),
        ],
        default="NOT_STARTED",
        db_index=True,
    )
    progress_percent = models.PositiveSmallIntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_accessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("content progress")
        verbose_name_plural = _("content progress")
        constraints = [
            models.UniqueConstraint(
                fields=["student", "content_item"],
                name="uniq_content_progress",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student_id} → {self.content_item_id}: {self.status}"
