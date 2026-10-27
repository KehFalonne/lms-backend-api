from rest_framework.routers import DefaultRouter

from .api.department_views import DepartmentViewSet
from .api.faculty_views import FacultyViewSet
from .api.programme_views import ProgrammeViewSet

router = DefaultRouter()
router.register(r"faculties", FacultyViewSet, basename="faculty")
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"programmes", ProgrammeViewSet, basename="programme")

urlpatterns = router.urls
