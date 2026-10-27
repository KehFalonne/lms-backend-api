"""
Unified calendar — merges multiple sources into one list.

Sources:
1. CalendarEvent rows (manually created)
2. Assignment.due_at from assignments the user can see
3. Assessment.available_until from assessments the user can see
"""

from datetime import datetime, time, timezone as dt_timezone

from django.utils.dateparse import parse_datetime, parse_date
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.assignments.models import Assignment, AssignmentStatus
from apps.assessments.models import Assessment, AssessmentStatus
from apps.calendar.models import CalendarEvent, EventType
from apps.common.responses import error_response, success_response
from apps.courses.models import CourseEnrollment, CourseInstructor, EnrollmentStatus


class UnifiedCalendarView(APIView):
    """
    GET /api/v1/calendar/?from=<iso>&to=<iso>

    Returns a flat, merged, sorted list of all events visible to the user.
    """

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        from_str = request.query_params.get("from")
        to_str = request.query_params.get("to")

        if not from_str or not to_str:
            return error_response(
                "Query params `from` and `to` are required (ISO date/datetime).",
                status_code=400,
            )

        date_from = parse_datetime(from_str) or _as_start_of_day(from_str)
        date_to = parse_datetime(to_str) or _as_end_of_day(to_str)

        if not date_from or not date_to:
            return error_response("Invalid date format.", status_code=400)

        codes = set(request.user.get_role_codes())
        is_staff = request.user.is_staff or request.user.is_superuser
        is_lecturer = bool(codes & {"LECTURER", "TEACHING_ASSISTANT", "HOD", "DEAN"})

        # Which offerings can this user see?
        if is_staff:
            offering_ids = None  # all
        elif is_lecturer:
            offering_ids = list(
                CourseInstructor.objects.filter(user=request.user).values_list(
                    "course_offering_id", flat=True
                )
            )
        else:
            offering_ids = list(
                CourseEnrollment.objects.filter(
                    student=request.user,
                    status=EnrollmentStatus.ACTIVE,
                ).values_list("course_offering_id", flat=True)
            )

        events = []

        # ── 1. Manual CalendarEvents ──────────────────────────────
        event_qs = CalendarEvent.objects.select_related(
            "course_offering__course"
        ).filter(start_at__lte=date_to, end_at__gte=date_from)
        if offering_ids is not None:
            # Include course-scoped + personal (null offering)
            from django.db.models import Q

            event_qs = event_qs.filter(
                Q(course_offering_id__in=offering_ids) | Q(course_offering__isnull=True)
            )

        for ev in event_qs:
            events.append(
                {
                    "id": str(ev.id),
                    "sourceType": "EVENT",
                    "sourceId": str(ev.id),
                    "eventType": ev.event_type,
                    "title": ev.title,
                    "description": ev.description,
                    "startAt": ev.start_at.isoformat(),
                    "endAt": ev.end_at.isoformat(),
                    "allDay": ev.is_all_day,
                    "location": ev.location,
                    "courseOfferingId": (
                        str(ev.course_offering_id) if ev.course_offering_id else None
                    ),
                    "courseCode": (
                        ev.course_offering.course.code
                        if ev.course_offering_id
                        else None
                    ),
                    "courseTitle": (
                        ev.course_offering.course.title
                        if ev.course_offering_id
                        else None
                    ),
                    "canEdit": ev.created_by_id == request.user.id or is_staff,
                }
            )

        # ── 2. Assignment due dates ───────────────────────────────
        assign_qs = Assignment.objects.select_related("course_offering__course").filter(
            due_at__gte=date_from,
            due_at__lte=date_to,
            status=AssignmentStatus.PUBLISHED,
        )
        if offering_ids is not None:
            assign_qs = assign_qs.filter(course_offering_id__in=offering_ids)

        for a in assign_qs:
            events.append(
                {
                    "id": f"assignment-{a.id}",
                    "sourceType": "ASSIGNMENT_DUE",
                    "sourceId": str(a.id),
                    "eventType": EventType.ASSIGNMENT_DUE,
                    "title": f"Due: {a.title}",
                    "description": a.description or "",
                    "startAt": a.due_at.isoformat(),
                    "endAt": a.due_at.isoformat(),
                    "allDay": False,
                    "location": "",
                    "courseOfferingId": str(a.course_offering_id),
                    "courseCode": a.course_offering.course.code,
                    "courseTitle": a.course_offering.course.title,
                    "canEdit": False,
                }
            )

        # ── 3. Assessment windows (until available_until) ─────────
        assess_qs = (
            Assessment.objects.select_related("course_offering__course")
            .filter(
                status=AssessmentStatus.PUBLISHED,
            )
            .exclude(available_until__isnull=True)
            .filter(
                available_until__gte=date_from,
                available_until__lte=date_to,
            )
        )
        if offering_ids is not None:
            assess_qs = assess_qs.filter(course_offering_id__in=offering_ids)

        for a in assess_qs:
            event_type = (
                EventType.EXAM
                if a.assessment_type == "FINAL_EXAM"
                else (
                    EventType.QUIZ
                    if a.assessment_type in ("QUIZ", "TEST")
                    else EventType.OTHER
                )
            )
            events.append(
                {
                    "id": f"assessment-{a.id}",
                    "sourceType": "ASSESSMENT_WINDOW",
                    "sourceId": str(a.id),
                    "eventType": event_type,
                    "title": f"{a.title} closes",
                    "description": a.description or "",
                    "startAt": a.available_until.isoformat(),
                    "endAt": a.available_until.isoformat(),
                    "allDay": False,
                    "location": "",
                    "courseOfferingId": str(a.course_offering_id),
                    "courseCode": a.course_offering.course.code,
                    "courseTitle": a.course_offering.course.title,
                    "canEdit": False,
                }
            )

        # ── Sort by start date ────────────────────────────────────
        events.sort(key=lambda e: e["startAt"])

        return success_response(data=events)


def _as_start_of_day(s: str):
    d = parse_date(s)
    if not d:
        return None
    return datetime.combine(d, time.min, tzinfo=dt_timezone.utc)


def _as_end_of_day(s: str):
    d = parse_date(s)
    if not d:
        return None
    return datetime.combine(d, time.max, tzinfo=dt_timezone.utc)
