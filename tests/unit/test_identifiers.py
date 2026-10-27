import pytest

from apps.accounts.models import StudentProfile, StaffProfile
from apps.accounts.utils.identifiers import (
    generate_matricule,
    generate_staff_number,
    generate_university_id,
)


@pytest.mark.django_db
class TestIdentifierGenerators:
    def test_university_id_sequence(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        # Pre-seed three users
        for i in range(3):
            User.objects.create_user(
                email=f"u{i}@x.y",
                university_id=f"GU2026{100 + i:03d}",
                password="x",
                first_name="A",
                last_name="B",
            )
        generated = generate_university_id()
        assert generated.startswith("GU2026")
        assert generated.endswith("103")

    def test_matricule_sequence(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        u = User.objects.create_user(
            email="s@x.y",
            university_id="GU1",
            password="x",
            first_name="A",
            last_name="B",
        )
        StudentProfile.objects.create(
            user=u,
            matricule_number="GU-2026-000999",
            admission_year=2026,
            current_level=100,
        )
        m = generate_matricule()
        assert m.startswith("GU-2026-")
        assert m.endswith("001000")

    def test_staff_number_sequence(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        u = User.objects.create_user(
            email="t@x.y",
            university_id="GU2",
            password="x",
            first_name="A",
            last_name="B",
        )
        StaffProfile.objects.create(user=u, staff_number="GU-STAFF-0009")
        s = generate_staff_number()
        assert s == "GU-STAFF-0010"
