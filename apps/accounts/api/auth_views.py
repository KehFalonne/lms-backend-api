"""
Auth endpoints — per backend doc §9.

Views stay thin: validate → call service → envelope response.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.views import APIView

from apps.accounts.models import UserSession
from apps.accounts.services.auth_service import AuthService

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
from apps.files.models import File, FileStatus


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
                "user": LoginUserSerializer(
                    result["user"], context={"request": request}
                ).data,
            },
            message="Login successful",
        )


class LogoutView(APIView):
    serializer_class = None
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh") or request.COOKIES.get("refresh_token")
        if refresh:
            AuthService.logout(refresh_token=refresh, request=request)
        return success_response(message="Logged out successfully.")


class MeView(APIView):
    serializer_class = UserMeSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(
            data=UserMeSerializer(request.user, context={"request": request}).data
        )


class AvatarView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        file_id = request.data.get("fileId") or request.data.get("file_id")
        if not file_id:
            return error_response("fileId is required.", status_code=400)

        avatar = File.objects.filter(
            id=file_id,
            uploaded_by=request.user,
            status=FileStatus.READY,
            mime_type__startswith="image/",
        ).first()
        if not avatar:
            return error_response("A completed image upload is required.", status_code=400)

        request.user.avatar_file = avatar
        request.user.avatar = ""
        request.user.save(update_fields=["avatar_file", "avatar", "updated_at"])
        return success_response(
            data=UserMeSerializer(request.user, context={"request": request}).data
        )


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
                request=request,
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
        PasswordService.initiate_reset(
            email=serializer.validated_data["email"], request=request
        )
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
                request=request,
            )
        except AuthError as exc:
            return _auth_error_response(exc)
        return success_response(message="Password reset successfully.")


class RefreshTokenView(TokenRefreshView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                user_id = token.get("user_id")
                session_id = token.get("session_id")
                user = get_user_model().objects.filter(id=user_id).first()
                if user and hasattr(user, "student_profile"):
                    if not session_id:
                        return error_response(
                            "Session expired or revoked.", status_code=401
                        )
                    session = UserSession.objects.filter(
                        id=session_id,
                        user=user,
                        revoked_at__isnull=True,
                        expires_at__gt=timezone.now(),
                    ).first()
                    if not session:
                        return error_response(
                            "Session expired or revoked.", status_code=401
                        )
            except TokenError:
                pass  # Delegate invalid/blacklisted token handling to SimpleJWT.

        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK and refresh_token:
            try:
                old_token = RefreshToken(refresh_token)
                session_id = old_token.get("session_id")
                user = get_user_model().objects.filter(
                    id=old_token.get("user_id")
                ).first()
                if user and hasattr(user, "student_profile") and session_id:
                    new_refresh = RefreshToken(response.data["refresh"])
                    new_refresh["session_id"] = str(session_id)
                    response.data["refresh"] = str(new_refresh)
                    session = UserSession.objects.filter(
                        id=session_id, user=user, revoked_at__isnull=True
                    ).first()
                    if session:
                        session.refresh_token_hash = AuthService._hash_token(
                            response.data["refresh"]
                        )
                        session.expires_at = datetime.fromtimestamp(
                            new_refresh["exp"], tz=dt_timezone.utc
                        )
                        session.save(update_fields=["refresh_token_hash", "expires_at"])
            except (TokenError, KeyError):
                pass
        return response


def _client_ip(request) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
