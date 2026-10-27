from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class LoginSerializer(serializers.Serializer):
    """
    Login payload — per backend doc §9.

    `identifier` accepts university ID (GU2026001), matricule (GU-2026-001234),
    or email.
    """

    identifier = serializers.CharField(help_text="University ID, matricule, or email.")
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class LoginUserSerializer(serializers.ModelSerializer):
    """Minimal user object embedded in the login response."""

    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "university_id",
            "email",
            "first_name",
            "middle_name",
            "last_name",
            "avatar",
            "roles",
        ]

    def get_roles(self, obj) -> list[str]:
        return obj.get_role_codes()


class TokenPairSerializer(serializers.Serializer):
    """The `data` block of the login response."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = LoginUserSerializer()


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        write_only=True, min_length=8, style={"input_type": "password"}
    )

    def validate_new_password(self, value):
        validate_password(value)
        return value


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True, min_length=8, style={"input_type": "password"}
    )

    def validate_new_password(self, value):
        validate_password(value)
        return value
