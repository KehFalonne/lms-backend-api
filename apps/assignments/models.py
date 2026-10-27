import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AssignmentStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Draft")
    PUBLISHED = "PUBLISHED", _("Published")
    CLOSED = "CLOSED", _("Closed")
    ARCHIVED = "ARCHIVED", _("Archived")


class SubmissionType(models.TextChoices):
    FILE_UPLOAD = "FILE_UPLOAD", _("File upload")
    TEXT_ENTRY = "TEXT_ENTRY", _("Text entry")
    FILE_AND_TEXT = "FILE_AND_TEXT", _("File and text")
    EXTERNAL_TOOL = "EXTERNAL_TOOL", _("External tool")


class LatePenaltyType(models.TextChoices):
    NONE = "NONE", _("None")
    PERCENTAGE = "PERCENTAGE", _("Percentage per day")
    POINTS = "POINTS", _("Points per day")


class SubmissionStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Draft")
    SUBMITTED = "SUBMITTED", _("Submitted")
    LATE = "LATE", _("Late")
    RETURNED = "RETURNED", _("Returned for revision")
    GRADED = "GRADED", _("Graded")
    MISSING = "MISSING", _("Missing")


# ──────────────────────────────────────────────────────────────────────
# Assignment (database doc §26)
# ──────────────────────────────────────────────────────────────────────
class Assignment(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course_offering = models.ForeignKey(
        "courses.CourseOffering",
        on_delete=models.CASCADE,
        related_name="assignments",
    )

    title = models.CharField(_("title"), max_length=250)
    description = models.TextField(_("description"), blank=True)
    instructions = models.TextField(_("instructions"), blank=True)

    max_score = models.DecimalField(
        _("max score"),
        max_digits=6,
        decimal_places=2,
        default=100,
    )

    available_from = models.DateTimeField(_("available from"), null=True, blank=True)
    due_at = models.DateTimeField(_("due at"))
    available_until = models.DateTimeField(_("available until"), null=True, blank=True)

    allow_late_submission = models.BooleanField(
        _("allow late submission"), default=True
    )
    late_penalty_type = models.CharField(
        _("late penalty type"),
        max_length=20,
        choices=LatePenaltyType.choices,
        default=LatePenaltyType.NONE,
    )
    late_penalty_value = models.DecimalField(
        _("late penalty value"),
        max_digits=6,
        decimal_places=2,
        default=0,
    )

    submission_type = models.CharField(
        _("submission type"),
        max_length=20,
        choices=SubmissionType.choices,
        default=SubmissionType.FILE_UPLOAD,
    )
    max_attempts = models.PositiveSmallIntegerField(_("max attempts"), default=1)

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.DRAFT,
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments_created",
    )
    published_at = models.DateTimeField(_("published at"), null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("assignment")
        verbose_name_plural = _("assignments")
        ordering = ["-due_at"]
        indexes = [
            models.Index(fields=["course_offering", "status"]),
            models.Index(fields=["due_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.course_offering_id} — {self.title}"

    def clean(self):
        if self.available_from and self.due_at and self.available_from >= self.due_at:
            raise ValidationError(
                {"due_at": _("Due date must be after availability start.")}
            )
        if self.late_penalty_value < 0:
            raise ValidationError(
                {"late_penalty_value": _("Penalty cannot be negative.")}
            )

    @property
    def is_open(self) -> bool:
        now = timezone.now()
        if self.status != AssignmentStatus.PUBLISHED:
            return False
        if self.available_from and now < self.available_from:
            return False
        if self.available_until and now > self.available_until:
            return False
        return True

    @property
    def is_past_due(self) -> bool:
        return timezone.now() > self.due_at

    def publish(self):
        self.status = AssignmentStatus.PUBLISHED
        if not self.published_at:
            self.published_at = timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])

    def close(self):
        self.status = AssignmentStatus.CLOSED
        self.save(update_fields=["status", "updated_at"])


# ──────────────────────────────────────────────────────────────────────
# Submission (database doc §27)
# ──────────────────────────────────────────────────────────────────────
class AssignmentSubmission(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assignment_submissions",
    )

    attempt_number = models.PositiveSmallIntegerField(_("attempt"), default=1)
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=SubmissionStatus.choices,
        default=SubmissionStatus.DRAFT,
        db_index=True,
    )

    submitted_at = models.DateTimeField(_("submitted at"), null=True, blank=True)
    is_late = models.BooleanField(_("late"), default=False)

    text_content = models.TextField(_("text content"), blank=True)

    score = models.DecimalField(
        _("score"),
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    feedback = models.TextField(_("feedback"), blank=True)

    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions_graded",
    )
    graded_at = models.DateTimeField(_("graded at"), null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("assignment submission")
        verbose_name_plural = _("assignment submissions")
        ordering = ["-submitted_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "student", "attempt_number"],
                name="uniq_submission_attempt",
            ),
        ]
        indexes = [
            models.Index(fields=["assignment", "student"]),
            models.Index(fields=["student", "status"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.student_id} → {self.assignment_id} (attempt {self.attempt_number})"
        )


# ──────────────────────────────────────────────────────────────────────
# Submission files (database doc §28)
# ──────────────────────────────────────────────────────────────────────
class SubmissionFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    submission = models.ForeignKey(
        AssignmentSubmission,
        on_delete=models.CASCADE,
        related_name="files",
    )
    file = models.ForeignKey(
        "files.File",
        on_delete=models.PROTECT,
        related_name="submission_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("submission file")
        verbose_name_plural = _("submission files")
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "file"],
                name="uniq_submission_file",
            ),
        ]


# ──────────────────────────────────────────────────────────────────────
# Feedback (database doc §29) — separate so multiple entries are possible
# ──────────────────────────────────────────────────────────────────────
class Feedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    submission = models.ForeignKey(
        AssignmentSubmission,
        on_delete=models.CASCADE,
        related_name="feedback_entries",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedback_authored",
    )
    content = models.TextField(_("content"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("feedback")
        verbose_name_plural = _("feedback")
        ordering = ["created_at"]
