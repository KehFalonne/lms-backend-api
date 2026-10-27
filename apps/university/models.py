import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class EntityStatus(models.TextChoices):
    ACTIVE = "ACTIVE", _("Active")
    ARCHIVED = "ARCHIVED", _("Archived")


# ──────────────────────────────────────────────────────────────────────
# Faculty (database doc §11)
# ──────────────────────────────────────────────────────────────────────
class Faculty(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    code = models.CharField(
        _("code"),
        max_length=20,
        unique=True,
        db_index=True,
        help_text=_("Short uppercase code, e.g. FOC."),
    )
    name = models.CharField(_("name"), max_length=200)
    description = models.TextField(_("description"), blank=True)

    dean = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dean_of_faculties",
    )

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=EntityStatus.choices,
        default=EntityStatus.ACTIVE,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    class Meta:
        verbose_name = _("faculty")
        verbose_name_plural = _("faculties")
        ordering = ["code"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


# ──────────────────────────────────────────────────────────────────────
# Department (database doc §12)
# ──────────────────────────────────────────────────────────────────────
class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.PROTECT,
        related_name="departments",
    )
    code = models.CharField(_("code"), max_length=20)
    name = models.CharField(_("name"), max_length=200)
    description = models.TextField(_("description"), blank=True)

    hod = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hod_of_departments",
    )

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=EntityStatus.choices,
        default=EntityStatus.ACTIVE,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    class Meta:
        verbose_name = _("department")
        verbose_name_plural = _("departments")
        ordering = ["faculty__code", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["faculty", "code"],
                name="uniq_department_faculty_code",
            )
        ]
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:
        return f"{self.faculty.code}/{self.code}"

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


# ──────────────────────────────────────────────────────────────────────
# Programme (database doc §13)
# ──────────────────────────────────────────────────────────────────────
class DegreeType(models.TextChoices):
    BSC = "BSC", _("BSc")
    BA = "BA", _("BA")
    BTECH = "BTECH", _("BTech")
    MSC = "MSC", _("MSc")
    MA = "MA", _("MA")
    MBA = "MBA", _("MBA")
    PHD = "PHD", _("PhD")
    DIPLOMA = "DIPLOMA", _("Diploma")
    CERTIFICATE = "CERTIFICATE", _("Certificate")


class Programme(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="programmes",
    )
    code = models.CharField(_("code"), max_length=30)
    name = models.CharField(_("name"), max_length=200)
    degree_type = models.CharField(
        _("degree type"),
        max_length=20,
        choices=DegreeType.choices,
        default=DegreeType.BSC,
    )
    duration_years = models.PositiveIntegerField(_("duration (years)"), default=4)
    total_credits = models.PositiveIntegerField(
        _("total credits"), null=True, blank=True
    )

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=EntityStatus.choices,
        default=EntityStatus.ACTIVE,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    class Meta:
        verbose_name = _("programme")
        verbose_name_plural = _("programmes")
        ordering = ["department__code", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "code"],
                name="uniq_programme_department_code",
            )
        ]
        indexes = [models.Index(fields=["status"])]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def clean(self):
        if self.duration_years is not None and self.duration_years <= 0:
            raise ValidationError({"duration_years": _("Must be greater than 0.")})
