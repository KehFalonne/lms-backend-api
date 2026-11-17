from datetime import date
from uuid import UUID

from django.core.cache import cache
from django.db.models import Q
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.views import APIView

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.common.responses import success_response


class CanViewAuditLogs(BasePermission):
    message = "You do not have permission to view audit logs."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or user.has_permission_code("audit.view"))
        )


class AuditLogListView(APIView):
    """GET /api/v1/audit-logs/  (admin only)"""

    serializer_class = AuditLogSerializer
    permission_classes = [CanViewAuditLogs]

    def get(self, request):
        qs = AuditLog.objects.select_related("actor").all()

        action = request.query_params.get("action")
        entity_type = request.query_params.get(
            "entityType"
        ) or request.query_params.get("entity_type")
        actor_id = request.query_params.get("actorId") or request.query_params.get(
            "actor_id"
        )
        actor = request.query_params.get("actor")
        entity_id = request.query_params.get("entityId") or request.query_params.get(
            "entity_id"
        )
        created_from = request.query_params.get("createdFrom") or request.query_params.get(
            "created_from"
        )
        created_to = request.query_params.get("createdTo") or request.query_params.get(
            "created_to"
        )
        if created_from:
            try:
                date.fromisoformat(created_from)
            except ValueError:
                raise ValidationError({"createdFrom": "Use YYYY-MM-DD format."})
        if created_to:
            try:
                date.fromisoformat(created_to)
            except ValueError:
                raise ValidationError({"createdTo": "Use YYYY-MM-DD format."})

        if action:
            qs = qs.filter(action__icontains=action)
        if entity_type:
            qs = qs.filter(entity_type__iexact=entity_type)
        if actor_id:
            try:
                actor_id = UUID(actor_id)
            except ValueError:
                raise ValidationError({"actorId": "Must be a valid UUID."})
            qs = qs.filter(actor_id=actor_id)
        if actor:
            qs = qs.filter(
                Q(actor__university_id__icontains=actor)
                | Q(actor__email__icontains=actor)
                | Q(actor__first_name__icontains=actor)
                | Q(actor__last_name__icontains=actor)
            )
        if entity_id:
            try:
                entity_id = UUID(entity_id)
            except ValueError:
                raise ValidationError({"entityId": "Must be a valid UUID."})
            qs = qs.filter(entity_id=entity_id)
        if created_from:
            qs = qs.filter(created_at__date__gte=created_from)
        if created_to:
            qs = qs.filter(created_at__date__lte=created_to)

        # Simple offset pagination
        try:
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = min(200, max(1, int(request.query_params.get("pageSize", 50))))
        except (TypeError, ValueError):
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


class AuditLogFacetsView(APIView):
    """GET /api/v1/audit-logs/facets/ — distinct actions & entity types for filters."""

    permission_classes = [CanViewAuditLogs]

    def get(self, request):
        facets = cache.get("audit_log_facets")
        if facets is None:
            facets = {
                "actions": sorted(
                    AuditLog.objects.values_list("action", flat=True).distinct()
                ),
                "entityTypes": sorted(
                    AuditLog.objects.exclude(entity_type="")
                    .values_list("entity_type", flat=True)
                    .distinct()
                ),
            }
            cache.set("audit_log_facets", facets, timeout=300)
        return success_response(data=facets)
