from django.urls import path

from .api.notification_views import (
    MarkAllReadView,
    MarkReadView,
    NotificationListView,
)

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="notifications-list"),
    path(
        "notifications/<uuid:pk>/read/",
        MarkReadView.as_view(),
        name="notification-read",
    ),
    path(
        "notifications/read-all/",
        MarkAllReadView.as_view(),
        name="notifications-read-all",
    ),
]
