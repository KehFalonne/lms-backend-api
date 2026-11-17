from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import (
    Role,
    RoleScope,
    StudentProfile,
    User,
    UserRole,
    UserStatus,
)
from apps.files.models import File, FileStatus
from apps.files.services.file_service import FileService
from .profile import StaffProfileSerializer, StudentProfileSerializer


class UserSerializer(serializers.ModelSerializer):
    """List / detail serializer — no nested profiles."""

    full_name = serializers.SerializerMethodField()
    student_profile = StudentProfileSerializer(read_only=True)
    staff_profile = StaffProfileSerializer(read_only=True)
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "university_id",
            "email",
            "first_name",
            "middle_name",
            "last_name",
            "full_name",
            "phone",
            "avatar",
            "status",
            "is_staff",
            "is_active",
            "email_verified_at",
            "last_login_at",
            "created_at",
            "updated_at",
            "student_profile",
            "staff_profile",
        ]
        read_only_fields = [
            "id",
            "email_verified_at",
            "last_login_at",
            "created_at",
            "updated_at",
        ]

    def get_full_name(self, obj: User) -> str:
        return obj.get_full_name()

    def get_avatar(self, obj: User) -> str:
        if obj.avatar_file_id and obj.avatar_file.status == FileStatus.READY:
            url = FileService.get_download_url(obj.avatar_file, expires_in=3600)
            request = self.context.get("request")
            if request and url.startswith("/"):
                return request.build_absolute_uri(url)
            return url
        return obj.avatar or ""


