from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.common.responses import success_response


class AuditLogListView(APIView):
    """GET /api/v1/audit-logs/  (admin only)"""

    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = AuditLog.objects.select_related("actor").all()

        action = request.query_params.get("action")
        entity_type = request.query_params.get(
            "entityType"
        ) or request.query_params.get("entity_type")
        actor_id = request.query_params.get("actorId") or request.query_params.get(
            "actor_id"
        )

        if action:
            qs = qs.filter(action__icontains=action)
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if actor_id:
            qs = qs.filter(actor_id=actor_id)

        # Simple offset pagination
        try:
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = min(200, max(1, int(request.query_params.get("pageSize", 50))))
        except ValueError:
            page, page_size = 1, 50

        total = qs.count()
        start = (page - 1) * page_size
        items = qs[start : start + page_size]

        return success_response(
            data=AuditLogSerializer(items, many=True).data,
            meta={
                "page": page,
                "pageSize": page_size,
                "total": total,
                "totalPages": (total + page_size - 1) // page_size,
            },
        )
