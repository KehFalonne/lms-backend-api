from django.shortcuts import get_object_or_404
from docx import Document
from docx.opc.exceptions import PackageNotFoundError
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
from apps.assessments.services.word_import_service import (
    apply_answer_key_to_questions,
    import_word_questions,
    parse_answer_key,
    parse_answer_key_document,
    parse_answer_key_texts,
)
from apps.common.responses import error_response, success_response
from apps.courses.models import CourseOffering


def _is_admin(user) -> bool:
    return bool(user.is_superuser or getattr(user, "is_staff", False))


def _bank_for(bank_id, user) -> QuestionBank:
    kwargs = {"pk": bank_id}
    if not _is_admin(user):
        kwargs["owner"] = user
    return get_object_or_404(QuestionBank, **kwargs)


def _question_for(pk, user) -> Question:
    kwargs = {"pk": pk, "deleted_at__isnull": True}
    if not _is_admin(user):
        kwargs["question_bank__owner"] = user
    return get_object_or_404(Question, **kwargs)


class QuestionBankListCreateView(APIView):
    """GET/POST /api/v1/question-banks/"""

    serializer_class = QuestionBankSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        qs = QuestionBank.objects.all() if _is_admin(request.user) else QuestionBank.objects.filter(owner=request.user)
        offering_id = request.query_params.get("courseOfferingId")
        if offering_id:
            offering = get_object_or_404(CourseOffering, pk=offering_id)
            qs = qs.filter(course_id=offering.course_id)
        return success_response(data=QuestionBankSerializer(qs, many=True).data)

    def post(self, request):
        payload = request.data.copy()
        offering_id = payload.pop("courseOfferingId", None) or payload.pop(
            "course_offering_id", None
        )
        if offering_id:
            if isinstance(offering_id, (list, tuple)):
                offering_id = offering_id[0]
            offering = get_object_or_404(CourseOffering, pk=offering_id)
            payload["course"] = offering.course_id
            payload["department"] = offering.course.department_id
        serializer = QuestionBankSerializer(data=payload)
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
        return _bank_for(pk, user)

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
        bank = _bank_for(bank_id, request.user)
        qs = bank.questions.filter(deleted_at__isnull=True).order_by("-created_at")
        return success_response(data=QuestionSerializer(qs, many=True).data)

    def post(self, request, bank_id):
        bank = _bank_for(bank_id, request.user)
        serializer = QuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("question_bank_id", None)
        question = serializer.save(question_bank=bank, created_by=request.user)
        return success_response(
            data=QuestionSerializer(question).data,
            message="Question created.",
            status=status.HTTP_201_CREATED,
        )


class BankQuestionWordImportView(APIView):
    """POST /api/v1/question-banks/{bank_id}/questions/import-word/"""

    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request, bank_id):
        bank = _bank_for(bank_id, request.user)
        upload = request.FILES.get("file")
        if upload is None:
            return error_response("A .docx Word document is required.", status_code=400)
        if not upload.name.lower().endswith(".docx"):
            return error_response("Only .docx Word documents are supported.", status_code=400)
        if upload.size > 10 * 1024 * 1024:
            return error_response("The Word document must be 10 MB or smaller.", status_code=400)

        try:
            document = Document(upload)
        except (PackageNotFoundError, ValueError, TypeError):
            return error_response("The uploaded Word document could not be read.", status_code=400)

        questions = import_word_questions(bank, document, request.user)
        if not questions:
            return error_response(
                "No questions were found. Use numbered questions with A/B/C options.",
                status_code=400,
            )
        return success_response(
            data=QuestionSerializer(questions, many=True).data,
            message=f"{len(questions)} questions imported as drafts.",
            status=status.HTTP_201_CREATED,
        )


class BankQuestionAnswerKeyImportView(APIView):
    """POST /api/v1/question-banks/{bank_id}/questions/import-answer-key/"""

    permission_classes = [IsAuthenticatedAndActive]

    def post(self, request, bank_id):
        bank = _bank_for(bank_id, request.user)
        upload = request.FILES.get("file")
        if upload is None:
            return error_response(
                "An answer key file (.docx or .txt) is required.", status_code=400
            )
        if upload.size > 10 * 1024 * 1024:
            return error_response("The file must be 10 MB or smaller.", status_code=400)

        name = upload.name.lower()
        answer_texts = None
        if name.endswith(".docx"):
            try:
                document = Document(upload)
            except (PackageNotFoundError, ValueError, TypeError):
                return error_response(
                    "The uploaded Word document could not be read.", status_code=400
                )
            entries = parse_answer_key_document(document)
            answer_texts = parse_answer_key_texts(document)
        elif name.endswith(".txt"):
            try:
                text = upload.read().decode("utf-8-sig")
            except UnicodeDecodeError:
                return error_response(
                    "The text file must be UTF-8 encoded.", status_code=400
                )
            entries = parse_answer_key(
                [line for line in text.splitlines() if line.strip()]
            )
        else:
            return error_response(
                "Only .docx or .txt answer key files are supported.", status_code=400
            )

        if not entries:
            return error_response(
                'No answer keys were found. Use lines like "1. B" or "1-B, 2-C", '
                "or a table with question numbers and letters.",
                status_code=400,
            )

        questions = list(
            bank.questions.filter(deleted_at__isnull=True).order_by("created_at", "id")
        )

        question_ids = (
            request.data.getlist("question_ids")
            if hasattr(request.data, "getlist")
            else request.data.get("question_ids")
        )
        if question_ids:
            if isinstance(question_ids, str):
                question_ids = [question_ids]
            id_set = {str(qid) for qid in question_ids}
            selected = [q for q in questions if str(q.id) in id_set]
            if not selected:
                return error_response(
                    "The selected questions were not found in this bank.",
                    status_code=400,
                )
            questions = selected

        if not questions:
            return error_response(
                "This bank has no questions yet. Import questions first.",
                status_code=400,
            )

        applied = apply_answer_key_to_questions(questions, entries, answer_texts)
        if applied == 0:
            return error_response(
                "No answer keys could be matched to questions in this bank.",
                status_code=400,
            )

        return success_response(
            data={"applied": applied, "total_questions": len(questions)},
            message=f"Answer key applied to {applied} of {len(questions)} questions.",
        )


class QuestionDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/questions/{id}/"""

    serializer_class = QuestionSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def _get(self, pk, user):
        return _question_for(pk, user)

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
        q = _question_for(pk, request.user)
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
