from .auth import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    LoginUserSerializer,
    ResetPasswordSerializer,
    TokenPairSerializer,
)

from .rbac import (
    AssignRoleSerializer,
    PermissionSerializer,
    RoleDetailSerializer,
    RolePermissionSetSerializer,
    RoleSerializer,
    UserRoleSerializer,
)

from .profile import StaffProfileSerializer, StudentProfileSerializer
from .user import (
    UserCreateSerializer,
    UserMeSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

__all__ = [
    # auth
    "LoginSerializer",
    "LoginUserSerializer",
    "TokenPairSerializer",
    "ChangePasswordSerializer",
    "ForgotPasswordSerializer",
    "ResetPasswordSerializer",
    # user
    "UserSerializer",
    "UserMeSerializer",
    "UserCreateSerializer",
    "UserUpdateSerializer",
    # profile
    "StudentProfileSerializer",
    "StaffProfileSerializer",
    # rbac
    "RoleSerializer",
    "RoleDetailSerializer",
    "PermissionSerializer",
    "RolePermissionSetSerializer",
    "UserRoleSerializer",
    "AssignRoleSerializer",
]
