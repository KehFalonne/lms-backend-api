"""
Custom User model — created before any other migration, per
backend architecture doc §7.1.

Base: AbstractBaseUser + PermissionsMixin.
Primary key: UUID (per backend doc §3).
"""

import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class UserStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    ACTIVE = "ACTIVE", _("Active")
    SUSPENDED = "SUSPENDED", _("Suspended")
    INACTIVE = "INACTIVE", _("Inactive")
    LOCKED = "LOCKED", _("Locked")


class User(AbstractBaseUser, PermissionsMixin):
    """
    GU-LMS user.

    Both students and staff live in this single table; role-specific data
    lives in `student_profiles` / `staff_profiles` (added in Sprint 2).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    university_id = models.CharField(
        _("university ID"),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_("Matricule (student) or staff number, e.g. GU2026001."),
    )
    email = models.EmailField(_("email address"), unique=True, db_index=True)

    first_name = models.CharField(_("first name"), max_length=100)
    middle_name = models.CharField(_("middle name"), max_length=100, blank=True)
    last_name = models.CharField(_("last name"), max_length=100)

    phone = models.CharField(_("phone"), max_length=30, blank=True)

    # Placeholder for File FK — replaced in Sprint 6 when the File model exists.
    avatar = models.CharField(
        _("avatar"),
        max_length=500,
        blank=True,
        help_text=_("Placeholder — will become a File FK in Sprint 6."),
    )

    status = models.CharField(
        _("status"),
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.PENDING,
        db_index=True,
    )
    email_verified_at = models.DateTimeField(
        _("email verified at"), null=True, blank=True
    )

    # Django admin flags (kept per doc; RBAC is separate, added in Sprint 3).
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into the Django admin."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Designates whether this user should be treated as active."),
    )

    last_login_at = models.DateTimeField(_("last login"), null=True, blank=True)

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["university_id", "first_name", "last_name"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.university_id} — {self.get_full_name()}"

    def get_full_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p).strip()

    def get_short_name(self) -> str:
        return self.first_name

    def mark_email_verified(self):
        self.email_verified_at = timezone.now()
        self.save(update_fields=["email_verified_at", "updated_at"])

    def touch_last_login(self):
        self.last_login_at = timezone.now()
        self.save(update_fields=["last_login_at", "updated_at"])

    def get_role_codes(self) -> list[str]:
        """
        Distinct role codes for this user across all scopes.

        Called on every request via DRF permissions — kept cheap by
        prefetching in authentication (see permissions.py).
        """
        cached = getattr(self, "_role_codes_cache", None)
        if cached is not None:
            return cached

        codes = set(self.user_roles.values_list("role__code", flat=True))
        if self.is_superuser:
            codes.add("SUPER_ADMIN")

        self._role_codes_cache = sorted(codes)
        return self._role_codes_cache

    def get_permission_codes(self) -> list[str]:
        """
        Distinct permission codes granted through any role assignment.
        """
        cached = getattr(self, "_permission_codes_cache", None)
        if cached is not None:
            return cached

        codes = set(
            RolePermission.objects.filter(role__user_roles__user=self).values_list(
                "permission__code", flat=True
            )
        )
        self._permission_codes_cache = sorted(codes)
        return self._permission_codes_cache

    def has_permission_code(self, *codes: str) -> bool:
        if self.is_superuser:
            return True
        return bool(set(codes) & set(self.get_permission_codes()))

    def has_role(self, *codes: str) -> bool:
        if self.is_superuser:
            return True
        return bool(set(codes) & set(self.get_role_codes()))


# Student Profile Model
class StudentProfile(models.Model):
    """
    Academic profile for student users.

    `programme_id` is stored as UUID for Sprint 2 and converted to a proper
    ForeignKey to `university.Programme` in Sprint 4.
    """

    # Student Profile Status enum
    class StudentStatus(models.TextChoices):
        ACTIVE = "ACTIVE", _("Acitve")
        On_LEAVE = "On_LEAVE", _("On leave")
        SUSPENDED = "SUSPENDED", _("Suspended")
        GRADUATED = "GRADUATED", _("Graduated")
        WITHDRAWN = "WITHDRAWN", _("Withdrawn")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        User, on_delete=models.PROTECT, related_name="student_profile"
    )

    matricule_number = models.CharField(
        _("matrucule number"),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=("Business identifier, e.g. GU-2026-001234."),
    )

    programme = models.ForeignKey(
        "university.Programme",
        on_delete=models.SET_NULL,  # would change this to PROTECT later on
        null=True,
        blank=True,
        related_name="students",
    )
    current_level = models.PositiveIntegerField(_("current level"), default=100)
    admission_year = models.PositiveIntegerField(_("admission year"))
    admission_date = models.DateField(_("admission date"), null=True, blank=True)
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=StudentStatus.choices,
        default=StudentStatus.ACTIVE,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("student profile")
        verbose_name_plural = _("student profiles")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["matricule_number"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.matricule_number} - {self.user.get_full_name()}"


# Staff Profile Model
class StaffProfile(models.Model):
    """
    Academic/administrative profile for staff users.

    `department_id` is stored as UUID for Sprint 2 and converted to a proper
    ForeignKey to `university.Department` in Sprint 4.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        User, on_delete=models.PROTECT, related_name="staff_profile"
    )

    staff_number = models.CharField(
        _("staff number"),
        max_length=50,
        unique=True,
        db_index=True,
    )
    department = models.ForeignKey(
        "university.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff",
    )
    job_title = models.CharField(_("job title"), max_length=150, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("staff profile")
        verbose_name_plural = _("staff profiles")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["staff_number"]),
        ]

    def __str__(self) -> str:
        return f"{self.staff_number} ({self.user.get_full_name()})"

    # User Session (database doc section 23) -refresh-token lifecycle tracking


