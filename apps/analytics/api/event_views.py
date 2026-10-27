from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.analytics.services.event_service import EventService
from apps.common.responses import error_response, success_response


class RecordEventView(APIView):
    """POST /api/v1/learning-events/"""

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request):
        event_type = request.data.get("eventType") or request.data.get("event_type")
        course_offering_id = request.data.get("courseOfferingId") or request.data.get(
            "course_offering_id"
        )
        entity_type = (
            request.data.get("entityType") or request.data.get("entity_type") or ""
        )
        entity_id = request.data.get("entityId") or request.data.get("entity_id")
        metadata = request.data.get("metadata") or {}

        if not event_type:
            return error_response("eventType is required.", status_code=400)

        event = EventService.record(
            student=request.user,
            event_type=event_type,
            course_offering_id=course_offering_id,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
        )
        if not event:
            return error_response("Could not record event.", status_code=500)

        return success_response(
            data={"id": str(event.id)},
            message="Event recorded.",
            status=status.HTTP_201_CREATED,
        )
