from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.responses import error_response, success_response
from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationSerializer
from apps.notifications.services.notification_service import NotificationService


class NotificationListView(APIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(recipient=request.user)
        unread_only = request.query_params.get("unread") == "true"
        if unread_only:
            qs = qs.filter(read_at__isnull=True)

        page = (
            self.paginate_queryset(qs) if hasattr(self, "paginate_queryset") else None
        )
        if page is not None:
            return self.get_paginated_response(
                NotificationSerializer(page, many=True).data
            )
        return success_response(data=NotificationSerializer(qs[:100], many=True).data)


class MarkReadView(APIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        n = Notification.objects.filter(pk=pk, recipient=request.user).first()
        if not n:
            return error_response("Not found.", status_code=404)
        NotificationService.mark_read(n)
        return success_response(data=NotificationSerializer(n).data)


class MarkAllReadView(APIView):
    serializer_class = None
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = NotificationService.mark_all_read(request.user)
        return success_response(data={"updated": count})
