"""
Auto-grading service (backend doc §29).

Handles objective question types:
  • MULTIPLE_CHOICE
  • MULTIPLE_ANSWER
  • TRUE_FALSE
  • SHORT_ANSWER
  • NUMERIC
  • FILL_BLANK

For LONG_ANSWER / MATCHING, marks the attempt as MANUAL_GRADING.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.assessments.models import (
    AssessmentAttempt,
    AttemptStatus,
    QuestionType,
    StudentAnswer,
)

# Question types the auto-grader can score
AUTO_GRADABLE = {
    QuestionType.MULTIPLE_CHOICE,
    QuestionType.MULTIPLE_ANSWER,
    QuestionType.TRUE_FALSE,
    QuestionType.SHORT_ANSWER,
    QuestionType.NUMERIC,
    QuestionType.FILL_BLANK,
}

MANUAL_ONLY = {
    QuestionType.LONG_ANSWER,
    QuestionType.MATCHING,
}


class AutoGradingService:

    @staticmethod
    @transaction.atomic
    def grade_attempt(*, attempt: AssessmentAttempt) -> AssessmentAttempt:
        aqs = attempt.assessment.assessment_questions.select_related("question").all()
        requires_manual = False
        total_score = Decimal("0")

        for aq in aqs:
            answer = attempt.answers.filter(assessment_question=aq).first()
            q = aq.question

            if q.question_type in MANUAL_ONLY:
                requires_manual = True
                continue

            if answer is None:
                # Nothing to grade → zero for this question
                total_score += Decimal("0")
                continue

            is_correct, score = AutoGradingService._grade_one(
                aq=aq,
                answer=answer,
            )
            answer.is_correct = is_correct
            answer.score = score
            answer.graded_at = timezone.now()
            answer.save(
                update_fields=["is_correct", "score", "graded_at", "updated_at"]
            )
            total_score += score

        attempt.total_score = total_score
        total_points = attempt.assessment.total_points or Decimal("0")
        attempt.percentage = (
            (total_score / total_points * Decimal("100")).quantize(Decimal("0.01"))
            if total_points > 0
            else Decimal("0")
        )

        if requires_manual:
            attempt.status = AttemptStatus.MANUAL_GRADING
        else:
            attempt.status = AttemptStatus.AUTO_GRADED
            attempt.graded_at = timezone.now()

        attempt.save(
            update_fields=[
                "total_score",
                "percentage",
                "status",
                "graded_at",
                "updated_at",
            ]
        )
        try:
            from apps.grading.services.grade_service import GradeService

            GradeService.sync_from_attempt(attempt=attempt)
        except Exception:
            pass
        return attempt

    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def _grade_one(*, aq, answer: StudentAnswer) -> tuple[bool, Decimal]:
        q = aq.question
        max_pts = aq.points

        if q.question_type == QuestionType.MULTIPLE_CHOICE:
            correct_ids = set(str(o.id) for o in q.options.filter(is_correct=True))
            selected = set(str(x) for x in (answer.selected_option_ids or []))
            ok = selected == correct_ids
            return ok, max_pts if ok else Decimal("0")

        if q.question_type == QuestionType.TRUE_FALSE:
            correct_ids = set(str(o.id) for o in q.options.filter(is_correct=True))
            selected = set(str(x) for x in (answer.selected_option_ids or []))
            ok = selected == correct_ids
            return ok, max_pts if ok else Decimal("0")

        if q.question_type == QuestionType.MULTIPLE_ANSWER:
            correct_ids = set(str(o.id) for o in q.options.filter(is_correct=True))
            selected = set(str(x) for x in (answer.selected_option_ids or []))
            if not correct_ids:
                return False, Decimal("0")
            hits = len(correct_ids & selected)
            misses = len(selected - correct_ids)
            # Partial credit: (hits/total) - (misses/total), floored at 0
            raw = Decimal(hits) - Decimal(misses)
            if raw <= 0:
                return False, Decimal("0")
            ratio = raw / Decimal(len(correct_ids))
            score = (max_pts * ratio).quantize(Decimal("0.01"))
            return score >= max_pts * Decimal("0.99"), score

        if q.question_type == QuestionType.SHORT_ANSWER:
            submitted = (answer.answer_text or "").strip().lower()
            keys = [str(k).strip().lower() for k in (q.answer_key or [])]
            ok = submitted in keys and bool(submitted)
            return ok, max_pts if ok else Decimal("0")

        if q.question_type == QuestionType.FILL_BLANK:
            # answer_data: {"blanks": ["a", "b", ...]}
            submitted_blanks = (answer.answer_data or {}).get("blanks") or []
            keys = [str(k).strip().lower() for k in (q.answer_key or [])]
            submitted = [str(b).strip().lower() for b in submitted_blanks]
            if not keys:
                return False, Decimal("0")
            hits = sum(1 for a, b in zip(submitted, keys) if a == b)
            ratio = Decimal(hits) / Decimal(len(keys))
            score = (max_pts * ratio).quantize(Decimal("0.01"))
            return hits == len(keys), score

        if q.question_type == QuestionType.NUMERIC:
            if answer.numeric_answer is None or q.numeric_answer is None:
                return False, Decimal("0")
            tolerance = q.numeric_tolerance or Decimal("0")
            diff = abs(Decimal(answer.numeric_answer) - Decimal(q.numeric_answer))
            ok = diff <= tolerance
            return ok, max_pts if ok else Decimal("0")

        # Should not reach here — MANUAL_ONLY is filtered earlier
        return False, Decimal("0")
