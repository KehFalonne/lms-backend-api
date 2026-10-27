"""
Read-side helpers — keep ORM queries out of views.
"""

from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


def get_user_by_identifier(identifier: str):
    """
    Resolve a user from an identifier that may be:
      • university ID  (GU2026001)
      • matricule      (GU-2026-001234)
      • email          (user@graciousuniversity.edu)
    """
    if not identifier:
        return None
    identifier = identifier.strip()

    q = (
        Q(university_id__iexact=identifier)
        | Q(email__iexact=identifier)
        | Q(student_profile__matricule_number__iexact=identifier)
    )
    return (
        User.objects.select_related("student_profile", "staff_profile")
        .filter(q)
        .first()
    )
