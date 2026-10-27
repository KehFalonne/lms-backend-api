from django.urls import path

from .api.audit_views import AuditLogListView

urlpatterns = [
    path("audit-logs/", AuditLogListView.as_view(), name="audit-logs"),
]
