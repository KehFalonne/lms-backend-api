from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.assessments.models import Question, QuestionBank, QuestionStatus
from apps.assessments.serializers import (
    QuestionBankDetailSerializer,
    QuestionBankSerializer,
    QuestionSerializer,
)
from apps.common.responses import error_response, success_response


class QuestionBankListCreateView(APIView):
    """GET/POST /api/v1/question-banks/"""

    serializer_class = QuestionBankSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        qs = QuestionBank.objects.filter(owner=request.user)
        return success_response(data=QuestionBankSerializer(qs, many=True).data)

    def post(self, request):
        serializer = QuestionBankSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bank = QuestionBank.objects.create(
            owner=request.user, **serializer.validated_data
        )
        return success_response(
            data=QuestionBankSerializer(bank).data,
            message="Question bank created.",
            status=status.HTTP_201_CREATED,
        )


class QuestionBankDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/question-banks/{id}/"""

    serializer_class = QuestionBankDetailSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def _get(self, pk, user):
        return get_object_or_404(QuestionBank, pk=pk, owner=user)

    def get(self, request, pk):
        bank = self._get(pk, request.user)
        return success_response(data=QuestionBankDetailSerializer(bank).data)

    def patch(self, request, pk):
        bank = self._get(pk, request.user)
        serializer = QuestionBankSerializer(bank, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(data=QuestionBankSerializer(bank).data)

    def delete(self, request, pk):
        bank = self._get(pk, request.user)
        bank.delete()
        return success_response(message="Question bank deleted.")


class BankQuestionListCreateView(APIView):
    """GET/POST /api/v1/question-banks/{bank_id}/questions/"""

    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, bank_id):
        bank = get_object_or_404(QuestionBank, pk=bank_id, owner=request.user)
        qs = bank.questions.filter(deleted_at__isnull=True).order_by("-created_at")
        return success_response(data=QuestionSerializer(qs, many=True).data)

    def post(self, request, bank_id):
        bank = get_object_or_404(QuestionBank, pk=bank_id, owner=request.user)
        serializer = QuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("question_bank_id", None)
        question = serializer.save(question_bank=bank, created_by=request.user)
        return success_response(
            data=QuestionSerializer(question).data,
            message="Question created.",
            status=status.HTTP_201_CREATED,
        )


class QuestionDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/questions/{id}/"""

    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def _get(self, pk, user):
        return get_object_or_404(
            Question,
            pk=pk,
            question_bank__owner=user,
            deleted_at__isnull=True,
        )

    def get(self, request, pk):
        q = self._get(pk, request.user)
        return success_response(data=QuestionSerializer(q).data)

    def patch(self, request, pk):
        q = self._get(pk, request.user)
        serializer = QuestionSerializer(q, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(data=QuestionSerializer(q).data)

    def delete(self, request, pk):
        q = self._get(pk, request.user)
        from django.utils import timezone

        q.deleted_at = timezone.now()
        q.save(update_fields=["deleted_at", "updated_at"])
        return success_response(message="Question deleted.")


class QuestionDuplicateView(APIView):
    """POST /api/v1/questions/{id}/duplicate/"""

    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request, pk):
        q = get_object_or_404(
            Question,
            pk=pk,
            question_bank__owner=request.user,
            deleted_at__isnull=True,
        )
        new_q = Question.objects.create(
            question_bank=q.question_bank,
            question_type=q.question_type,
            text=q.text,
            explanation=q.explanation,
            difficulty=q.difficulty,
            default_points=q.default_points,
            tags=list(q.tags or []),
            answer_key=list(q.answer_key or []),
            numeric_answer=q.numeric_answer,
            numeric_tolerance=q.numeric_tolerance,
            matching_pairs=list(q.matching_pairs or []),
            sample_answer=q.sample_answer,
            blank_count=q.blank_count,
            created_by=request.user,
        )
        for opt in q.options.all():
            from apps.assessments.models import QuestionOption

            QuestionOption.objects.create(
                question=new_q,
                text=opt.text,
                is_correct=opt.is_correct,
                position=opt.position,
            )
        return success_response(
            data=QuestionSerializer(new_q).data,
            message="Question duplicated.",
            status=status.HTTP_201_CREATED,
        )
