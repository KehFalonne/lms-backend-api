from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import success_response
from apps.content.models import ContentItem, CourseModule
from apps.content.serializers import ContentItemSerializer
from apps.courses.permissions import CanManageCourseContent


class ModuleContentListCreateView(APIView):
    """
    GET  /api/v1/modules/{module_id}/content/
    POST /api/v1/modules/{module_id}/content/
    """

    serializer_class = ContentItemSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticatedAndActive(), CanManageCourseContent()]
        return super().get_permissions()

    def _module(self, module_id):
        return get_object_or_404(CourseModule, pk=module_id)

    def get(self, request, module_id):
        module = self._module(module_id)
        qs = module.content_items.filter(deleted_at__isnull=True).order_by("position")
        if not request.user.is_staff:
            qs = qs.filter(is_published=True)
        return success_response(data=ContentItemSerializer(qs, many=True).data)

    def post(self, request, module_id):
        module = self._module(module_id)
        self.check_object_permissions(request, module.course_offering)

        serializer = ContentItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        next_position = (
            module.content_items.filter(deleted_at__isnull=True)
            .order_by("-position")
            .values_list("position", flat=True)
            .first()
            or 0
        ) + 1

        item = ContentItem.objects.create(
            course_module=module,
            created_by=request.user,
            position=serializer.validated_data.pop("position", next_position),
            **serializer.validated_data,
        )
        return success_response(
            data=ContentItemSerializer(item).data,
            message="Content created successfully.",
            status=status.HTTP_201_CREATED,
        )


class ContentItemDetailView(APIView):
    """
    GET    /api/v1/content/{id}/
    PATCH  /api/v1/content/{id}/
    DELETE /api/v1/content/{id}/
    """

    serializer_class = ContentItemSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT", "DELETE"):
            return [IsAuthenticatedAndActive(), CanManageCourseContent()]
        return super().get_permissions()

    def _get(self, pk):
        return get_object_or_404(ContentItem, pk=pk, deleted_at__isnull=True)

    def get(self, request, pk):
        item = self._get(pk)
        # Record learning event (fire-and-forget)
        try:
            from apps.analytics.services.event_service import EventService

            EventService.record(
                student=request.user,
                event_type="CONTENT_VIEWED",
                course_offering=item.course_module.course_offering,
                entity_type="content_item",
                entity_id=item.id,
            )
        except Exception:
            pass
        return success_response(data=ContentItemSerializer(item).data)

    def patch(self, request, pk):
        item = self._get(pk)
        self.check_object_permissions(request, item.course_module.course_offering)
        serializer = ContentItemSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(
            data=ContentItemSerializer(item).data,
            message="Content updated successfully.",
        )

    def delete(self, request, pk):
        item = self._get(pk)
        self.check_object_permissions(request, item.course_module.course_offering)
        item.delete()
        return success_response(message="Content deleted successfully.")


class ContentPublishView(APIView):
    serializer_class = ContentItemSerializer
    permission_classes = [IsAuthenticatedAndActive, CanManageCourseContent]

    def post(self, request, pk):
        item = get_object_or_404(ContentItem, pk=pk, deleted_at__isnull=True)
        self.check_object_permissions(request, item.course_module.course_offering)
        item.is_published = True
        item.save(update_fields=["is_published", "updated_at"])
        return success_response(
            data=ContentItemSerializer(item).data,
            message="Content published.",
        )


class ContentUnpublishView(APIView):
    serializer_class = ContentItemSerializer
    permission_classes = [IsAuthenticatedAndActive, CanManageCourseContent]

    def post(self, request, pk):
        item = get_object_or_404(ContentItem, pk=pk, deleted_at__isnull=True)
        self.check_object_permissions(request, item.course_module.course_offering)
        item.is_published = False
        item.save(update_fields=["is_published", "updated_at"])
        return success_response(
            data=ContentItemSerializer(item).data,
            message="Content unpublished.",
        )
