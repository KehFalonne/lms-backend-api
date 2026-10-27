"""
Course-scope permission classes (per backend doc §11 and §19).

Checks `CourseInstructor` assignments first (real teaching roles), falling
back to GLOBAL UserRole scope for admins.
"""

from rest_framework.permissions import BasePermission

from .models import CourseInstructor


def _offering_id_from(obj):
    """Resolve the CourseOffering PK from an offering, module, or content obj."""
    if hasattr(obj, "course_offering_id"):
        return obj.course_offering_id
    if hasattr(obj, "course_module") and hasattr(
        obj.course_module, "course_offering_id"
    ):
        return obj.course_module.course_offering_id
    return getattr(obj, "id", None)


class CanManageCourseContent(BasePermission):
    """
    Object-level: user must be an instructor for this offering with
    `can_manage_content=True`, OR a superuser, OR have GLOBAL scope.
    """

    message = "You are not an instructor for this course."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True

        offering_id = _offering_id_from(obj)
        if not offering_id:
            return False

        # Global role → allowed
        if user.user_roles.filter(scope_type="GLOBAL").exists():
            return True

        # Instructor with content permission
        return CourseInstructor.objects.filter(
            course_offering_id=offering_id,
            user=user,
            can_manage_content=True,
        ).exists()


class IsCourseInstructor(BasePermission):
    """Object-level: user is any instructor (any role) for the offering."""

    message = "You are not an instructor for this course."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        offering_id = _offering_id_from(obj)
        if not offering_id:
            return False
        return CourseInstructor.objects.filter(
            course_offering_id=offering_id, user=user
        ).exists()


class CanGradeCourse(BasePermission):
    """Object-level: instructor with `can_grade=True`."""

    message = "You cannot grade this course."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        offering_id = _offering_id_from(obj)
        if not offering_id:
            return False
        return CourseInstructor.objects.filter(
            course_offering_id=offering_id, user=user, can_grade=True
        ).exists()


class IsEnrolledStudent(BasePermission):
    """Object-level: student is actively enrolled in the offering."""

    message = "You are not enrolled in this course."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        offering_id = _offering_id_from(obj)
        if not offering_id:
            return False

        from .models import CourseEnrollment, EnrollmentStatus

        return CourseEnrollment.objects.filter(
            course_offering_id=offering_id,
            student=user,
            status=EnrollmentStatus.ACTIVE,
        ).exists()
