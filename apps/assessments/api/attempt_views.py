from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.assessments.models import (
    Assessment,
    AssessmentAttempt,
    AttemptStatus,
    StudentAnswer,
)
from apps.assessments.serializers import (
    AttemptDetailSerializer,
    AttemptSerializer,
    SaveAnswerSerializer,
    StudentAnswerSerializer,
    LogProctoringEventSerializer,
)
from apps.assessments.services.attempt_service import AttemptService
from apps.common.responses import error_response, success_response


class StartAttemptView(APIView):
    """POST /api/v1/assessments/{id}/attempts/start/"""

    serializer_class = AttemptSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request, pk):
        assessment = get_object_or_404(Assessment, pk=pk)
        try:
            attempt = AttemptService.start_attempt(
                assessment=assessment,
                student=request.user,
            )
        except Exception as exc:
            detail = getattr(exc, "detail", str(exc))
            if isinstance(detail, dict):
                detail = "; ".join(
                    f"{k}: {', '.join(v) if isinstance(v, list) else v}"
                    for k, v in detail.items()
                )
            return error_response(str(detail), status_code=400)

        # Record learning event (fire-and-forget)
        try:
            from apps.analytics.services.event_service import EventService

            EventService.record(
                student=request.user,
                event_type="ASSESSMENT_STARTED",
                course_offering=assessment.course_offering,
                entity_type="assessment",
                entity_id=assessment.id,
            )
        except Exception:
            pass

        return success_response(
            data=AttemptDetailSerializer(attempt).data,
            message="Attempt started.",
            status=status.HTTP_201_CREATED,
        )


class AttemptDetailView(APIView):
    """GET /api/v1/assessment-attempts/{id}/"""

    serializer_class = AttemptDetailSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, pk):
        attempt = get_object_or_404(
            AssessmentAttempt.objects.select_related("assessment", "student"),
            pk=pk,
        )
        # Student sees own; staff with course content permission sees any
        if attempt.student_id != request.user.id:
            from apps.courses.permissions import CanManageCourseContent

            if not CanManageCourseContent().has_object_permission(
                request, self, attempt.assessment.course_offering
            ):
                return error_response("Not allowed.", status_code=403)

        # Auto-expire on read
        AttemptService.expire_if_needed(attempt)
        attempt.refresh_from_db()

        return success_response(data=AttemptDetailSerializer(attempt).data)


class SaveAnswerView(APIView):
    """PUT /api/v1/assessment-attempts/{id}/answers/{question_id}/"""

    serializer_class = SaveAnswerSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def put(self, request, attempt_id, question_id):
        attempt = get_object_or_404(AssessmentAttempt, pk=attempt_id)
        serializer = SaveAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            answer = AttemptService.save_answer(
                attempt=attempt,
                student=request.user,
                assessment_question_id=question_id,
                answer_text=serializer.validated_data.get("answer_text"),
                selected_option_ids=[
                    str(x)
                    for x in serializer.validated_data.get("selected_option_ids", [])
                ]
                or None,
                numeric_answer=serializer.validated_data.get("numeric_answer"),
                answer_data=serializer.validated_data.get("answer_data"),
            )
        except Exception as exc:
            detail = getattr(exc, "detail", str(exc))
            if isinstance(detail, dict):
                detail = "; ".join(
                    f"{k}: {', '.join(v) if isinstance(v, list) else v}"
                    for k, v in detail.items()
                )
            return error_response(str(detail), status_code=400)

        return success_response(
            data=StudentAnswerSerializer(answer).data,
            message="Answer saved.",
        )


class SubmitAttemptView(APIView):
    """POST /api/v1/assessment-attempts/{id}/submit/"""

    serializer_class = AttemptDetailSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request, pk):
        attempt = get_object_or_404(
            AssessmentAttempt.objects.select_related("assessment"), pk=pk
        )
        try:
            attempt = AttemptService.submit_attempt(
                attempt=attempt,
                student=request.user,
            )
        except Exception as exc:
            detail = getattr(exc, "detail", str(exc))
            if isinstance(detail, dict):
                detail = "; ".join(
                    f"{k}: {', '.join(v) if isinstance(v, list) else v}"
                    for k, v in detail.items()
                )
            return error_response(str(detail), status_code=400)

        # Record learning event (fire-and-forget)
        try:
            from apps.analytics.services.event_service import EventService

            EventService.record(
                student=request.user,
                event_type="ASSESSMENT_SUBMITTED",
                course_offering=attempt.assessment.course_offering,
                entity_type="assessment",
                entity_id=attempt.assessment_id,
            )
        except Exception:
            pass

        # Notify instructors if manual grading is needed
        if attempt.status == AttemptStatus.MANUAL_GRADING:
            try:
                from apps.courses.models import CourseInstructor
                from apps.notifications.services.notification_service import (
                    NotificationService,
                )
                from django.contrib.auth import get_user_model

                User = get_user_model()
                instructor_ids = CourseInstructor.objects.filter(
                    course_offering_id=attempt.assessment.course_offering_id,
                    can_grade=True,
                ).values_list("user_id", flat=True)

                recipients = list(
                    User.objects.filter(id__in=instructor_ids, is_active=True)
                )
                if recipients:
                    NotificationService.push_bulk(
                        recipients=recipients,
                        type="ASSESSMENT",
                        title=f"Manual grading needed: {attempt.assessment.title}",
                        message=(
                            f"{request.user.first_name} {request.user.last_name} "
                            f"submitted an attempt requiring manual grading."
                        ),
                        entity_type="assessment_attempt",
                        entity_id=attempt.id,
                        data={
                            "attemptId": str(attempt.id),
                            "assessmentId": str(attempt.assessment_id),
                        },
                    )
            except Exception:
                pass

        return success_response(
            data=AttemptDetailSerializer(attempt).data,
            message="Attempt submitted.",
        )


