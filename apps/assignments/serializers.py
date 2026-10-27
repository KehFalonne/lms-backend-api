from rest_framework import serializers
from apps.accounts.serializers import UserSerializer
from apps.files.models import File
from .models import (
    Assignment,
    AssignmentSubmission,
    Feedback,
    SubmissionFile,
)

# ──────────────────────────────────────────────────────────────────────
# Assignment
# ──────────────────────────────────────────────────────────────────────


class AssignmentSerializer(serializers.ModelSerializer):
    course_offering_id = serializers.UUIDField(write_only=True, required=False)
    created_by = UserSerializer(read_only=True)
    submission_count = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            "id",
            "course_offering_id",
            "title",
            "description",
            "instructions",
            "max_score",
            "available_from",
            "due_at",
            "available_until",
            "allow_late_submission",
            "late_penalty_type",
            "late_penalty_value",
            "submission_type",
            "max_attempts",
            "status",
            "published_at",
            "created_by",
            "submission_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "published_at",
            "created_by",
            "submission_count",
            "created_at",
            "updated_at",
        ]

    # ─── this MUST be at the class level, NOT inside Meta ───
    def get_submission_count(self, obj) -> int:
        return obj.submissions.count()


class AssignmentListSerializer(serializers.ModelSerializer):
    """Lean shape for lists — no nested relations, no submission count."""

    class Meta:
        model = Assignment
        fields = [
            "id",
            "title",
            "max_score",
            "due_at",
            "status",
            "submission_type",
            "created_at",
        ]
        read_only_fields = fields


# ──────────────────────────────────────────────────────────────────────
# Submission
# ──────────────────────────────────────────────────────────────────────
class SubmissionFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionFile
        fields = ["id", "file", "created_at"]
        read_only_fields = fields


class FeedbackSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = Feedback
        fields = ["id", "author", "content", "created_at"]
        read_only_fields = fields


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)
    files = SubmissionFileSerializer(many=True, read_only=True)
    feedback_entries = FeedbackSerializer(many=True, read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = [
            "id",
            "assignment",
            "student",
            "attempt_number",
            "status",
            "submitted_at",
            "is_late",
            "text_content",
            "files",
            "score",
            "feedback",
            "feedback_entries",
            "graded_by",
            "graded_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# class SubmissionCreateSerializer(serializers.Serializer):
#     text_content = serializers.CharField(required=False, allow_blank=True, default="")
#     field_ids = serializers.ListField(
#         child=serializers.UUIDField(),
#         required=False,
#         default=list,
#     )


class SubmissionCreateSerializer(serializers.Serializer):
    text_content = serializers.CharField(required=False, allow_blank=True, default="")
    file_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )

    def to_internal_value(self, data):
        # Defensive: accept camelCase even if the parser didn't convert.
        if hasattr(data, "dict"):
            data = data.dict()
        else:
            data = dict(data)

        if "fileIds" in data and "file_ids" not in data:
            data["file_ids"] = data.pop("fileIds")
        if "textContent" in data and "text_content" not in data:
            data["text_content"] = data.pop("textContent")

        return super().to_internal_value(data)


class GradeSubmissionSerializer(serializers.Serializer):
    score = serializers.DecimalField(max_digits=6, decimal_places=2)
    feedback = serializers.CharField(required=False, allow_blank=True, default="")
