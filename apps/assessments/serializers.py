from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.files.models import File
from .models import (
    Assessment,
    AssessmentAttempt,
    AssessmentQuestion,
    AttemptStatus,
    Question,
    QuestionBank,
    QuestionOption,
    StudentAnswer,
)


# ──────────────────────────────────────────────────────────────────────
# Question Bank
# ──────────────────────────────────────────────────────────────────────
class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ["id", "text", "is_correct", "position"]
        read_only_fields = ["id"]


class QuestionOptionStudentSerializer(serializers.ModelSerializer):
    """Hides `is_correct` from students."""

    class Meta:
        model = QuestionOption
        fields = ["id", "text", "position"]
        read_only_fields = fields


class QuestionSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True, required=False)
    question_bank_id = serializers.UUIDField(write_only=True, required=False)
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "question_bank_id",
            "question_type",
            "text",
            "explanation",
            "difficulty",
            "default_points",
            "tags",
            "answer_key",
            "numeric_answer",
            "numeric_tolerance",
            "matching_pairs",
            "sample_answer",
            "blank_count",
            "status",
            "current_version",
            "created_by",
            "options",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "current_version",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        options = validated_data.pop("options", [])
        question = Question.objects.create(**validated_data)
        for idx, opt in enumerate(options, start=1):
            QuestionOption.objects.create(
                question=question,
                position=opt.get("position") or idx,
                text=opt["text"],
                is_correct=opt.get("is_correct", False),
            )
        return question

    def update(self, instance, validated_data):
        options = validated_data.pop("options", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if options is not None:
            instance.options.all().delete()
            for idx, opt in enumerate(options, start=1):
                QuestionOption.objects.create(
                    question=instance,
                    position=opt.get("position") or idx,
                    text=opt["text"],
                    is_correct=opt.get("is_correct", False),
                )
        return instance


class QuestionBankSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = QuestionBank
        fields = [
            "id",
            "course",
            "department",
            "title",
            "description",
            "visibility",
            "owner",
            "question_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "question_count", "created_at", "updated_at"]

    def get_question_count(self, obj) -> int:
        return obj.questions.filter(deleted_at__isnull=True).count()


class QuestionBankDetailSerializer(QuestionBankSerializer):
    questions = serializers.SerializerMethodField()

    class Meta(QuestionBankSerializer.Meta):
        fields = QuestionBankSerializer.Meta.fields + ["questions"]

    def get_questions(self, obj):
        qs = obj.questions.filter(deleted_at__isnull=True)
        return QuestionSerializer(qs, many=True).data


# ──────────────────────────────────────────────────────────────────────
# Assessment
# ──────────────────────────────────────────────────────────────────────
class AssessmentQuestionSerializer(serializers.ModelSerializer):
    question = QuestionSerializer(read_only=True)
    question_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = AssessmentQuestion
        fields = ["id", "question", "question_id", "position", "points"]
        read_only_fields = ["id", "question"]


class AssessmentQuestionStudentSerializer(serializers.ModelSerializer):
    """Student-facing — hides correct options."""

    question = serializers.SerializerMethodField()

    class Meta:
        model = AssessmentQuestion
        fields = ["id", "position", "points", "question"]
        read_only_fields = fields

    def get_question(self, obj):
        q = obj.question
        data = {
            "id": str(q.id),
            "question_type": q.question_type,
            "text": q.text,
            "options": QuestionOptionStudentSerializer(q.options.all(), many=True).data,
            "blank_count": q.blank_count,
            "matching_pairs": [
                {"left": p.get("left", "")} for p in (q.matching_pairs or [])
            ],
        }
        return data


class AssessmentSerializer(serializers.ModelSerializer):
    course_offering_id = serializers.UUIDField(write_only=True, required=True)
    created_by = UserSerializer(read_only=True)
    question_count = serializers.SerializerMethodField()
    has_access_code = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            "id",
            "course_offering_id",
            "title",
            "description",
            "instructions",
            "assessment_type",
            "total_points",
            "available_from",
            "available_until",
            "time_limit_minutes",
            "max_attempts",
            "shuffle_questions",
            "shuffle_options",
            "show_results",
            "show_correct_answers",
            "passing_score",
            "status",
            "published_at",
            "created_by",
            "question_count",
            "created_at",
            "updated_at",
            "is_code_gated",
            "ca_opens_at",
            "ca_last_entry_at",
            "serve_question_count",
            "randomize_question_order",
            "has_access_code",
            "proctoring_enabled ",
            "proctoring_max_violations ",
        ]
        read_only_fields = [
            "id",
            "total_points",
            "status",
            "published_at",
            "created_by",
            "question_count",
            "created_at",
            "updated_at",
        ]

    def get_question_count(self, obj) -> int:
        return obj.assessment_questions.count()

    def get_has_access_code(self, obj) -> bool:
        return bool(obj.access_code_hash)


class AssessmentListSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(
        source="course_offering.course.code", read_only=True
    )

    class Meta:
        model = Assessment
        fields = [
            "id",
            "title",
            "assessment_type",
            "course_code",
            "total_points",
            "time_limit_minutes",
            "available_from",
            "available_until",
            "status",
            "created_at",
            "is_code_gated",
            "ca_opens_at",
            "proctoring_enabled ",
            "proctoring_max_violations ",
        ]
        read_only_fields = fields


class AssessmentDetailStudentSerializer(serializers.ModelSerializer):
    """Student-facing — no correct answers, includes user's attempt count."""

    attempts_used = serializers.SerializerMethodField()
    can_start = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            "id",
            "title",
            "description",
            "instructions",
            "assessment_type",
            "total_points",
            "available_from",
            "available_until",
            "time_limit_minutes",
            "max_attempts",
            "attempts_used",
            "can_start",
            "passing_score",
            "is_code_gated",
        ]
        read_only_fields = fields

    def get_attempts_used(self, obj) -> int:
        user = self.context["request"].user
        return obj.attempts.filter(student=user).count()

    def get_can_start(self, obj) -> bool:
        user = self.context["request"].user
        if obj.status != "PUBLISHED":
            return False
        if self.get_attempts_used(obj) >= obj.max_attempts:
            return False
        from django.utils import timezone

        now = timezone.now()
        if obj.available_from and now < obj.available_from:
            return False
        if obj.available_until and now > obj.available_until:
            return False
        return True