class MyAssessmentsView(APIView):
    """GET /api/v1/my/assessments/"""

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        from django.utils import timezone
        from apps.courses.models import CourseEnrollment, EnrollmentStatus

        offering_ids = CourseEnrollment.objects.filter(
            student=request.user,
            status=EnrollmentStatus.ACTIVE,
        ).values_list("course_offering_id", flat=True)

        qs = (
            Assessment.objects.filter(
                course_offering_id__in=offering_ids,
                status="PUBLISHED",
            )
            .select_related("course_offering__course")
            .order_by("-available_from", "-created_at")
        )

        now = timezone.now()
        data = []
        for a in qs:
            attempts = a.attempts.filter(student=request.user).order_by(
                "-attempt_number"
            )
            used = attempts.count()
            last = attempts.first()

            can_start = (
                used < a.max_attempts
                and (not a.available_from or now >= a.available_from)
                and (not a.available_until or now <= a.available_until)
            )

            data.append(
                {
                    "id": str(a.id),
                    "title": a.title,
                    "description": a.description,
                    "courseOfferingId": str(a.course_offering_id),
                    "courseCode": a.course_offering.course.code,
                    "courseTitle": a.course_offering.course.title,
                    "assessmentType": a.assessment_type,
                    "totalPoints": str(a.total_points),
                    "timeLimitMinutes": a.time_limit_minutes,
                    "maxAttempts": a.max_attempts,
                    "attemptsUsed": used,
                    "isCodeGated": bool(a.is_code_gated),
                    "caOpensAt": (a.ca_opens_at.isoformat() if a.ca_opens_at else None),
                    "caLastEntryAt": (
                        a.ca_last_entry_at.isoformat() if a.ca_last_entry_at else None
                    ),
                    "hasAccessCode": bool(a.access_code_hash),
                    "availableFrom": (
                        a.available_from.isoformat() if a.available_from else None
                    ),
                    "availableUntil": (
                        a.available_until.isoformat() if a.available_until else None
                    ),
                    "passingScore": str(a.passing_score),
                    "canStart": can_start,
                    "lastAttempt": (
                        {
                            "id": str(last.id),
                            "status": last.status,
                            "totalScore": str(last.total_score),
                            "percentage": str(last.percentage),
                            "submittedAt": (
                                last.submitted_at.isoformat()
                                if last.submitted_at
                                else None
                            ),
                        }
                        if last
                        else None
                    ),
                }
            )

        return success_response(data=data)