class UserSession(models.Model):
    """
    Tracks issued refresh tokens so we can revoke sessions and audit logins.

    We store a SHA-256 hash of the refresh token (never the raw token).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sessions",
    )

    refresh_token_hash = models.CharField(
        _("refresh token hash"),
        max_length=128,
        db_index=True,
        help_text=_("SHA-256 hash of the refresh token."),
    )

    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    user_agent = models.TextField(_("user agent"), blank=True)

    expires_at = models.DateTimeField(_("expires at"))
    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("user session")
        verbose_name_plural = _("user sessions")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "revoked_at"]),
            models.Index(fields=["refresh_token_hash"]),
        ]

    def __str__(self) -> str:
        return f"Session {self.id} for {self.user.university_id}"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()


# ──────────────────────────────────────────────────────────────────────
# RBAC — Roles, Permissions, RolePermissions, UserRoles
# (Database doc §4.2 – §4.5)
# ──────────────────────────────────────────────────────────────────────


class RoleScope(models.TextChoices):
    """
    Where a role assignment applies (database doc §4.5).

    A lecturer with `RoleScope.COURSE` only has that role inside the
    specific course offering they were assigned to.
    """

    GLOBAL = "GLOBAL", _("Global")
    FACULTY = "FACULTY", _("Faculty")
    DEPARTMENT = "DEPARTMENT", _("Department")
    COURSE = "COURSE", _("Course")


class Role(models.Model):
    """
    A named set of permissions (backend doc §10).

    System roles (`is_system_role=True`) ship with the platform and cannot
    be deleted — they may still be edited by SUPER_ADMIN.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    code = models.CharField(
        _("code"),
        max_length=100,
        unique=True,
        db_index=True,
        help_text=_("Stable identifier, uppercase (e.g. LECTURER, HOD)."),
    )
    name = models.CharField(_("name"), max_length=100)
    description = models.TextField(_("description"), blank=True)

    is_system_role = models.BooleanField(
        _("system role"),
        default=False,
        help_text=_("Platform-provided roles that must not be deleted."),
    )
    permissions = models.ManyToManyField(
        "Permission",
        through="RolePermission",
        related_name="roles",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("role")
        verbose_name_plural = _("roles")
        ordering = ["code"]
        indexes = [models.Index(fields=["code"])]

    def __str__(self) -> str:
        return f"{self.code}"

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


class Permission(models.Model):
    """
    A granular action (backend doc §4.3).

    Codes are dot-namespaced by module: `courses.create`, `grades.manage`.
    Permissions are seeded once (see seed_rbac command) and referenced by
    code in views.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    code = models.CharField(
        _("code"),
        max_length=150,
        unique=True,
        db_index=True,
        help_text=_("Dot-namespaced action code, e.g. `courses.create`."),
    )
    name = models.CharField(_("name"), max_length=150)
    module = models.CharField(_("module"), max_length=100, db_index=True)
    description = models.TextField(_("description"), blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("permission")
        verbose_name_plural = _("permissions")
        ordering = ["module", "code"]
        indexes = [models.Index(fields=["module", "code"])]

    def __str__(self) -> str:
        return self.code

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().lower()
        super().save(*args, **kwargs)


class RolePermission(models.Model):
    """Assigns a permission to a role (database doc §4.4)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name="role_permissions"
    )
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name="permission_roles"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("role permission")
        verbose_name_plural = _("role permissions")
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"], name="uniq_role_permission"
            )
        ]
        indexes = [models.Index(fields=["role", "permission"])]

    def __str__(self) -> str:
        return f"{self.role.code} → {self.permission.code}"


class UserRole(models.Model):
    """
    Assigns a role to a user, optionally scoped (database doc §4.5).

    Scope rules:
      • GLOBAL      → applies everywhere; all scope FKs are NULL
      • FACULTY     → requires `faculty_id`
      • DEPARTMENT  → requires `department_id`
      • COURSE      → requires `course_offering_id`
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="user_roles")

    scope_type = models.CharField(
        _("scope"),
        max_length=20,
        choices=RoleScope.choices,
        default=RoleScope.GLOBAL,
        db_index=True,
    )

    faculty = models.ForeignKey(
        "university.Faculty",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_roles",
    )
    department = models.ForeignKey(
        "university.Department",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_roles",
    )
    course_offering_id = models.UUIDField(
        _("course offering"), null=True, blank=True, db_index=True
    )

    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="roles_assigned",
    )

    class Meta:
        verbose_name = _("user role")
        verbose_name_plural = _("user roles")
        ordering = ["-assigned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "role",
                    "scope_type",
                    "faculty_id",
                    "department_id",
                    "course_offering_id",
                ],
                name="uniq_user_role_scoped",
            )
        ]
        indexes = [
            models.Index(fields=["user", "role"]),
            models.Index(fields=["user", "scope_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.university_id} → {self.role.code} ({self.scope_type})"

    def clean(self):
        from django.core.exceptions import ValidationError as DjangoValidationError

        if self.scope_type == RoleScope.FACULTY and not self.faculty_id:
            raise DjangoValidationError({"faculty_id": "Required for FACULTY scope."})
        if self.scope_type == RoleScope.DEPARTMENT and not self.department_id:
            raise DjangoValidationError(
                {"department_id": "Required for DEPARTMENT scope."}
            )
        if self.scope_type == RoleScope.COURSE and not self.course_offering_id:
            raise DjangoValidationError(
                {"course_offering_id": "Required for COURSE scope."}
            )