# ──────────────────────────────────────────────────────────────────────
# Attempt
# ──────────────────────────────────────────────────────────────────────
class StudentAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAnswer
        fields = [
            "id",
            "assessment_question",
            "answer_text",
            "selected_option_ids",
            "numeric_answer",
            "answer_data",
            "score",
            "is_correct",
            "feedback",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "score",
            "is_correct",
            "feedback",
            "created_at",
            "updated_at",
        ]


class AttemptSerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)
    assessment_title = serializers.CharField(source="assessment.title", read_only=True)

    class Meta:
        model = AssessmentAttempt
        fields = [
            "id",
            "assessment",
            "assessment_title",
            "student",
            "attempt_number",
            "status",
            "started_at",
            "submitted_at",
            "expires_at",
            "total_score",
            "percentage",
            "graded_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AttemptDetailSerializer(AttemptSerializer):
    answers = StudentAnswerSerializer(many=True, read_only=True)

    class Meta(AttemptSerializer.Meta):
        fields = AttemptSerializer.Meta.fields + ["answers"]


class SaveAnswerSerializer(serializers.Serializer):
    answer_text = serializers.CharField(required=False, allow_blank=True)
    selected_option_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False
    )
    numeric_answer = serializers.DecimalField(
        max_digits=12,
        decimal_places=4,
        required=False,
        allow_null=True,
    )
    answer_data = serializers.DictField(required=False)


from .models import AssessmentProctoringEvent


class AssessmentProctoringEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentProctoringEvent
        fields = [
            "id",
            "attempt",
            "event_type",
            "detail",
            "ip_address",
            "user_agent",
            "created_at",
        ]
        read_only_fields = ["id", "attempt", "ip_address", "user_agent", "created_at"]


class LogProctoringEventSerializer(serializers.Serializer):
    event_type = serializers.ChoiceField(
        choices=[
            "TAB_SWITCH",
            "WINDOW_BLUR",
            "FULLSCREEN_EXIT",
            "CONTEXT_MENU",
            "COPY",
            "PASTE",
            "OTHER",
        ]
    )
    detail = serializers.DictField(required=False, default=dict)
