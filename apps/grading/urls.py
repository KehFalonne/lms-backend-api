from django.urls import path

from .api.category_views import (
    GradeCategoryDetailView,
    OfferingCategoryListCreateView,
    SetCategoryWeightsView,
)
from .api.grade_views import (
    GradeHistoryView,
    GradeItemGradesListView,
    MyCourseGradesView,
    MyGradesView,
    SetGradeView,
)
from .api.item_views import (
    GradeItemDetailView,
    OfferingGradeItemListCreateView,
    PublishGradeItemView,
    PublishOfferingGradesView,
)

urlpatterns = [
    # Categories
    path(
        "course-offerings/<uuid:offering_id>/grade-categories/",
        OfferingCategoryListCreateView.as_view(),
        name="offering-grade-categories",
    ),
    path(
        "course-offerings/<uuid:offering_id>/grade-categories/set-weights/",
        SetCategoryWeightsView.as_view(),
        name="offering-category-weights",
    ),
    path(
        "grade-categories/<uuid:pk>/",
        GradeCategoryDetailView.as_view(),
        name="grade-category-detail",
    ),
    # Items
    path(
        "course-offerings/<uuid:offering_id>/grade-items/",
        OfferingGradeItemListCreateView.as_view(),
        name="offering-grade-items",
    ),
    path(
        "grade-items/<uuid:pk>/",
        GradeItemDetailView.as_view(),
        name="grade-item-detail",
    ),
    path(
        "grade-items/<uuid:pk>/publish/",
        PublishGradeItemView.as_view(),
        name="grade-item-publish",
    ),
    path(
        "course-offerings/<uuid:offering_id>/grades/publish/",
        PublishOfferingGradesView.as_view(),
        name="offering-grades-publish",
    ),
    # Grades
    path(
        "grade-items/<uuid:pk>/grades/",
        GradeItemGradesListView.as_view(),
        name="item-grades",
    ),
    path(
        "grade-items/<uuid:pk>/grades/<uuid:student_id>/",
        SetGradeView.as_view(),
        name="set-grade",
    ),
    path("grades/<uuid:pk>/history/", GradeHistoryView.as_view(), name="grade-history"),
    # Student
    path("my/grades/", MyGradesView.as_view(), name="my-grades"),
    path(
        "my/course-offerings/<uuid:offering_id>/grades/",
        MyCourseGradesView.as_view(),
        name="my-course-grades",
    ),
]
