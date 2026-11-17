from django.urls import path

from .api.audit_views import AuditLogFacetsView, AuditLogListView

urlpatterns = [
    path("audit-logs/facets/", AuditLogFacetsView.as_view(), name="audit-logs-facets"),
    path("audit-logs/", AuditLogListView.as_view(), name="audit-logs"),
]
