from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.academics.models import AcademicYear, Semester
from apps.accounts.models import StudentProfile, User, UserRole
from apps.announcements.models import Announcement
from apps.assessments.models import Assessment
from apps.assignments.models import Assignment, AssignmentSubmission
from apps.audit.services.audit_service import AuditService
from apps.common.audit_context import get_audit_actor, get_audit_request
from apps.content.models import ContentItem
from apps.courses.models import (
    Course,
    CourseEnrollment,
    CourseInstructor,
    CourseOffering,
)
from apps.grading.models import Grade, GradeAppeal
from apps.university.models import Department, Faculty, Programme


def _snapshot(instance, fields):
    values = {}
    for field in fields:
        value = getattr(instance, field, None)
        values[field] = str(value) if value is not None else None
    return values


@receiver(pre_save, sender=User)
def capture_user_before_save(sender, instance, **kwargs):
    instance._audit_old_values = None
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).first()
        if old:
            instance._audit_old_values = _snapshot(
                old, ("university_id", "email", "status", "is_active")
            )


@receiver(post_save, sender=User)
def audit_user_save(sender, instance, created, **kwargs):
    if getattr(instance, "_skip_audit_log", False):
        return
    action = "USER_CREATED" if created else "USER_UPDATED"
    AuditService.record(
        action=action,
        actor=get_audit_actor(),
        request=get_audit_request(),
        entity_type="User",
        entity_id=instance.pk,
        old_values=None if created else getattr(instance, "_audit_old_values", None),
        new_values=_snapshot(
            instance, ("university_id", "email", "status", "is_active")
        ),
    )


@receiver(post_delete, sender=User)
def audit_user_delete(sender, instance, **kwargs):
    AuditService.record(
        action="USER_DELETED",
        actor=get_audit_actor(),
        request=get_audit_request(),
        entity_type="User",
        entity_id=instance.pk,
        old_values=_snapshot(
            instance, ("university_id", "email", "status", "is_active")
        ),
    )


@receiver(pre_save, sender=StudentProfile)
def capture_student_profile_before_save(sender, instance, **kwargs):
    instance._audit_old_values = None
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).first()
        if old:
            instance._audit_old_values = _snapshot(
                old, ("matricule_number", "current_level", "status")
            )


@receiver(post_save, sender=StudentProfile)
def audit_student_profile_save(sender, instance, created, **kwargs):
    if getattr(instance, "_skip_audit_log", False):
        return
    action = "STUDENT_PROFILE_CREATED" if created else "STUDENT_PROFILE_UPDATED"
    AuditService.record(
        action=action,
        actor=get_audit_actor(),
        request=get_audit_request(),
        entity_type="StudentProfile",
        entity_id=instance.pk,
        old_values=None if created else getattr(instance, "_audit_old_values", None),
        new_values=_snapshot(
            instance, ("matricule_number", "current_level", "status")
        ),
        metadata={"user_id": str(instance.user_id)},
    )


@receiver(post_save, sender=UserRole)
def audit_user_role_assigned(sender, instance, created, **kwargs):
    if not created:
        return
    AuditService.record(
        action="USER_ROLE_ASSIGNED",
        actor=instance.assigned_by or get_audit_actor(),
        request=get_audit_request(),
        entity_type="UserRole",
        entity_id=instance.pk,
        new_values={
            "user_id": str(instance.user_id),
            "role": instance.role.code,
            "scope_type": instance.scope_type,
        },
    )


@receiver(post_delete, sender=UserRole)
def audit_user_role_revoked(sender, instance, **kwargs):
    AuditService.record(
        action="USER_ROLE_REVOKED",
        actor=get_audit_actor(),
        request=get_audit_request(),
        entity_type="UserRole",
        entity_id=instance.pk,
        old_values={"user_id": str(instance.user_id), "role": instance.role.code},
    )


@receiver(pre_save, sender=AcademicYear)
def capture_academic_year_before_save(sender, instance, **kwargs):
    instance._audit_old_values = None
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).first()
        if old:
            instance._audit_old_values = _snapshot(
                old, ("name", "status", "is_current")
            )


@receiver(pre_save, sender=Semester)
def capture_semester_before_save(sender, instance, **kwargs):
    instance._audit_old_values = None
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).first()
        if old:
            instance._audit_old_values = _snapshot(
                old, ("name", "status", "is_current", "academic_year_id")
            )


@receiver(post_save, sender=AcademicYear)
def audit_academic_year_save(sender, instance, created, **kwargs):
    if getattr(instance, "_skip_audit_log", False):
        return
    action = "ACADEMIC_YEAR_CREATED" if created else "ACADEMIC_YEAR_UPDATED"
    AuditService.record(
        action=action,
        actor=get_audit_actor(),
        request=get_audit_request(),
        entity_type="AcademicYear",
        entity_id=instance.pk,
        old_values=None if created else getattr(instance, "_audit_old_values", None),
        new_values=_snapshot(instance, ("name", "status", "is_current")),
    )


@receiver(post_delete, sender=AcademicYear)
def audit_academic_year_delete(sender, instance, **kwargs):
    AuditService.record(
        action="ACADEMIC_YEAR_DELETED",
        actor=get_audit_actor(),
        request=get_audit_request(),
        entity_type="AcademicYear",
        entity_id=instance.pk,
        old_values=_snapshot(instance, ("name", "status", "is_current")),
    )


