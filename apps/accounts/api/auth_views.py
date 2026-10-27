"""
Auth endpoints — per backend doc §9.

Views stay thin: validate → call service → envelope response.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.common.responses import error_response, success_response
from apps.accounts.serializers import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    LoginUserSerializer,
    ResetPasswordSerializer,
    UserMeSerializer,
)
from apps.accounts.services import AuthService, PasswordService
from apps.accounts.services.auth_service import AuthError


def _auth_error_response(exc: AuthError):
    return error_response(
        exc.args[0],
        status_code=status.HTTP_400_BAD_REQUEST,
        errors={"code": [exc.code]},
    )


class LoginView(APIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ip = _client_ip(request)
        ua = request.META.get("HTTP_USER_AGENT", "")

        try:
            result = AuthService.login(
                identifier=serializer.validated_data["identifier"],
                password=serializer.validated_data["password"],
                ip_address=ip,
                user_agent=ua,
            )
        except AuthError as exc:
            return _auth_error_response(exc)
        try:
            from apps.analytics.services.event_service import EventService

            EventService.record(
                student=result["user"],
                event_type="LOGIN",
            )
        except Exception:
            pass

        return success_response(
            data={
                "access": result["access"],
                "refresh": result["refresh"],
                "user": LoginUserSerializer(result["user"]).data,
            },
            message="Login successful",
        )


class LogoutView(APIView):
    serializer_class = None
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh") or request.COOKIES.get("refresh_token")
        if refresh:
            AuthService.logout(refresh_token=refresh)
        return success_response(message="Logged out successfully.")


class MeView(APIView):
    serializer_class = UserMeSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(data=UserMeSerializer(request.user).data)


class ChangePasswordView(APIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            PasswordService.change_password(
                user=request.user,
                current_password=serializer.validated_data["current_password"],
                new_password=serializer.validated_data["new_password"],
            )
        except AuthError as exc:
            return _auth_error_response(exc)
        return success_response(message="Password changed successfully.")


class ForgotPasswordView(APIView):
    serializer_class = ForgotPasswordSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PasswordService.initiate_reset(email=serializer.validated_data["email"])
        return success_response(
            message="If an account exists with that email, a reset link has been sent.",
        )


class ResetPasswordView(APIView):
    serializer_class = ResetPasswordSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            PasswordService.confirm_reset(
                uid=serializer.validated_data["uid"],
                token=serializer.validated_data["token"],
                new_password=serializer.validated_data["new_password"],
            )
        except AuthError as exc:
            return _auth_error_response(exc)
        return success_response(message="Password reset successfully.")


class RefreshTokenView(TokenRefreshView):
    permission_classes = [AllowAny]


def _client_ip(request) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
