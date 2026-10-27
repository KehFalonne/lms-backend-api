from rest_framework.routers import DefaultRouter

from .api.semester_views import SemesterViewSet
from .api.year_views import AcademicYearViewSet

router = DefaultRouter()
router.register(r"academic-years", AcademicYearViewSet, basename="academic-year")
router.register(r"semesters", SemesterViewSet, basename="semester")

urlpatterns = router.urls