@receiver(post_save, sender=Semester)
def audit_semester_save(sender, instance, created, **kwargs):
    if getattr(instance, "_skip_audit_log", False):
        return
    action = "SEMESTER_CREATED" if created else "SEMESTER_UPDATED"
    AuditService.record(
        action=action,
        actor=get_audit_actor(),
        request=get_audit_request(),
        entity_type="Semester",
        entity_id=instance.pk,
        old_values=None if created else getattr(instance, "_audit_old_values", None),
        new_values=_snapshot(
            instance, ("name", "status", "is_current", "academic_year_id")
        ),
    )


@receiver(post_delete, sender=Semester)
def audit_semester_delete(sender, instance, **kwargs):
    AuditService.record(
        action="SEMESTER_DELETED",
        actor=get_audit_actor(),
        request=get_audit_request(),
        entity_type="Semester",
        entity_id=instance.pk,
        old_values=_snapshot(
            instance, ("name", "status", "is_current", "academic_year_id")
        ),
    )


# ──────────────────────────────────────────────────────────────────────
# Generic CRUD coverage — one receiver triplet per audited model.
#
# Actions are named `<PREFIX>_CREATED | _UPDATED | _DELETED`; entity_type
# is the model class name. `_skip_audit_log` on the instance suppresses
# the entry (used by views that record a more specific action instead).
# ──────────────────────────────────────────────────────────────────────


def _register_crud_audit(sender, *, prefix: str, fields: tuple[str, ...]):
    entity_type = sender.__name__

    # weak=False is required: these receivers are closures with no other
    # strong reference, so the default weak connect would be GC'd.
    @receiver(pre_save, sender=sender, weak=False)
    def _capture_old(sender, instance, **kwargs):
        instance._audit_old_values = None
        if instance.pk:
            old = sender.objects.filter(pk=instance.pk).first()
            if old:
                instance._audit_old_values = _snapshot(old, fields)

    @receiver(post_save, sender=sender, weak=False)
    def _log_save(sender, instance, created, **kwargs):
        if getattr(instance, "_skip_audit_log", False):
            return
        action = f"{prefix}_{'CREATED' if created else 'UPDATED'}"
        AuditService.record(
            action=action,
            actor=get_audit_actor(),
            request=get_audit_request(),
            entity_type=entity_type,
            entity_id=instance.pk,
            old_values=(
                None if created else getattr(instance, "_audit_old_values", None)
            ),
            new_values=_snapshot(instance, fields),
        )

    @receiver(post_delete, sender=sender, weak=False)
    def _log_delete(sender, instance, **kwargs):
        AuditService.record(
            action=f"{prefix}_DELETED",
            actor=get_audit_actor(),
            request=get_audit_request(),
            entity_type=entity_type,
            entity_id=instance.pk,
            old_values=_snapshot(instance, fields),
        )


# University structure
_register_crud_audit(Faculty, prefix="FACULTY", fields=("code", "name", "status"))
_register_crud_audit(
    Department,
    prefix="DEPARTMENT",
    fields=("faculty_id", "code", "name", "status"),
)
_register_crud_audit(
    Programme,
    prefix="PROGRAMME",
    fields=("department_id", "code", "name", "status"),
)

# Courses & enrolment
_register_crud_audit(
    Course, prefix="COURSE", fields=("code", "title", "status")
)
_register_crud_audit(
    CourseOffering,
    prefix="COURSE_OFFERING",
    fields=(
        "course_id",
        "semester_id",
        "programme_id",
        "section",
        "capacity",
        "status",
    ),
)
_register_crud_audit(
    CourseInstructor,
    prefix="COURSE_INSTRUCTOR",
    fields=(
        "course_offering_id",
        "user_id",
        "teaching_role",
        "can_grade",
        "can_manage_content",
    ),
)
_register_crud_audit(
    CourseEnrollment,
    prefix="ENROLLMENT",
    fields=("course_offering_id", "student_id", "status", "final_status"),
)

# Grading
_register_crud_audit(
    Grade,
    prefix="GRADE",
    fields=(
        "grade_item_id",
        "student_id",
        "score",
        "percentage",
        "letter_grade",
        "status",
    ),
)
_register_crud_audit(
    GradeAppeal,
    prefix="GRADE_APPEAL",
    fields=(
        "grade_id",
        "student_id",
        "status",
        "original_score",
        "resolved_score",
    ),
)

# Teaching & assessment content
_register_crud_audit(
    Assignment,
    prefix="ASSIGNMENT",
    fields=("course_offering_id", "title", "max_score", "due_at", "status"),
)
_register_crud_audit(
    AssignmentSubmission,
    prefix="ASSIGNMENT_SUBMISSION",
    fields=("assignment_id", "student_id", "status", "score", "is_late"),
)
_register_crud_audit(
    Assessment,
    prefix="ASSESSMENT",
    fields=(
        "course_offering_id",
        "title",
        "assessment_type",
        "total_points",
        "status",
    ),
)
_register_crud_audit(
    Announcement,
    prefix="ANNOUNCEMENT",
    fields=("course_offering_id", "title", "status", "is_pinned"),
)
_register_crud_audit(
    ContentItem,
    prefix="CONTENT_ITEM",
    fields=("course_module_id", "title", "content_type", "is_published"),
)



