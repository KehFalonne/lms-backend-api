"""
Auth + user endpoints.

Auth (per backend doc §9):
    POST /api/v1/auth/login/
    POST /api/v1/auth/token/refresh/
    POST /api/v1/auth/logout/
    GET  /api/v1/auth/me/
    POST /api/v1/auth/change-password/
    POST /api/v1/auth/forgot-password/
    POST /api/v1/auth/reset-password/

Users (per backend doc §15) are registered on the parent router.
"""

from django.urls import path

from apps.accounts.api.auth_views import (
    ChangePasswordView,
    ForgotPasswordView,
    LoginView,
    LogoutView,
    MeView,
    RefreshTokenView,
    ResetPasswordView,
)

app_name = "accounts"

auth_urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", RefreshTokenView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
]

urlpatterns = auth_urlpatterns
