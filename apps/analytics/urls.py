from django.urls import path

from .api.dashboard_views import (
    AdminDashboardView,
    AdminStatsView,
    LecturerDashboardView,
    StudentDashboardView,
)
from .api.report_views import ReportsOverviewView
from .api.event_views import RecordEventView
from .api.progress_views import ContentProgressView

urlpatterns = [
    path("learning-events/", RecordEventView.as_view(), name="learning-events"),
    path(
        "content/<uuid:content_id>/progress/",
        ContentProgressView.as_view(),
        name="content-progress",
    ),
    # Dashboards (role-based)
    path(
        "dashboards/student/", StudentDashboardView.as_view(), name="dashboard-student"
    ),
    path(
        "dashboards/lecturer/",
        LecturerDashboardView.as_view(),
        name="dashboard-lecturer",
    ),
    path("dashboards/admin/", AdminDashboardView.as_view(), name="dashboard-admin"),
    # Admin stats aliases (frontend expects both)
    path("admin/stats/", AdminStatsView.as_view(), name="admin-stats"),
    path("admin/dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path(
        "admin/reports/overview/",
        ReportsOverviewView.as_view(),
        name="reports-overview",
    ),
]
