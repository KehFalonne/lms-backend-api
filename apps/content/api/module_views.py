from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import error_response, success_response
from apps.content.models import CourseModule
from apps.content.serializers import CourseModuleSerializer
from apps.courses.models import CourseOffering
from apps.courses.permissions import CanManageCourseContent


def _can_manage_content(request, offering):
    return CanManageCourseContent().has_object_permission(request, None, offering)


class OfferingModuleListCreateView(APIView):
    """
    GET  /api/v1/course-offerings/{offering_id}/modules/
    POST /api/v1/course-offerings/{offering_id}/modules/
    """

    serializer_class = CourseModuleSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticatedAndActive(), CanManageCourseContent()]
        return super().get_permissions()

    def _get_offering(self, offering_id):
        return get_object_or_404(CourseOffering, pk=offering_id)

    def get(self, request, offering_id):
        offering = self._get_offering(offering_id)
        qs = offering.modules.all().order_by("position")
        if not _can_manage_content(request, offering):
            now = timezone.now()
            qs = qs.filter(is_published=True).filter(
                (Q(availability_start__isnull=True) | Q(availability_start__lte=now))
                & (Q(availability_end__isnull=True) | Q(availability_end__gte=now))
            )
        return success_response(data=CourseModuleSerializer(qs, many=True).data)

    def post(self, request, offering_id):
        offering = self._get_offering(offering_id)
        self.check_object_permissions(request, offering)

        serializer = CourseModuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        next_position = (
            offering.modules.order_by("-position")
            .values_list("position", flat=True)
            .first()
            or 0
        ) + 1

        module = CourseModule.objects.create(
            course_offering=offering,
            created_by=request.user,
            position=serializer.validated_data.pop("position", next_position),
            **serializer.validated_data,
        )
        return success_response(
            data=CourseModuleSerializer(module).data,
            message="Module created successfully.",
            status=status.HTTP_201_CREATED,
        )


class ModuleDetailView(APIView):
    """
    GET    /api/v1/modules/{id}/
    PATCH  /api/v1/modules/{id}/
    DELETE /api/v1/modules/{id}/
    """

    serializer_class = CourseModuleSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT", "DELETE"):
            return [IsAuthenticatedAndActive(), CanManageCourseContent()]
        return super().get_permissions()

    def _get(self, pk):
        return get_object_or_404(CourseModule, pk=pk)

    def get(self, request, pk):
        module = self._get(pk)
        return success_response(data=CourseModuleSerializer(module).data)

    def patch(self, request, pk):
        module = self._get(pk)
        self.check_object_permissions(request, module.course_offering)
        serializer = CourseModuleSerializer(module, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(
            data=CourseModuleSerializer(module).data,
            message="Module updated successfully.",
        )

    def delete(self, request, pk):
        module = self._get(pk)
        self.check_object_permissions(request, module.course_offering)
        module.delete()
        return success_response(message="Module deleted successfully.")


class MyContentTreeView(APIView):
    """
    GET /api/v1/my/course-offerings/{offering_id}/content-tree/

    Returns the full published content tree for the current student,
    with per-item progress folded in. Single call — no N+1.
    """

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, offering_id):
        from apps.courses.models import CourseEnrollment, EnrollmentStatus
        from apps.analytics.models import ContentProgress

        if not CourseEnrollment.objects.filter(
            student=request.user,
            course_offering_id=offering_id,
            status=EnrollmentStatus.ACTIVE,
        ).exists():
            from apps.common.responses import error_response

            return error_response(
                "You are not enrolled in this course.", status_code=403
            )

        modules = CourseModule.objects.filter(
            course_offering_id=offering_id, is_published=True
        ).order_by("position")
        now = timezone.now()
        modules = modules.filter(
            (Q(availability_start__isnull=True) | Q(availability_start__lte=now))
            & (Q(availability_end__isnull=True) | Q(availability_end__gte=now))
        )

        content_ids = []
        module_data = []
        for module in modules:
            items = list(
                module.content_items.filter(
                    is_published=True,
                    deleted_at__isnull=True,
                )
                .filter(
                    (Q(availability_start__isnull=True) | Q(availability_start__lte=now))
                    & (Q(availability_end__isnull=True) | Q(availability_end__gte=now))
                )
                .order_by("position")
            )
            content_ids.extend(item.id for item in items)
            module_data.append(
                {
                    "id": str(module.id),
                    "title": module.title,
                    "description": module.description,
                    "position": module.position,
                    "contentItems": [
                        {
                            "id": str(item.id),
                            "title": item.title,
                            "contentType": item.content_type,
                            "description": item.description,
                            "body": item.body,
                            "transcript": item.transcript,
                            "externalUrl": item.external_url,
                            "position": item.position,
                            "isRequired": item.is_required,
                        }
                        for item in items
                    ],
                }
            )

        # Batch-fetch progress for all content items at once
        progress_by_item = {
            cp.content_item_id: cp.status
            for cp in ContentProgress.objects.filter(
                student=request.user,
                content_item_id__in=content_ids,
            )
        }
        for module in module_data:
            for item in module["contentItems"]:
                item["progressStatus"] = progress_by_item.get(
                    __import__("uuid").UUID(item["id"]), "NOT_STARTED"
                )

        return success_response(data=module_data)
