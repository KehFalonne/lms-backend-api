"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.http import JsonResponse
from django.contrib import admin
from django.urls import include, path
from apps.accounts.api.user_views import UserViewSet
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from apps.accounts.api.role_views import PermissionListView, RoleViewSet

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"roles", RoleViewSet, basename="role")


api_v1_patterns = [
    path("auth/", include("apps.accounts.urls")),
    path("permissions/", PermissionListView.as_view(), name="permissions-list"),
    path("", include("apps.university.urls")),
    path("", include("apps.academics.urls")),
    path("", include("apps.courses.urls")),
    path("", include("apps.content.urls")),
    path("", include("apps.files.urls")),
    path("", include("apps.announcements.urls")),
    path("", include("apps.discussions.urls")),
    path("", include("apps.notifications.urls")),
    path("", include("apps.assignments.urls")),
    path("", include("apps.assessments.urls")),
    path("", include("apps.grading.urls")),
    path("", include("apps.analytics.urls")),
    path("", include("apps.audit.urls")),
    path("", include("apps.calendar.urls")),
    path("", include(router.urls)),
]


urlpatterns = [
    path("admin/", admin.site.urls),
    # ── API v1 (per backend architecture doc, section 12) ──
    path("api/v1/", include((api_v1_patterns, "v1"), namespace="v1")),
    # ── OpenAPI (per backend architecture doc, section 40) ──
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]
