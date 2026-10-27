from django.urls import path

from .api.event_views import (
    CalendarEventDetailView,
    CalendarEventListCreateView,
)
from .api.unified_views import UnifiedCalendarView

urlpatterns = [
    path("calendar/", UnifiedCalendarView.as_view(), name="unified-calendar"),
    path(
        "calendar-events/",
        CalendarEventListCreateView.as_view(),
        name="calendar-events",
    ),
    path(
        "calendar-events/<uuid:pk>/",
        CalendarEventDetailView.as_view(),
        name="calendar-event-detail",
    ),
]
