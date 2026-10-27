from django.urls import path

from .api.assignment_views import (
    AssignmentCloseView,
    AssignmentDetailView,
    AssignmentPublishView,
    OfferingAssignmentListCreateView,
)
from .api.submission_views import (
    GradeSubmissionView,
    MySubmissionView,
    SubmissionDetailView,
    SubmissionListCreateView,
)
from .api.my_views import MyAssignmentsView

urlpatterns = [
    # Assignments (nested under offering)
    path(
        "course-offerings/<uuid:offering_id>/assignments/",
        OfferingAssignmentListCreateView.as_view(),
        name="offering-assignments",
    ),
    path(
        "assignments/<uuid:pk>/",
        AssignmentDetailView.as_view(),
        name="assignment-detail",
    ),
    # My assignments (student)
    path(
        "my/assignments/",
        MyAssignmentsView.as_view(),
        name="my-assignments",
    ),
    path(
        "assignments/<uuid:pk>/publish/",
        AssignmentPublishView.as_view(),
        name="assignment-publish",
    ),
    path(
        "assignments/<uuid:pk>/close/",
        AssignmentCloseView.as_view(),
        name="assignment-close",
    ),
    # Student endpoints
    path(
        "assignments/<uuid:pk>/submission/",
        MySubmissionView.as_view(),
        name="assignment-my-submission",
    ),
    # Submissions (list for staff + create for student)
    path(
        "assignments/<uuid:pk>/submissions/",
        SubmissionListCreateView.as_view(),
        name="assignment-submissions",
    ),
    path(
        "assignment-submissions/<uuid:pk>/",
        SubmissionDetailView.as_view(),
        name="submission-detail",
    ),
    path(
        "assignment-submissions/<uuid:pk>/grade/",
        GradeSubmissionView.as_view(),
        name="submission-grade",
    ),
]
