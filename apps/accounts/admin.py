from django.contrib import admin
from .models import (
    User,
    StudentProfile,
    StaffProfile,
    UserSession,
    Permission,
    Role,
    RolePermission,
    UserRole,
)

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("-created_at",)
    list_display = ("university_id", "email", "get_full_name", "status", "is_staff")
    list_filter = ("status", "is_staff", "is_superuser", "is_active")
    search_fields = ("university_id", "email", "first_name", "last_name")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Identity"),
            {
                "fields": (
                    "university_id",
                    "first_name",
                    "middle_name",
                    "last_name",
                    "phone",
                    "avatar",
                )
            },
        ),
        (
            _("Status"),
            {
                "fields": (
                    "status",
                    "email_verified_at",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "last_login_at",
                )
            },
        ),
        (_("Permissions"), {"fields": ("groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at", "last_login", "last_login_at")

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "university_id",
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                    "status",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = (
        "matricule_number",
        "user",
        "current_level",
        "status",
        "admission_year",
    )
    list_filter = ("status", "current_level", "admission_year")
    search_fields = (
        "matricule_number",
        "user__first_name",
        "user__last_name",
        "user__email",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    autocomplete_fields = ("user",)


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ("staff_number", "user", "job_title")
    search_fields = (
        "staff_number",
        "user__first_name",
        "user__last_name",
        "user__email",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    autocomplete_fields = ("user",)


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "ip_address",
        "expires_at",
        "revoked_at",
        "created_at",
    )
    list_filter = ("revoked_at",)
    search_fields = ("user__university_id", "user__email", "ip_address")
    readonly_fields = (
        "id",
        "refresh_token_hash",
        "ip_address",
        "user_agent",
        "expires_at",
        "revoked_at",
        "created_at",
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_system_role", "created_at")
    list_filter = ("is_system_role",)
    search_fields = ("code", "name", "description")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("code",)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "module")
    list_filter = ("module",)
    search_fields = ("code", "name")
    readonly_fields = ("id", "created_at")
    ordering = ("module", "code")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission", "created_at")
    list_filter = ("role__code", "permission__module")
    search_fields = ("role__code", "permission__code")
    readonly_fields = ("id", "created_at")
    autocomplete_fields = ("role", "permission")


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "role",
        "scope_type",
        "faculty_id",
        "department_id",
        "course_offering_id",
        "assigned_at",
    )
    list_filter = ("scope_type", "role__code")
    search_fields = ("user__university_id", "user__email", "role__code")
    readonly_fields = ("id", "assigned_at")
    autocomplete_fields = ("user", "role", "assigned_by")


admin.site.site_header = "GU-LMS Administration"
admin.site.site_title = "GU-LMS Admin"
admin.site.index_title = "Gracious University Learning Management System"
