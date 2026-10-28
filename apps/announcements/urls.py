from django.urls import path

from .api.announcement_views import (
    AnnouncementArchiveView,
    AnnouncementDetailView,
    AnnouncementPublishView,
    OfferingAnnouncementListCreateView,
    AnnouncementReadersView,
    MarkAnnouncementReadView,
)

urlpatterns = [
    path(
        "course-offerings/<uuid:offering_id>/announcements/",
        OfferingAnnouncementListCreateView.as_view(),
        name="offering-announcements",
    ),
    path(
        "announcements/<uuid:pk>/",
        AnnouncementDetailView.as_view(),
        name="announcement-detail",
    ),
    path(
        "announcements/<uuid:pk>/publish/",
        AnnouncementPublishView.as_view(),
        name="announcement-publish",
    ),
    path(
        "announcements/<uuid:pk>/archive/",
        AnnouncementArchiveView.as_view(),
        name="announcement-archive",
    ),
    path(
        "announcements/<uuid:pk>/mark-read/",
        MarkAnnouncementReadView.as_view(),
        name="announcement-mark-read",
    ),
    path(
        "announcements/<uuid:pk>/readers/",
        AnnouncementReadersView.as_view(),
        name="announcement-readers",
    ),
]
