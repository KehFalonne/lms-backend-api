import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.university.models import Department


class CourseStatus(models.TextChoices):
    ACTIVE = "ACTIVE", _("Active")
    ARCHIVED = "ARCHIVED", _("Archived")


class Course(models.Model):
    """Database doc §16."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="courses",
    )
    code = models.CharField(_("code"), max_length=20)
    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)

    credits = models.PositiveSmallIntegerField(_("credits"), default=3)
    level = models.PositiveSmallIntegerField(
        _("level"),
        default=100,
        help_text=_("100, 200, 300, 400, 500, 600, 700."),
    )
    course_type = models.CharField(_("course type"), max_length=20, default="CORE")

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=CourseStatus.choices,
        default=CourseStatus.ACTIVE,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    class Meta:
        verbose_name = _("course")
        verbose_name_plural = _("courses")
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "code"],
                name="uniq_course_department_code",
            ),
        ]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["status"]),
            models.Index(fields=["level"]),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.title}"

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def clean(self):
        if self.credits is not None and self.credits <= 0:
            raise ValidationError({"credits": _("Must be greater than 0.")})


class CoursePrerequisite(models.Model):
    """Database doc §17."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="prerequisites",
    )
    prerequisite_course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="required_by_courses",
    )
    minimum_grade = models.CharField(
        _("minimum grade"),
        max_length=10,
        blank=True,
        help_text=_("Optional minimum grade, e.g. C, D+."),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("course prerequisite")
        verbose_name_plural = _("course prerequisites")
        constraints = [
            models.UniqueConstraint(
                fields=["course", "prerequisite_course"],
                name="uniq_course_prerequisite",
            ),
            models.CheckConstraint(
                check=~models.Q(course=models.F("prerequisite_course")),
                name="course_prerequisite_not_self",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.course.code} requires {self.prerequisite_course.code}"


# ──────────────────────────────────────────────────────────────────────
# Course Offering (database doc §18)
# ──────────────────────────────────────────────────────────────────────
class OfferingStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Draft")
    ACTIVE = "ACTIVE", _("Active")
    COMPLETED = "COMPLETED", _("Completed")
    ARCHIVED = "ARCHIVED", _("Archived")
    CANCELLED = "CANCELLED", _("Cancelled")


class TeachingRole(models.TextChoices):
    PRIMARY_INSTRUCTOR = "PRIMARY_INSTRUCTOR", _("Primary Instructor")
    INSTRUCTOR = "INSTRUCTOR", _("Instructor")
    TEACHING_ASSISTANT = "TEACHING_ASSISTANT", _("Teaching Assistant")
    GRADER = "GRADER", _("Grader")


class EnrollmentStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    ACTIVE = "ACTIVE", _("Active")
    WITHDRAWN = "WITHDRAWN", _("Withdrawn")
    COMPLETED = "COMPLETED", _("Completed")
    SUSPENDED = "SUSPENDED", _("Suspended")


class CourseOffering(models.Model):
    """Database doc §18 — a course delivered in a specific semester."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="offerings",
    )
    semester = models.ForeignKey(
        "academics.Semester",
        on_delete=models.PROTECT,
        related_name="course_offerings",
    )
    programme = models.ForeignKey(
        "university.Programme",
        on_delete=models.PROTECT,
        related_name="course_offerings",
    )

    section = models.CharField(_("section"), max_length=10, default="A")
    capacity = models.PositiveIntegerField(_("capacity"), default=100)

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=OfferingStatus.choices,
        default=OfferingStatus.DRAFT,
        db_index=True,
    )

    published_at = models.DateTimeField(_("published at"), null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("course offering")
        verbose_name_plural = _("course offerings")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "semester", "programme", "section"],
                name="uniq_course_offering_natural_key",
            ),
        ]
        indexes = [
            models.Index(fields=["course", "semester"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.course.code} · {self.semester} · {self.section}"

    @property
    def enrolled_count(self) -> int:
        # If the queryset was annotated with a count, use that (avoids N+1).
        cached = self.__dict__.get("_enrolled_count_annotation")
        if cached is not None:
            return cached
        return self.enrollments.filter(status=EnrollmentStatus.ACTIVE).count()

    @enrolled_count.setter
    def enrolled_count(self, value):
        # Allow Django to set this when the queryset is annotated.
        self.__dict__["_enrolled_count_annotation"] = value

    @property
    def instructor_count(self) -> int:
        cached = self.__dict__.get("_instructor_count_annotation")
        if cached is not None:
            return cached
        return self.instructors.count()

    @instructor_count.setter
    def instructor_count(self, value):
        self.__dict__["_instructor_count_annotation"] = value

    @property
    def is_full(self) -> bool:
        return self.enrolled_count >= self.capacity


class CourseInstructor(models.Model):
    """Database doc §19 — a staff member teaching an offering."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course_offering = models.ForeignKey(
        CourseOffering,
        on_delete=models.CASCADE,
        related_name="instructors",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="teaching_assignments",
    )
    teaching_role = models.CharField(
        _("teaching role"),
        max_length=30,
        choices=TeachingRole.choices,
        default=TeachingRole.INSTRUCTOR,
    )

    can_manage_content = models.BooleanField(default=False)
    can_grade = models.BooleanField(default=False)
    can_manage_assessments = models.BooleanField(default=False)
    can_manage_students = models.BooleanField(default=False)

    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="instructor_assignments_made",
    )

    class Meta:
        verbose_name = _("course instructor")
        verbose_name_plural = _("course instructors")
        ordering = ["teaching_role", "assigned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["course_offering", "user", "teaching_role"],
                name="uniq_instructor_assignment",
            ),
        ]
        indexes = [
            models.Index(fields=["course_offering", "user"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.university_id} → {self.course_offering_id} ({self.teaching_role})"


class CourseEnrollment(models.Model):
    """Database doc §11.1 — a student enrolled in an offering."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    course_offering = models.ForeignKey(
        CourseOffering,
        on_delete=models.PROTECT,
        related_name="enrollments",
    )
    student = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="enrollments",
    )

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.ACTIVE,
        db_index=True,
    )

    enrolled_at = models.DateTimeField(auto_now_add=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    final_status = models.CharField(_("final status"), max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("course enrollment")
        verbose_name_plural = _("course enrollments")
        ordering = ["-enrolled_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["course_offering", "student"],
                name="uniq_course_enrollment",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["course_offering", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.student.university_id} → {self.course_offering_id}"
