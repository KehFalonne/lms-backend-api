"""
Business-identifier generators.

Per the database doc, human-facing IDs follow patterns like:
    University ID:  GU2026001
    Matricule:      GU-2026-001234
"""

from datetime import datetime

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User, StudentProfile, StaffProfile


def _next_sequence(prefix: str, field: str, model) -> int:
    """
    Highest numeric suffix currently in use for the given prefix, +1.
    Uses string length ordering so 001234 sorts after 000999.
    """
    last = (
        model.objects.filter(**{f"{field}__startswith": prefix})
        .order_by(f"-{field}")
        .values_list(field, flat=True)
        .first()
    )
    if not last:
        return 1
    try:
        return int(last[len(prefix) :]) + 1
    except (ValueError, TypeError):
        return 1


def generate_university_id() -> str:
    """e.g. GU2026001, GU2026002, …"""
    year = timezone.now().year
    prefix = f"GU{year}"
    with transaction.atomic():
        seq = _next_sequence(prefix, "university_id", User)
        return f"{prefix}{seq:03d}"


def generate_matricule() -> str:
    """e.g. GU-2026-001234"""
    year = timezone.now().year
    prefix = f"GU-{year}-"
    with transaction.atomic():
        seq = _next_sequence(prefix, "matricule_number", StudentProfile)
        return f"{prefix}{seq:06d}"


def generate_staff_number() -> str:
    """e.g. GU-STAFF-0001"""
    prefix = "GU-STAFF-"
    with transaction.atomic():
        seq = _next_sequence(prefix, "staff_number", StaffProfile)
        return f"{prefix}{seq:04d}"
