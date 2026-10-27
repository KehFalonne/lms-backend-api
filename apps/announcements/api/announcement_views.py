from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.announcements.models import Announcement, AnnouncementStatus
from apps.announcements.serializers import AnnouncementSerializer
from apps.common.responses import error_response, success_response
from apps.courses.models import CourseOffering
from apps.courses.permissions import CanManageCourseContent


class OfferingAnnouncementListCreateView(APIView):
    """GET/POST /api/v1/course-offerings/{offering_id}/announcements/"""

    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticatedAndActive(), CanManageCourseContent()]
        return super().get_permissions()

    def get(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        qs = offering.announcements.all()
        if not request.user.is_staff:
            qs = qs.filter(status=AnnouncementStatus.PUBLISHED)
        return success_response(data=AnnouncementSerializer(qs, many=True).data)

    def post(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        self.check_object_permissions(request, offering)
        serializer = AnnouncementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("course_offering_id", None)
        announcement = Announcement.objects.create(
            course_offering=offering,
            created_by=request.user,
            **serializer.validated_data,
        )
        return success_response(
            data=AnnouncementSerializer(announcement).data,
            message="Announcement created.",
            status=status.HTTP_201_CREATED,
        )


class AnnouncementDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/announcements/{id}/"""

    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method in ("PATCH", "PUT", "DELETE"):
            return [IsAuthenticatedAndActive(), CanManageCourseContent()]
        return super().get_permissions()

    def _get(self, pk):
        return get_object_or_404(Announcement, pk=pk)

    def get(self, request, pk):
        return success_response(data=AnnouncementSerializer(self._get(pk)).data)

    def patch(self, request, pk):
        a = self._get(pk)
        self.check_object_permissions(request, a.course_offering)
        serializer = AnnouncementSerializer(a, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("course_offering_id", None)
        serializer.save()
        return success_response(
            data=AnnouncementSerializer(a).data,
            message="Announcement updated.",
        )

    def delete(self, request, pk):
        a = self._get(pk)
        self.check_object_permissions(request, a.course_offering)
        a.delete()
        return success_response(message="Announcement deleted.")


class AnnouncementPublishView(APIView):
    """POST /api/v1/announcements/{id}/publish/"""

    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticatedAndActive, CanManageCourseContent]

    def post(self, request, pk):
        a = get_object_or_404(Announcement, pk=pk)
        self.check_object_permissions(request, a.course_offering)
        a.publish()

        # ── Create a notification for every enrolled student ──
        from apps.courses.models import CourseEnrollment, EnrollmentStatus
        from apps.notifications.services.notification_service import (
            NotificationService,
        )

        student_ids = CourseEnrollment.objects.filter(
            course_offering=a.course_offering,
            status=EnrollmentStatus.ACTIVE,
        ).values_list("student_id", flat=True)

        if student_ids:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            recipients = list(User.objects.filter(id__in=student_ids, is_active=True))

            NotificationService.push_bulk(
                recipients=recipients,
                type="ANNOUNCEMENT",
                title=f"New announcement: {a.title}",
                message=a.body[:200],
                entity_type="announcement",
                entity_id=a.id,
                data={
                    "announcementId": str(a.id),
                    "courseOfferingId": str(a.course_offering_id),
                },
            )

        return success_response(
            data=AnnouncementSerializer(a).data,
            message="Announcement published.",
        )


class AnnouncementArchiveView(APIView):
    """POST /api/v1/announcements/{id}/archive/"""

    serializer_class = AnnouncementSerializer
    permission_classes = [IsAuthenticatedAndActive, CanManageCourseContent]

    def post(self, request, pk):
        a = get_object_or_404(Announcement, pk=pk)
        self.check_object_permissions(request, a.course_offering)
        a.status = AnnouncementStatus.ARCHIVED
        a.save(update_fields=["status", "updated_at"])
        return success_response(
            data=AnnouncementSerializer(a).data,
            message="Announcement archived.",
        )
