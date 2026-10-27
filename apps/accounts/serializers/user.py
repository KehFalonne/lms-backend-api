from rest_framework import serializers

from apps.accounts.models import User, UserStatus
from .profile import StaffProfileSerializer, StudentProfileSerializer


class UserSerializer(serializers.ModelSerializer):
    """List / detail serializer — no nested profiles."""

    full_name = serializers.SerializerMethodField()

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
            "student_profile",
            "staff_profile",
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

    def create(self, validated_data):
        # Pop profile side-channel data
        matricule = validated_data.pop("matricule_number", "") or None
        staff_number = validated_data.pop("staff_number", "") or None
        current_level = validated_data.pop("current_level", 100)
        admission_year = validated_data.pop("admission_year", None)
        programme_id = validated_data.pop("programme_id", None)
        department_id = validated_data.pop("department_id", None)
        job_title = validated_data.pop("job_title", "")

        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)

        # Attach profile if either side-channel is provided
        if matricule:
            from apps.accounts.models import StudentProfile

            StudentProfile.objects.create(
                user=user,
                matricule_number=matricule,
                programme_id=programme_id,
                current_level=current_level or 100,
                admission_year=admission_year or user.created_at.year,
            )
        elif staff_number:
            from apps.accounts.models import StaffProfile

            StaffProfile.objects.create(
                user=user,
                staff_number=staff_number,
                department_id=department_id,
                job_title=job_title,
            )

        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "phone",
            "avatar",
            "status",
        ]
