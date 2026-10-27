from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from .models import Grade, GradeCategory, GradeHistory, GradeItem


class GradeCategorySerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = GradeCategory
        fields = [
            "id",
            "course_offering",
            "name",
            "weight",
            "position",
            "item_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "course_offering",
            "item_count",
            "created_at",
            "updated_at",
        ]

    def get_item_count(self, obj) -> int:
        return obj.items.count()


class GradeItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradeItem
        fields = [
            "id",
            "course_offering",
            "category",
            "name",
            "max_score",
            "weight",
            "source_type",
            "source_id",
            "position",
            "is_published",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "course_offering",
            "is_published",
            "created_at",
            "updated_at",
        ]


class GradeSerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)
    grade_item = GradeItemSerializer(read_only=True)
    percentage = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = Grade
        fields = [
            "id",
            "grade_item",
            "student",
            "score",
            "percentage",
            "letter_grade",
            "feedback",
            "status",
            "graded_by",
            "graded_at",
            "published_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "student",
            "grade_item",
            "percentage",
            "letter_grade",
            "status",
            "graded_by",
            "graded_at",
            "published_at",
            "created_at",
            "updated_at",
        ]


class GradeHistorySerializer(serializers.ModelSerializer):
    changed_by = UserSerializer(read_only=True)

    class Meta:
        model = GradeHistory
        fields = [
            "id",
            "previous_score",
            "new_score",
            "previous_status",
            "new_status",
            "reason",
            "changed_by",
            "changed_at",
        ]
        read_only_fields = fields


class SetGradeSerializer(serializers.Serializer):
    score = serializers.DecimalField(max_digits=7, decimal_places=2, allow_null=True)
    feedback = serializers.CharField(required=False, allow_blank=True, default="")
    reason = serializers.CharField(
        required=False, allow_blank=True, default="Manual update"
    )


class SetWeightsSerializer(serializers.Serializer):
    weights = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False,
    )

    def validate_weights(self, value):
        required = {"name", "weight"}
        for w in value:
            missing = required - set(w.keys())
            if missing:
                raise serializers.ValidationError(
                    f"Each entry must contain {required}. Missing: {missing}"
                )
        return value
