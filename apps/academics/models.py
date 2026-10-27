import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class AcademicYearStatus(models.TextChoices):
    UPCOMING = "UPCOMING", _("Upcoming")
    ACTIVE = "ACTIVE", _("Active")
    COMPLETED = "COMPLETED", _("Completed")
    ARCHIVED = "ARCHIVED", _("Archived")


class SemesterStatus(models.TextChoices):
    UPCOMING = "UPCOMING", _("Upcoming")
    ACTIVE = "ACTIVE", _("Active")
    COMPLETED = "COMPLETED", _("Completed")
    ARCHIVED = "ARCHIVED", _("Archived")


class AcademicYear(models.Model):
    """Database doc §14."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(
        _("name"),
        max_length=30,
        unique=True,
        db_index=True,
        help_text=_("e.g. 2026/2027."),
    )
    start_date = models.DateField(_("start date"))
    end_date = models.DateField(_("end date"))

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=AcademicYearStatus.choices,
        default=AcademicYearStatus.UPCOMING,
        db_index=True,
    )
    is_current = models.BooleanField(_("current"), default=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("academic year")
        verbose_name_plural = _("academic years")
        ordering = ["-start_date"]

    def __str__(self) -> str:
        return self.name

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError({"end_date": _("End date must be after start date.")})


class Semester(models.Model):
    """Database doc §15."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="semesters",
    )
    name = models.CharField(_("name"), max_length=50)
    code = models.CharField(_("code"), max_length=20)
    sequence = models.PositiveSmallIntegerField(_("sequence"))

    start_date = models.DateField(_("start date"))
    end_date = models.DateField(_("end date"))

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=SemesterStatus.choices,
        default=SemesterStatus.UPCOMING,
        db_index=True,
    )
    is_current = models.BooleanField(_("current"), default=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("semester")
        verbose_name_plural = _("semesters")
        ordering = ["academic_year__name", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "code"],
                name="uniq_semester_year_code",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.academic_year.name} — {self.name}"

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError({"end_date": _("End date must be after start date.")})
