"""
Scope-aware DRF permission classes (backend doc §11).

Naming and behavior follows the doc's list:
    IsAuthenticated  HasRole  HasPermissionCode
    HasFacultyAccess  HasDepartmentAccess  HasCourseAccess
    IsCourseInstructor  CanGradeCourse  IsEnrolledStudent

Views can combine them freely:

    class CourseGradeView(APIView):
        permission_classes = [IsAuthenticatedAndActive, CanGradeCourse]

Object-level checks use `has_object_permission` where relevant — DRF calls
them only after `get_object()` runs in the view.
"""

from rest_framework.permissions import BasePermission

from apps.accounts.models import RoleScope

# ──────────────────────────────────────────────────────────────────────
# Basic
# ──────────────────────────────────────────────────────────────────────


class IsAuthenticatedAndActive(BasePermission):
    message = "Authentication required."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.is_active
        )


class HasRole(BasePermission):
    """
    Requires at least one of `view.required_roles`.

    Example:
        class X(APIView):
            required_roles = ["LECTURER", "HOD"]
            permission_classes = [HasRole]
    """

    message = "You do not have the required role."

    def has_permission(self, request, view):
        required = getattr(view, "required_roles", None)
        if not required:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_role(*required)


class HasPermissionCode(BasePermission):
    """
    Requires at least one of `view.required_permissions`.

    Example:
        class X(APIView):
            required_permissions = ["courses.create"]
            permission_classes = [HasPermissionCode]
    """

    message = "You do not have the required permission."

    def has_permission(self, request, view):
        required = getattr(view, "required_permissions", None)
        if not required:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.has_permission_code(*required)


# ──────────────────────────────────────────────────────────────────────
# Scope-based
# ──────────────────────────────────────────────────────────────────────


def _scoped_roles_qs(user):
    return user.user_roles.select_related("role")


class HasFacultyAccess(BasePermission):
    """
    Access requires either:
      • a GLOBAL role assignment, OR
      • a FACULTY-scoped assignment matching `view.get_faculty_id(obj)`
    """

    message = "You do not have access to this faculty."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        faculty_id = _extract_id(view, obj, "faculty_id")
        if faculty_id is None:
            return False
        return (
            _scoped_roles_qs(user)
            .filter(scope_type=RoleScope.FACULTY, faculty_id=faculty_id)
            .exists()
            or _scoped_roles_qs(user).filter(scope_type=RoleScope.GLOBAL).exists()
        )


class HasDepartmentAccess(BasePermission):
    message = "You do not have access to this department."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        department_id = _extract_id(view, obj, "department_id")
        if department_id is None:
            return False
        return (
            _scoped_roles_qs(user)
            .filter(scope_type=RoleScope.DEPARTMENT, department_id=department_id)
            .exists()
            or _scoped_roles_qs(user).filter(scope_type=RoleScope.GLOBAL).exists()
        )


class HasCourseAccess(BasePermission):
    """
    User can interact with this course offering (broad access — view,
    see enrolled students, etc.). Stricter actions use CanGradeCourse.
    """

    message = "You do not have access to this course."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True

        course_offering_id = _extract_id(view, obj, "course_offering_id")
        if course_offering_id is None:
            return False

        # 1) explicit COURSE-scope assignment
        if (
            _scoped_roles_qs(user)
            .filter(scope_type=RoleScope.COURSE, course_offering_id=course_offering_id)
            .exists()
        ):
            return True

        # 2) global role
        if _scoped_roles_qs(user).filter(scope_type=RoleScope.GLOBAL).exists():
            return True

        # 3) student enrolled in this offering
        return _is_enrolled(user, course_offering_id)


class IsCourseInstructor(BasePermission):
    """
    Only the primary/co-instructor of the course offering may proceed.
    Reads `course_instructors` table (added in Sprint 5). In Sprint 3 we
    fall back to the COURSE-scope UserRole assignment.
    """

    message = "You are not an instructor for this course."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        course_offering_id = _extract_id(view, obj, "course_offering_id")
        if course_offering_id is None:
            return False
        return (
            _scoped_roles_qs(user)
            .filter(scope_type=RoleScope.COURSE, course_offering_id=course_offering_id)
            .exists()
        )


class CanGradeCourse(BasePermission):
    """
    Instructor who can grade. Sprint 5 will check `course_instructors.can_grade`;
    in Sprint 3 we require COURSE scope + `grades.manage` permission.
    """

    message = "You cannot grade this course."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        course_offering_id = _extract_id(view, obj, "course_offering_id")
        if course_offering_id is None:
            return False
        has_course_scope = (
            _scoped_roles_qs(user)
            .filter(scope_type=RoleScope.COURSE, course_offering_id=course_offering_id)
            .exists()
        )
        return has_course_scope and user.has_permission_code("grades.manage")


class IsEnrolledStudent(BasePermission):
    """Object-level: student must be actively enrolled in the offering."""

    message = "You are not enrolled in this course."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        course_offering_id = _extract_id(view, obj, "course_offering_id")
        if course_offering_id is None:
            return False
        return _is_enrolled(user, course_offering_id)


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _extract_id(view, obj, attr: str):
    """
    Resolve the scope anchor from the view or the object.

    Views can override `get_course_offering_id(obj)` etc. to customize.
    """
    getter_name = f"get_{attr}"
    if hasattr(view, getter_name):
        return getattr(view, getter_name)(obj)
    return getattr(obj, attr, None) or getattr(obj, "id", None)


def _is_enrolled(user, course_offering_id) -> bool:
    """
    Sprint 5 replaces this with a direct lookup on `course_enrollments`.
    In Sprint 3 the enrollment model doesn't exist yet, so we defensively
    return False.
    """
    try:
        from apps.courses.models import CourseEnrollment  # noqa: F401
    except Exception:
        return False
    return CourseEnrollment.objects.filter(
        student=user,
        course_offering_id=course_offering_id,
        status="ACTIVE",
    ).exists()
