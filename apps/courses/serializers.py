from rest_framework import serializers
from apps.accounts.serializers import UserSerializer
from apps.academics.serializers import SemesterSerializer
from apps.university.serializers import DepartmentSerializer, ProgrammeSerializer
from .models import Course, CoursePrerequisite


class CoursePrerequisiteSerializer(serializers.ModelSerializer):
    prerequisite_course = serializers.SerializerMethodField()
    prerequisite_course_id = serializers.UUIDField(
        write_only=True, required=True
    )  # ← explicit

    class Meta:
        model = CoursePrerequisite
        fields = [
            "id",
            "course",
            "prerequisite_course",
            "prerequisite_course_id",
            "minimum_grade",
            "created_at",
        ]
        read_only_fields = ["id", "course", "prerequisite_course", "created_at"]
        # ← extra_kwargs removed entirely

    def get_prerequisite_course(self, obj):
        return {
            "id": str(obj.prerequisite_course_id),
            "code": obj.prerequisite_course.code,
            "title": obj.prerequisite_course.title,
        }


class CourseSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer(read_only=True)
    department_id = serializers.UUIDField(write_only=True, required=True)  # ← explicit
    prerequisite_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Course
        fields = [
            "id",
            "department",
            "department_id",
            "code",
            "title",
            "description",
            "credits",
            "level",
            "course_type",
            "status",
            "prerequisite_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "department",
            "prerequisite_count",
            "created_at",
            "updated_at",
        ]
        # ← extra_kwargs removed entirely


from .models import CourseEnrollment, CourseInstructor, CourseOffering


class CourseOfferingSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    semester = SemesterSerializer(read_only=True)
    programme = ProgrammeSerializer(read_only=True)

    course_id = serializers.UUIDField(write_only=True, required=True)
    semester_id = serializers.UUIDField(write_only=True, required=True)
    programme_id = serializers.UUIDField(write_only=True, required=True)
    eligible_programme_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )
    eligible_programmes = ProgrammeSerializer(many=True, read_only=True)

    enrolled_count = serializers.IntegerField(read_only=True)
    instructor_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CourseOffering
        fields = [
            "id",
            "course",
            "course_id",
            "semester",
            "semester_id",
            "programme",
            "programme_id",
            "eligible_programme_ids",
            "eligible_programmes",
            "section",
            "capacity",
            "status",
            "published_at",
            "enrolled_count",
            "instructor_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "course",
            "semester",
            "programme",
            "published_at",
            "enrolled_count",
            "instructor_count",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        course_id = attrs.get("course_id", getattr(self.instance, "course_id", None))
        programme_id = attrs.get(
            "programme_id", getattr(self.instance, "programme_id", None)
        )
        if course_id and programme_id:
            course = Course.objects.filter(pk=course_id).first()
            from apps.university.models import Programme

            programme = Programme.objects.filter(pk=programme_id).first()
            if course and programme and course.department_id != programme.department_id:
                raise serializers.ValidationError(
                    {
                        "programme_id": (
                            "The programme must belong to the same department "
                            "as the selected course."
                        )
                    }
                )
        return attrs


class CourseOfferingListSerializer(serializers.ModelSerializer):
    """Lean shape for lists — no nested semester/programme."""

    course_code = serializers.CharField(source="course.code", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    semester_name = serializers.CharField(source="semester.name", read_only=True)

    class Meta:
        model = CourseOffering
        fields = [
            "id",
            "course_code",
            "course_title",
            "semester_name",
            "section",
            "capacity",
            "status",
            "created_at",
        ]
        read_only_fields = fields


class CourseInstructorSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True, required=True)

    def validate_user_id(self, value):
        from apps.accounts.models import StudentProfile

        if StudentProfile.objects.filter(user_id=value).exists():
            raise serializers.ValidationError(
                "Students cannot be assigned teaching roles."
            )
        return value

    class Meta:
        model = CourseInstructor
        fields = [
            "id",
            "user",
            "user_id",
            "teaching_role",
            "can_manage_content",
            "can_grade",
            "can_manage_assessments",
            "can_manage_students",
            "assigned_at",
        ]
        read_only_fields = ["id", "user", "assigned_at"]


class CourseEnrollmentSerializer(serializers.ModelSerializer):
    student = UserSerializer(read_only=True)
    student_id = serializers.UUIDField(write_only=True, required=True)

    class Meta:
        model = CourseEnrollment
        fields = [
            "id",
            "student",
            "student_id",
            "status",
            "enrolled_at",
            "withdrawn_at",
            "completed_at",
            "final_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "student",
            "enrolled_at",
            "withdrawn_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]


class BulkEnrollSerializer(serializers.Serializer):
    student_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
    )


class MyCourseEnrollmentSerializer(serializers.ModelSerializer):
    """Student-facing enrollment with the offering embedded."""

    course_offering = serializers.SerializerMethodField()

    class Meta:
        model = CourseEnrollment
        fields = ["id", "course_offering", "status", "enrolled_at"]
        read_only_fields = fields

    def get_course_offering(self, obj):
        o = obj.course_offering
        return {
            "id": str(o.id),
            "course": {
                "id": str(o.course_id),
                "code": o.course.code,
                "title": o.course.title,
                "credits": o.course.credits,
                "level": o.course.level,
            },
            "semester": {
                "id": str(o.semester_id),
                "name": o.semester.name,
                "isCurrent": o.semester.is_current,
            },
            "programme": {
                "id": str(o.programme_id),
                "name": o.programme.name,
            },
            "programmes": [
                {"id": str(o.programme_id), "name": o.programme.name},
                *[
                    {"id": str(p.id), "name": p.name}
                    for p in o.eligible_programmes.all()
                ],
            ],
            "section": o.section,
            "capacity": o.capacity,
            "status": o.status,
        }
