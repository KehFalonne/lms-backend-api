"""
Seeds the RBAC catalogue — roles + permissions — and wires them together.

Idempotent: safe to run repeatedly; only creates what's missing.

Usage:
    python manage.py seed_rbac
    python manage.py seed_rbac --reset-permissions   # re-apply role->permission matrix
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Permission, Role, RolePermission

# ──────────────────────────────────────────────────────────────────────
# Permissions — one entry per action that a view actually checks
# ──────────────────────────────────────────────────────────────────────
PERMISSIONS = [
    # users
    ("users.view", "View users", "users"),
    ("users.create", "Create users", "users"),
    ("users.update", "Update users", "users"),
    ("users.delete", "Delete users", "users"),
    ("users.activate", "Activate users", "users"),
    ("users.deactivate", "Deactivate users", "users"),
    ("users.assign_role", "Assign roles to users", "users"),
    # roles
    ("roles.view", "View roles", "roles"),
    ("roles.create", "Create roles", "roles"),
    ("roles.update", "Update roles", "roles"),
    ("roles.delete", "Delete roles", "roles"),
    ("roles.manage_permissions", "Manage role permissions", "roles"),
    # academic structure
    ("academics.view", "View academic structure", "academics"),
    ("academics.manage", "Manage academic structure", "academics"),
    # courses
    ("courses.view", "View courses", "courses"),
    ("courses.create", "Create courses", "courses"),
    ("courses.update", "Update courses", "courses"),
    ("courses.delete", "Delete courses", "courses"),
    ("courses.publish", "Publish courses", "courses"),
    # enrollments
    ("enrollments.view", "View enrollments", "enrollments"),
    ("enrollments.manage", "Manage enrollments", "enrollments"),
    # content
    ("content.view", "View content", "content"),
    ("content.manage", "Manage content", "content"),
    # assignments
    ("assignments.view", "View assignments", "assignments"),
    ("assignments.create", "Create assignments", "assignments"),
    ("assignments.update", "Update assignments", "assignments"),
    ("assignments.delete", "Delete assignments", "assignments"),
    ("assignments.grade", "Grade assignments", "assignments"),
    # assessments
    ("assessments.view", "View assessments", "assessments"),
    ("assessments.create", "Create assessments", "assessments"),
    ("assessments.update", "Update assessments", "assessments"),
    ("assessments.delete", "Delete assessments", "assessments"),
    ("assessments.publish", "Publish assessments", "assessments"),
    # question banks
    ("questions.view", "View question banks", "questions"),
    ("questions.manage", "Manage question banks", "questions"),
    # grades
    ("grades.view", "View grades", "grades"),
    ("grades.manage", "Manage grades", "grades"),
    ("grades.publish", "Publish grades", "grades"),
    # announcements & discussions
    ("announcements.view", "View announcements", "announcements"),
    ("announcements.manage", "Manage announcements", "announcements"),
    ("discussions.view", "View discussions", "discussions"),
    ("discussions.moderate", "Moderate discussions", "discussions"),
    # analytics & audit
    ("analytics.view", "View analytics", "analytics"),
    ("audit.view", "View audit logs", "audit"),
]

# ──────────────────────────────────────────────────────────────────────
# Roles
# ──────────────────────────────────────────────────────────────────────
ROLES = [
    ("SUPER_ADMIN", "Super Administrator", True),
    ("UNIVERSITY_ADMIN", "University Administrator", True),
    ("FACULTY_ADMIN", "Faculty Administrator", True),
    ("DEAN", "Dean", True),
    ("DEPARTMENT_ADMIN", "Department Administrator", True),
    ("HOD", "Head of Department", True),
    ("LECTURER", "Lecturer", True),
    ("TEACHING_ASSISTANT", "Teaching Assistant", True),
    ("STUDENT", "Student", True),
    ("PARENT_GUARDIAN", "Parent / Guardian", True),
]

# ──────────────────────────────────────────────────────────────────────
# Role → permission matrix
# ──────────────────────────────────────────────────────────────────────
ALL_CODES = [p[0] for p in PERMISSIONS]

ROLE_PERMISSIONS = {
    "SUPER_ADMIN": ["*"],
    "UNIVERSITY_ADMIN": ["*"],
    "FACULTY_ADMIN": [
        "users.view",
        "users.create",
        "users.update",
        "users.deactivate",
        "roles.view",
        "academics.view",
        "academics.manage",
        "courses.view",
        "courses.create",
        "courses.update",
        "courses.publish",
        "enrollments.view",
        "enrollments.manage",
        "content.view",
        "content.manage",
        "assignments.view",
        "assignments.create",
        "assignments.update",
        "assignments.delete",
        "assignments.grade",
        "assessments.view",
        "assessments.create",
        "assessments.update",
        "assessments.delete",
        "assessments.publish",
        "questions.view",
        "questions.manage",
        "grades.view",
        "grades.manage",
        "grades.publish",
        "announcements.view",
        "announcements.manage",
        "discussions.view",
        "discussions.moderate",
        "analytics.view",
    ],
    "DEAN": [
        "academics.view",
        "courses.view",
        "courses.publish",
        "enrollments.view",
        "analytics.view",
        "audit.view",
    ],
    "DEPARTMENT_ADMIN": [
        "users.view",
        "users.create",
        "users.update",
        "academics.view",
        "courses.view",
        "courses.create",
        "courses.update",
        "enrollments.view",
        "enrollments.manage",
        "assignments.view",
        "assessments.view",
        "grades.view",
        "analytics.view",
    ],
    "HOD": [
        "academics.view",
        "courses.view",
        "courses.create",
        "courses.update",
        "enrollments.view",
        "assignments.view",
        "assignments.update",
        "assessments.view",
        "grades.view",
        "analytics.view",
    ],
    "LECTURER": [
        "courses.view",
        "enrollments.view",
        "content.view",
        "content.manage",
        "assignments.view",
        "assignments.create",
        "assignments.update",
        "assignments.delete",
        "assignments.grade",
        "assessments.view",
        "assessments.create",
        "assessments.update",
        "assessments.delete",
        "assessments.publish",
        "questions.view",
        "questions.manage",
        "grades.view",
        "grades.manage",
        "grades.publish",
        "announcements.view",
        "announcements.manage",
        "discussions.view",
        "discussions.moderate",
        "analytics.view",
    ],
    "TEACHING_ASSISTANT": [
        "courses.view",
        "enrollments.view",
        "content.view",
        "assignments.view",
        "assignments.grade",
        "assessments.view",
        "grades.view",
        "grades.manage",
        "discussions.view",
    ],
    "STUDENT": [
        "courses.view",
        "content.view",
        "assignments.view",
        "assessments.view",
        "grades.view",
        "announcements.view",
        "discussions.view",
    ],
    "PARENT_GUARDIAN": [
        "grades.view",
        "announcements.view",
    ],
}


class Command(BaseCommand):
    help = "Seed RBAC roles, permissions, and the role-permission matrix."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-permissions",
            action="store_true",
            help="Re-apply the role→permission matrix (idempotent).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # 1) Permissions
        created_perms = 0
        for code, name, module in PERMISSIONS:
            _, created = Permission.objects.update_or_create(
                code=code,
                defaults={"name": name, "module": module},
            )
            if created:
                created_perms += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"  ✓ Permissions: {Permission.objects.count()} total ({created_perms} new)"
            )
        )

        # 2) Roles
        created_roles = 0
        for code, name, is_system in ROLES:
            _, created = Role.objects.update_or_create(
                code=code,
                defaults={"name": name, "is_system_role": is_system},
            )
            if created:
                created_roles += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"  ✓ Roles: {Role.objects.count()} total ({created_roles} new)"
            )
        )

        # 3) Role → permission matrix
        permissions_by_code = {p.code: p for p in Permission.objects.all()}
        total_links = 0

        for role_code, perm_codes in ROLE_PERMISSIONS.items():
            role = Role.objects.get(code=role_code)

            # "wildcard" → all permissions
            if perm_codes == ["*"]:
                perm_codes = ALL_CODES

            target_ids = {
                permissions_by_code[c].id
                for c in perm_codes
                if c in permissions_by_code
            }

            # Clear existing, add target
            RolePermission.objects.filter(role=role).exclude(
                permission_id__in=target_ids
            ).delete()

            existing = set(
                RolePermission.objects.filter(role=role).values_list(
                    "permission_id", flat=True
                )
            )
            new_links = [
                RolePermission(role=role, permission_id=pid)
                for pid in target_ids
                if pid not in existing
            ]
            RolePermission.objects.bulk_create(new_links)
            total_links += len(new_links)

        self.stdout.write(
            self.style.SUCCESS(
                f"  ✓ Role-permission links: {RolePermission.objects.count()} total "
                f"({total_links} new)"
            )
        )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("RBAC seed complete."))
