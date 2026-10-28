import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class GradeSourceType(models.TextChoices):
    ASSIGNMENT = "ASSIGNMENT", _("Assignment")
    ASSESSMENT = "ASSESSMENT", _("Assessment")
    MANUAL = "MANUAL", _("Manual")
    EXTERNAL = "EXTERNAL", _("External")


class GradeStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Draft")
    PUBLISHED = "PUBLISHED", _("Published")
    VOID = "VOID", _("Void")


# ──────────────────────────────────────────────────────────────────────
# Category (database doc §39)
# ──────────────────────────────────────────────────────────────────────
class GradeCategory(models.Model):
    """
    A weighted bucket like "Assignments (40%)" or "Final Exam (60%)".

    Category weights must sum to 100% for the offering (validated at the
    service layer, not the DB — business rule).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course_offering = models.ForeignKey(
        "courses.CourseOffering",
        on_delete=models.CASCADE,
        related_name="grade_categories",
    )
    name = models.CharField(_("name"), max_length=100)
    weight = models.DecimalField(
        _("weight (%)"),
        max_digits=5,
        decimal_places=2,
        help_text=_("Percentage weight of this category in the final grade."),
    )
    position = models.PositiveSmallIntegerField(_("position"), default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("grade category")
        verbose_name_plural = _("grade categories")
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["course_offering", "name"],
                name="uniq_grade_category_name",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.course_offering_id} — {self.name} ({self.weight}%)"


# ──────────────────────────────────────────────────────────────────────
# GradeItem (database doc §40)
# ──────────────────────────────────────────────────────────────────────
class GradeItem(models.Model):
    """
    A single graded activity inside a category.

    `source_type` + `source_id` link back to the originating Assignment,
    Assessment, or nothing (MANUAL). This is a polymorphic link — integrity
    is enforced at the service layer, not by an FK.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course_offering = models.ForeignKey(
        "courses.CourseOffering",
        on_delete=models.CASCADE,
        related_name="grade_items",
    )
    category = models.ForeignKey(
        GradeCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )

    name = models.CharField(_("name"), max_length=200)
    max_score = models.DecimalField(
        _("max score"), max_digits=7, decimal_places=2, default=100
    )
    weight = models.DecimalField(
        _("weight (%)"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Optional within-category weight. If null, items share equally."),
    )

    source_type = models.CharField(
        _("source type"),
        max_length=20,
        choices=GradeSourceType.choices,
        default=GradeSourceType.MANUAL,
        db_index=True,
    )
    source_id = models.UUIDField(_("source id"), null=True, blank=True, db_index=True)

    position = models.PositiveSmallIntegerField(_("position"), default=1)
    is_published = models.BooleanField(_("published"), default=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("grade item")
        verbose_name_plural = _("grade items")
        ordering = ["category__position", "position"]
        indexes = [
            models.Index(fields=["course_offering", "category"]),
            models.Index(fields=["source_type", "source_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} (/{self.max_score})"


# ──────────────────────────────────────────────────────────────────────
# Grade (database doc §41)
# ──────────────────────────────────────────────────────────────────────
class Grade(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    grade_item = models.ForeignKey(
        GradeItem,
        on_delete=models.CASCADE,
        related_name="grades",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="grades",
    )

    score = models.DecimalField(
        _("score"),
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    percentage = models.DecimalField(
        _("percentage"),
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    letter_grade = models.CharField(_("letter grade"), max_length=5, blank=True)

    feedback = models.TextField(_("feedback"), blank=True)

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=GradeStatus.choices,
        default=GradeStatus.DRAFT,
        db_index=True,
    )

    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grades_assigned",
    )
    graded_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("grade")
        verbose_name_plural = _("grades")
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["grade_item", "student"],
                name="uniq_grade_per_item_student",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["grade_item", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.student_id} → {self.grade_item.name}: {self.score}"

    def save(self, *args, **kwargs):
        # Coerce everything to Decimal, then compute percentage
        if (
            self.score is not None
            and self.grade_item.max_score
            and self.grade_item.max_score > 0
        ):
            from decimal import Decimal as D

            score = D(str(self.score))
            max_score = D(str(self.grade_item.max_score))
            self.percentage = (score / max_score * D("100")).quantize(D("0.01"))
        super().save(*args, **kwargs)


# ──────────────────────────────────────────────────────────────────────
# GradeHistory (database doc §42) — immutable trail of every grade change
# ──────────────────────────────────────────────────────────────────────
class GradeHistory(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    grade = models.ForeignKey(
        Grade,
        on_delete=models.CASCADE,
        related_name="history",
    )
    previous_score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    new_score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    reason = models.CharField(max_length=250, blank=True)

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("grade history")
        verbose_name_plural = _("grade history")
        ordering = ["-changed_at"]

    def __str__(self) -> str:
        return f"{self.grade_id}: {self.previous_score} → {self.new_score}"


class AppealStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    UNDER_REVIEW = "UNDER_REVIEW", _("Under review")
    APPROVED = "APPROVED", _("Approved")
    DENIED = "DENIED", _("Denied")
    WITHDRAWN = "WITHDRAWN", _("Withdrawn")


class GradeAppeal(models.Model):
    """
    Student-initiated appeal of a published grade (backend doc §4.3).

    Only one PENDING / UNDER_REVIEW appeal is allowed per grade.
    Approving creates a GradeHistory entry and updates the grade score.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    grade = models.ForeignKey(
        Grade,
        on_delete=models.CASCADE,
        related_name="appeals",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="grade_appeals",
    )

    reason = models.TextField(_("reason"))
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=AppealStatus.choices,
        default=AppealStatus.PENDING,
        db_index=True,
    )

    original_score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )
    resolved_score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
    )

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grade_appeals_reviewed",
    )
    reviewer_notes = models.TextField(_("reviewer notes"), blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("grade appeal")
        verbose_name_plural = _("grade appeals")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["student", "-created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["grade", "student"],
                condition=models.Q(status__in=["PENDING", "UNDER_REVIEW"]),
                name="uniq_active_appeal_per_grade",
            ),
        ]

    def __str__(self) -> str:
        return f"Appeal {self.id} on {self.grade_id} ({self.status})"