class UserMeSerializer(UserSerializer):
    """`/auth/me/` — includes roles and profiles."""

    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    user_roles = serializers.SerializerMethodField()
    student_profile = StudentProfileSerializer(read_only=True)
    staff_profile = StaffProfileSerializer(read_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + [
            "is_superuser",
            "roles",
            "permissions",
            "user_roles",
        ]
        read_only_fields = fields

    def get_roles(self, obj) -> list[str]:
        return obj.get_role_codes()

    def get_permissions(self, obj) -> list[str]:
        return obj.get_permission_codes()

    def get_user_roles(self, obj):
        from .rbac import UserRoleSerializer

        return UserRoleSerializer(
            obj.user_roles.select_related("role", "assigned_by").all(),
            many=True,
        ).data


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, min_length=8, style={"input_type": "password"}
    )
    # Optional: attach a profile at creation time
    matricule_number = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    staff_number = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    current_level = serializers.IntegerField(
        write_only=True, required=False, default=100
    )
    admission_year = serializers.IntegerField(
        write_only=True, required=False, allow_null=True
    )
    programme_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    department_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    job_title = serializers.CharField(write_only=True, required=False, allow_blank=True)
    student_status = serializers.ChoiceField(
        write_only=True,
        required=False,
        choices=StudentProfile.StudentStatus.choices,
    )
    admission_date = serializers.DateField(
        write_only=True, required=False, allow_null=True
    )
    profile_type = serializers.ChoiceField(
        write_only=True, required=False, choices=["student", "staff", "none"]
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "university_id",
            "password",
            "first_name",
            "middle_name",
            "last_name",
            "phone",
            "status",
            # profile side-channel
            "matricule_number",
            "staff_number",
            "current_level",
            "admission_year",
            "programme_id",
            "department_id",
            "job_title",
            "student_status",
            "admission_date",
            "profile_type",
        ]
        read_only_fields = ["id"]

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower().strip()

    def validate_university_id(self, value):
        value = value.strip().upper()
        if User.objects.filter(university_id=value).exists():
            raise serializers.ValidationError(
                "A user with this university ID already exists."
            )
        return value

    def validate(self, attrs):
        profile_type = attrs.get("profile_type", "none")
        if profile_type == "student" and not attrs.get("matricule_number"):
            raise serializers.ValidationError(
                {"matricule_number": "Matricule is required for a student profile."}
            )
        if profile_type == "staff" and not attrs.get("staff_number"):
            raise serializers.ValidationError(
                {"staff_number": "Staff number is required for a staff profile."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        # Pop profile side-channel data
        matricule = validated_data.pop("matricule_number", "") or None
        staff_number = validated_data.pop("staff_number", "") or None
        current_level = validated_data.pop("current_level", 100)
        admission_year = validated_data.pop("admission_year", None)
        programme_id = validated_data.pop("programme_id", None)
        department_id = validated_data.pop("department_id", None)
        job_title = validated_data.pop("job_title", "")
        student_status = validated_data.pop(
            "student_status", StudentProfile.StudentStatus.ACTIVE
        )
        admission_date = validated_data.pop("admission_date", None)
        profile_type = validated_data.pop("profile_type", "none")

        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)

        if user.status in {UserStatus.INACTIVE, UserStatus.LOCKED}:
            user.is_active = False
            user.save(update_fields=["is_active", "updated_at"])

        if profile_type == "student":
            StudentProfile.objects.create(
                user=user,
                matricule_number=matricule,
                programme_id=programme_id,
                current_level=current_level or 100,
                admission_year=admission_year or user.created_at.year,
                admission_date=admission_date,
                status=student_status,
            )
            student_role = Role.objects.filter(code="STUDENT").first()
            if student_role:
                request = self.context.get("request")
                UserRole.objects.create(
                    user=user,
                    role=student_role,
                    scope_type=RoleScope.GLOBAL,
                    assigned_by=request.user if request else None,
                )
        elif profile_type == "staff":
            from apps.accounts.models import StaffProfile

            StaffProfile.objects.create(
                user=user,
                staff_number=staff_number,
                department_id=department_id,
                job_title=job_title,
            )

        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=False, min_length=8
    )
    matricule_number = serializers.CharField(
        write_only=True, required=False, allow_blank=False
    )
    staff_number = serializers.CharField(
        write_only=True, required=False, allow_blank=False
    )
    current_level = serializers.IntegerField(write_only=True, required=False)
    admission_year = serializers.IntegerField(write_only=True, required=False)
    programme_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    department_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    job_title = serializers.CharField(write_only=True, required=False, allow_blank=True)
    student_status = serializers.ChoiceField(
        write_only=True,
        required=False,
        choices=StudentProfile.StudentStatus.choices,
    )
    admission_date = serializers.DateField(
        write_only=True, required=False, allow_null=True
    )
    profile_type = serializers.ChoiceField(
        write_only=True, required=False, choices=["student", "staff", "none"]
    )
    avatar_file_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = User
        fields = [
            "email",
            "university_id",
            "first_name",
            "middle_name",
            "last_name",
            "phone",
            "avatar",
            "avatar_file_id",
            "status",
            "password",
            "matricule_number",
            "staff_number",
            "current_level",
            "admission_year",
            "programme_id",
            "department_id",
            "job_title",
            "student_status",
            "admission_date",
            "profile_type",
        ]

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_university_id(self, value):
        value = value.strip().upper()
        if User.objects.filter(university_id=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError(
                "A user with this university ID already exists."
            )
        return value

    def validate(self, attrs):
        avatar_file_id = attrs.get("avatar_file_id")
        if avatar_file_id:
            file = File.objects.filter(
                id=avatar_file_id,
                status=FileStatus.READY,
                uploaded_by=self.context["request"].user,
            ).first()
            if not file:
                raise serializers.ValidationError(
                    {"avatar_file_id": "The uploaded avatar is not available."}
                )
            if not file.mime_type.startswith("image/"):
                raise serializers.ValidationError(
                    {"avatar_file_id": "Avatar must be an image."}
                )
        profile_type = attrs.get("profile_type")
        if profile_type == "student":
            from apps.accounts.services.rbac_service import TEACHING_ROLE_CODES
            from apps.courses.models import CourseInstructor

            if CourseInstructor.objects.filter(user=self.instance).exists() or self.instance.user_roles.filter(
                role__code__in=TEACHING_ROLE_CODES
            ).exists():
                raise serializers.ValidationError(
                    {
                        "profile_type": (
                            "Users with teaching assignments cannot be "
                            "converted to a student profile."
                        )
                    }
                )
        if profile_type == "student" and not (
            attrs.get("matricule_number") or hasattr(self.instance, "student_profile")
        ):
            raise serializers.ValidationError(
                {"matricule_number": "Matricule is required for a student profile."}
            )
        if profile_type == "staff" and not (
            attrs.get("staff_number") or hasattr(self.instance, "staff_profile")
        ):
            raise serializers.ValidationError(
                {"staff_number": "Staff number is required for a staff profile."}
            )
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        from apps.accounts.models import StaffProfile, StudentProfile

        password = validated_data.pop("password", None)
        profile_type = validated_data.pop("profile_type", None)
        avatar_file_id = validated_data.pop("avatar_file_id", None)
        matricule = validated_data.pop("matricule_number", None)
        staff_number = validated_data.pop("staff_number", None)
        current_level = validated_data.pop("current_level", None)
        admission_year = validated_data.pop("admission_year", None)
        programme_id = validated_data.pop("programme_id", None)
        department_id = validated_data.pop("department_id", None)
        job_title = validated_data.pop("job_title", None)
        student_status = validated_data.pop("student_status", None)
        admission_date = validated_data.pop("admission_date", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if "status" in validated_data:
            instance.is_active = validated_data["status"] not in {
                UserStatus.INACTIVE,
                UserStatus.LOCKED,
            }
        if password:
            instance.set_password(password)
        if avatar_file_id is not None:
            instance.avatar_file_id = avatar_file_id
            instance.avatar = ""
        instance.save()

        if profile_type == "none":
            if hasattr(instance, "student_profile"):
                instance.student_profile.delete()
            if hasattr(instance, "staff_profile"):
                instance.staff_profile.delete()
        elif profile_type == "student" or (
            profile_type is None and hasattr(instance, "student_profile")
        ):
            if hasattr(instance, "staff_profile"):
                instance.staff_profile.delete()
            profile, _ = StudentProfile.objects.get_or_create(
                user=instance,
                defaults={
                    "matricule_number": matricule,
                    "admission_year": admission_year or instance.created_at.year,
                },
            )
            if matricule is not None:
                profile.matricule_number = matricule
            if current_level is not None:
                profile.current_level = current_level
            if admission_year is not None:
                profile.admission_year = admission_year
            if programme_id is not None:
                profile.programme_id = programme_id
            if student_status is not None:
                profile.status = student_status
            if admission_date is not None:
                profile.admission_date = admission_date
            profile.save()
        elif profile_type == "staff" or (
            profile_type is None and hasattr(instance, "staff_profile")
        ):
            if hasattr(instance, "student_profile"):
                instance.student_profile.delete()
            profile, _ = StaffProfile.objects.get_or_create(
                user=instance, defaults={"staff_number": staff_number}
            )
            if staff_number is not None:
                profile.staff_number = staff_number
            if department_id is not None:
                profile.department_id = department_id
            if job_title is not None:
                profile.job_title = job_title
            profile.save()

        return instance


class AdminPasswordResetSerializer(serializers.Serializer):
    password = serializers.CharField(
        write_only=True, min_length=8, style={"input_type": "password"}
    )
    password_confirmation = serializers.CharField(
        write_only=True, min_length=8, style={"input_type": "password"}
    )

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirmation"]:
            raise serializers.ValidationError(
                {"password_confirmation": "Passwords do not match."}
            )
        return attrs
