import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class EventType(models.TextChoices):
    LECTURE = "LECTURE", _("Lecture")
    ASSIGNMENT_DUE = "ASSIGNMENT_DUE", _("Assignment due")
    EXAM = "EXAM", _("Exam")
    QUIZ = "QUIZ", _("Quiz")
    MEETING = "MEETING", _("Meeting")
    OTHER = "OTHER", _("Other")


class CalendarEvent(models.Model):
    """Database doc §49 — explicit user-created event."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course_offering = models.ForeignKey(
        "courses.CourseOffering",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="calendar_events",
        help_text=_("Optional — personal events may not belong to a course."),
    )

    title = models.CharField(_("title"), max_length=250)
    description = models.TextField(_("description"), blank=True)

    event_type = models.CharField(
        _("event type"),
        max_length=20,
        choices=EventType.choices,
        default=EventType.OTHER,
        db_index=True,
    )

    start_at = models.DateTimeField(_("start at"), db_index=True)
    end_at = models.DateTimeField(_("end at"))
    is_all_day = models.BooleanField(_("all day"), default=False)

    location = models.CharField(_("location"), max_length=200, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="calendar_events_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("calendar event")
        verbose_name_plural = _("calendar events")
        ordering = ["start_at"]
        indexes = [
            models.Index(fields=["start_at"]),
            models.Index(fields=["course_offering", "start_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} @ {self.start_at}"

    def clean(self):
        if self.start_at and self.end_at and self.start_at > self.end_at:
            raise ValidationError({"end_at": _("End must be after start.")})
