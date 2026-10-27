from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.analytics.services.progress_service import ProgressService
from apps.common.responses import error_response, success_response
from apps.content.models import ContentItem


class ContentProgressView(APIView):
    """PUT /api/v1/content/{content_id}/progress/"""

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def put(self, request, content_id):
        item = get_object_or_404(ContentItem, pk=content_id, deleted_at__isnull=True)

        status_value = request.data.get("status")
        progress_percent = request.data.get("progressPercent") or request.data.get(
            "progress_percent"
        )

        cp = ProgressService.mark_content_progress(
            student=request.user,
            content_item=item,
            status=status_value,
            progress_percent=progress_percent,
        )

        # Fire-and-forget: recompute overall course progress
        try:
            ProgressService.recompute(
                student=request.user,
                course_offering_id=item.course_module.course_offering_id,
            )
        except Exception:
            pass

        return success_response(
            data={
                "id": str(cp.id),
                "status": cp.status,
                "progressPercent": cp.progress_percent,
            },
            message="Progress updated.",
        )