class AttemptLiveView(APIView):
    """
    GET /api/v1/assessment-attempts/{id}/live/

    Single-call payload for the live attempt UI:
    - Assessment + attempt metadata
    - Full question set (correct answers hidden)
    - Existing answers keyed by assessment-question ID

    If the attempt is no longer IN_PROGRESS, the frontend should redirect
    to the result page based on `status`.
    """

    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, pk):
        attempt = get_object_or_404(
            AssessmentAttempt.objects.select_related("assessment"),
            pk=pk,
        )
        if attempt.student_id != request.user.id:
            return error_response("Not allowed.", status_code=403)

        # Auto-expire if past time limit
        AttemptService.expire_if_needed(attempt)
        attempt.refresh_from_db()

        aqs_qs = (
            attempt.assessment.assessment_questions.select_related("question")
            .prefetch_related("question__options")
            .order_by("position")
        )
        # Apply served_questions if this attempt is randomized
        if attempt.served_questions:
            from django.db.models import Case, When, IntegerField

            served_ids = attempt.served_questions
            aqs_qs = (
                aqs_qs.filter(id__in=served_ids)
                .annotate(
                    _served_order=Case(
                        *[When(id=sid, then=idx) for idx, sid in enumerate(served_ids)],
                        output_field=IntegerField(),
                    )
                )
                .order_by("_served_order")
            )

        import hashlib

        aqs = aqs_qs

        def _shuffle_key(attempt_id, option_id) -> str:
            return hashlib.sha256(f"{attempt_id}:{option_id}".encode()).hexdigest()

        questions = []
        for idx, aq in enumerate(aqs):
            q = aq.question
            options_list = list(q.options.all().order_by("position"))

            # Option-level shuffle — deterministic per attempt, per question.
            # Same student reloading the same attempt sees the same order.
            if attempt.assessment.shuffle_options and len(options_list) > 1:
                options_list.sort(key=lambda o: _shuffle_key(attempt.id, o.id))

            questions.append(
                {
                    "id": str(aq.id),
                    "questionId": str(q.id),
                    "position": idx + 1,  # served-order position, not original
                    "points": str(aq.points),
                    "questionType": q.question_type,
                    "text": q.text,
                    "options": [
                        {"id": str(o.id), "text": o.text, "position": i + 1}
                        for i, o in enumerate(options_list)
                    ],
                    "blankCount": q.blank_count,
                    "matchingPairs": [
                        {"left": p.get("left", "")} for p in (q.matching_pairs or [])
                    ],
                }
            )

        answers = {
            str(a.assessment_question_id): {
                "answerText": a.answer_text,
                "selectedOptionIds": a.selected_option_ids or [],
                "numericAnswer": (
                    str(a.numeric_answer) if a.numeric_answer is not None else None
                ),
                "answerData": a.answer_data or {},
            }
            for a in attempt.answers.all()
        }

        return success_response(
            data={
                "id": str(attempt.id),
                "assessmentId": str(attempt.assessment_id),
                "assessmentTitle": attempt.assessment.title,
                "timeLimitMinutes": attempt.assessment.time_limit_minutes,
                "startedAt": attempt.started_at.isoformat(),
                "expiresAt": (
                    attempt.expires_at.isoformat() if attempt.expires_at else None
                ),
                "status": attempt.status,
                "totalPoints": str(attempt.assessment.total_points),
                "questions": questions,
                "answers": answers,
                "proctoringEnabled": bool(attempt.assessment.proctoring_enabled),
                "proctoringMaxViolations": int(
                    attempt.assessment.proctoring_max_violations or 0
                ),
            }
        )


class AttemptProctoringEventView(APIView):
    """
    POST /api/v1/assessment-attempts/{id}/proctoring-events/
      Body: { "eventType": "TAB_SWITCH", "detail": {...} }
      Student-only — logs one integrity event for this attempt.

    GET /api/v1/assessment-attempts/{id}/proctoring-events/
      Lecturers/admins only — returns the full event log for this attempt.
    """

    serializer_class = LogProctoringEventSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, pk):
        from apps.assessments.serializers import (
            AssessmentProctoringEventSerializer,
        )

        attempt = get_object_or_404(
            AssessmentAttempt.objects.select_related(
                "assessment__course_offering", "student"
            ),
            pk=pk,
        )

        # Staff or grading instructor on this offering
        is_allowed = request.user.is_staff or request.user.is_superuser
        if not is_allowed:
            from apps.courses.permissions import CanManageCourseContent

            if not CanManageCourseContent().has_object_permission(
                request, self, attempt.assessment.course_offering
            ):
                return error_response("Not allowed.", status_code=403)

        qs = attempt.proctoring_events.order_by("-created_at")
        return success_response(
            data=AssessmentProctoringEventSerializer(qs, many=True).data
        )

    def post(self, request, pk):
        from apps.assessments.models import (
            AssessmentProctoringEvent,
            AttemptStatus,
        )

        attempt = get_object_or_404(AssessmentAttempt, pk=pk)

        if attempt.student_id != request.user.id:
            return error_response("Not allowed.", status_code=403)
        if attempt.status != AttemptStatus.IN_PROGRESS:
            return error_response("Attempt is not in progress.", status_code=400)
        if not attempt.assessment.proctoring_enabled:
            return error_response(
                "Proctoring is not enabled for this assessment.",
                status_code=400,
            )

        serializer = LogProctoringEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[
            0
        ].strip() or request.META.get("REMOTE_ADDR")
        ua = (request.META.get("HTTP_USER_AGENT") or "")[:500]

        AssessmentProctoringEvent.objects.create(
            attempt=attempt,
            event_type=serializer.validated_data["event_type"],
            detail=serializer.validated_data.get("detail") or {},
            ip_address=ip or None,
            user_agent=ua,
        )

        return success_response(message="Event logged.")
