"""
Calendar events — CRUD.

Also enforces: lecturers can only create events for courses they teach
(or globally if admin).
"""

from django.shortcuts import get_object_or_404
from rest_framework import filters, status
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.calendar.models import CalendarEvent
from apps.calendar.serializers import CalendarEventSerializer
from apps.common.responses import error_response, success_response
from apps.courses.models import CourseInstructor, CourseOffering


def _can_manage_events(user) -> bool:
    if user.is_staff or user.is_superuser:
        return True
    if user.roles if hasattr(user, "roles") else []:
        pass
    codes = set(user.get_role_codes()) if hasattr(user, "get_role_codes") else set()
    return bool(codes & {"LECTURER", "TEACHING_ASSISTANT", "HOD", "DEAN"})


def _is_instructor_of(user, offering_id) -> bool:
    return CourseInstructor.objects.filter(
        course_offering_id=offering_id,
        user=user,
    ).exists()


class CalendarEventListCreateView(APIView):
    """GET/POST /api/v1/calendar-events/"""

    serializer_class = CalendarEventSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        qs = CalendarEvent.objects.select_related(
            "course_offering__course", "created_by"
        )

        # Date range
        from_str = request.query_params.get("from")
        to_str = request.query_params.get("to")
        if from_str:
            qs = qs.filter(end_at__gte=from_str)
        if to_str:
            qs = qs.filter(start_at__lte=to_str)

        # Course filter
        offering = request.query_params.get("courseOfferingId")
        if offering:
            qs = qs.filter(course_offering_id=offering)

        # Non-admin non-lecturer users see only events in their courses
        codes = set(request.user.get_role_codes())
        if not (request.user.is_staff or request.user.is_superuser):
            if not (codes & {"LECTURER", "TEACHING_ASSISTANT", "HOD", "DEAN"}):
                # Student: restrict to their enrolled offerings
                from apps.courses.models import CourseEnrollment, EnrollmentStatus

                offering_ids = CourseEnrollment.objects.filter(
                    student=request.user,
                    status=EnrollmentStatus.ACTIVE,
                ).values_list("course_offering_id", flat=True)
                qs = qs.filter(course_offering_id__in=offering_ids)

        return success_response(data=CalendarEventSerializer(qs, many=True).data)

    def post(self, request):
        if not _can_manage_events(request.user):
            return error_response(
                "Only lecturers and admins can create calendar events.",
                status_code=403,
            )

        serializer = CalendarEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        offering_id = serializer.validated_data.pop("course_offering_id", None)

        # Validate instructor permission on the offering
        if offering_id and not (
            request.user.is_staff
            or request.user.is_superuser
            or _is_instructor_of(request.user, offering_id)
        ):
            return error_response(
                "You don't have permission to create events for this course.",
                status_code=403,
            )

        offering = None
        if offering_id:
            try:
                offering = CourseOffering.objects.get(pk=offering_id)
            except CourseOffering.DoesNotExist:
                return error_response("Course offering not found.", status_code=400)

        event = CalendarEvent.objects.create(
            course_offering=offering,
            created_by=request.user,
            **serializer.validated_data,
        )
        return success_response(
            data=CalendarEventSerializer(event).data,
            message="Event created.",
            status=status.HTTP_201_CREATED,
        )


class CalendarEventDetailView(APIView):
    """PATCH/DELETE /api/v1/calendar-events/{id}/"""

    serializer_class = CalendarEventSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def _get(self, pk):
        return get_object_or_404(CalendarEvent, pk=pk)

    def _can_edit(self, user, event: CalendarEvent) -> bool:
        if user.is_staff or user.is_superuser:
            return True
        if event.created_by_id == user.id:
            return True
        return _can_manage_events(user) and (
            event.course_offering_id is None
            or _is_instructor_of(user, event.course_offering_id)
        )

    def patch(self, request, pk):
        event = self._get(pk)
        if not self._can_edit(request.user, event):
            return error_response("Not allowed.", status_code=403)

        serializer = CalendarEventSerializer(event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("course_offering_id", None)
        for k, v in serializer.validated_data.items():
            setattr(event, k, v)
        event.save()
        return success_response(data=CalendarEventSerializer(event).data)

    def delete(self, request, pk):
        event = self._get(pk)
        if not self._can_edit(request.user, event):
            return error_response("Not allowed.", status_code=403)
        event.delete()
        return success_response(message="Event deleted.")
