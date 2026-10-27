"""
Deterministic seed users for development — per database doc §75.

Usage:
    python manage.py seed_users
    python manage.py seed_users --reset   # wipe and reseed
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import StudentProfile, StaffProfile, UserStatus
from apps.accounts.utils.identifiers import (
    generate_matricule,
    generate_staff_number,
    generate_university_id,
)

User = get_user_model()

SEED = [
    {
        "kind": "admin",
        "email": "admin@graciousuniversity.edu",
        "university_id": "GU0001",
        "password": "Admin1234!",
        "first_name": "Super",
        "last_name": "Admin",
    },
    {
        "kind": "lecturer",
        "email": "lecturer@graciousuniversity.edu",
        "university_id": "GU0002",
        "password": "Lecturer1234!",
        "first_name": "Jane",
        "last_name": "Smith",
        "staff_number": "GU-STAFF-0001",
        "job_title": "Senior Lecturer",
    },
    {
        "kind": "student",
        "email": "student@graciousuniversity.edu",
        "university_id": "GU2026001",
        "password": "Student1234!",
        "first_name": "John",
        "last_name": "Doe",
        "matricule": "GU-2026-001234",
        "current_level": 400,
        "admission_year": 2026,
    },
]


class Command(BaseCommand):
    help = "Seed development users (admin, lecturer, student)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Delete existing seed users first."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            emails = [s["email"] for s in SEED]
            User.objects.filter(email__in=emails).delete()
            self.stdout.write(self.style.WARNING("Existing seed users deleted."))

        for spec in SEED:
            if User.objects.filter(email=spec["email"]).exists():
                self.stdout.write(f"  ↳ {spec['email']} already exists — skipping")
                continue

            kind = spec["kind"]
            user = User.objects.create_user(
                email=spec["email"],
                university_id=spec["university_id"],
                password=spec["password"],
                first_name=spec["first_name"],
                last_name=spec["last_name"],
                status=UserStatus.ACTIVE,
            )

            if kind == "admin":
                user.is_staff = True
                user.is_superuser = True
                user.save(update_fields=["is_staff", "is_superuser"])
            elif kind == "lecturer":
                StaffProfile.objects.create(
                    user=user,
                    staff_number=spec["staff_number"],
                    job_title=spec.get("job_title", ""),
                )
            elif kind == "student":
                StudentProfile.objects.create(
                    user=user,
                    matricule_number=spec["matricule"],
                    current_level=spec["current_level"],
                    admission_year=spec["admission_year"],
                )

            self.stdout.write(self.style.SUCCESS(f"  ✓ Created {kind}: {user.email}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Seed complete. Credentials:"))
        for spec in SEED:
            self.stdout.write(
                f"  {spec['kind']:8}  {spec['email']:42}  {spec['password']}"
            )
