from django.urls import path
from rest_framework.routers import DefaultRouter

from .api.lecturer_views import (
    LecturerDashboardStatsView,
    MyTeachingCoursesView,
)
from .api.gradebook_views import GradebookView
from .api.course_views import CourseViewSet
from .api.enrollment_views import (
    EnrollmentDeleteView,
    MyCourseOfferingView,
    MyCoursesView,
    OfferingBulkEnrollView,
    OfferingEnrollmentListCreateView,
)
from .api.instructor_views import (
    InstructorDetailView,
    OfferingInstructorListCreateView,
)
from .api.offering_views import CourseOfferingViewSet

router = DefaultRouter()
router.register(r"courses", CourseViewSet, basename="course")
router.register(r"course-offerings", CourseOfferingViewSet, basename="course-offering")

urlpatterns = [
    # Instructors (nested)
    path(
        "course-offerings/<uuid:offering_id>/instructors/",
        OfferingInstructorListCreateView.as_view(),
        name="offering-instructors",
    ),
    path(
        "course-offerings/<uuid:offering_id>/instructors/<uuid:instructor_id>/",
        InstructorDetailView.as_view(),
        name="instructor-detail",
    ),
    # Enrollments (nested)
    path(
        "course-offerings/<uuid:offering_id>/enrollments/",
        OfferingEnrollmentListCreateView.as_view(),
        name="offering-enrollments",
    ),
    path(
        "course-offerings/<uuid:offering_id>/enrollments/bulk/",
        OfferingBulkEnrollView.as_view(),
        name="offering-enrollments-bulk",
    ),
    path(
        "course-offerings/<uuid:offering_id>/enrollments/<uuid:student_id>/",
        EnrollmentDeleteView.as_view(),
        name="enrollment-delete",
    ),
    # My courses
    path("my/courses/", MyCoursesView.as_view(), name="my-courses"),
    path(
        "my/course-offerings/<uuid:offering_id>/",
        MyCourseOfferingView.as_view(),
        name="my-course-offering",
    ),
    path(
        "my/teaching-courses/",
        MyTeachingCoursesView.as_view(),
        name="my-teaching-courses",
    ),
    path(
        "lecturer/dashboard/stats/",
        LecturerDashboardStatsView.as_view(),
        name="lecturer-dashboard-stats",
    ),
    path(
        "course-offerings/<uuid:offering_id>/gradebook/",
        GradebookView.as_view(),
        name="gradebook",
    ),
    # Router URLs (courses + course-offerings CRUD)
    *router.urls,
]
