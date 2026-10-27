import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    def test_create_user_with_email_and_university_id(self):
        user = User.objects.create_user(
            email="Test@Example.com",
            university_id="gu2026001",
            password="secret-pass-123",
            first_name="Test",
            last_name="User",
        )
        assert user.email == "test@example.com"
        assert user.university_id == "GU2026001"  # uppercased
        assert user.check_password("secret-pass-123")
        assert user.status == "PENDING"
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_user_requires_email(self):
        with pytest.raises(ValueError, match="Email is required"):
            User.objects.create_user(email="", university_id="GU1", password="x")

    def test_create_user_requires_university_id(self):
        with pytest.raises(ValueError, match="University ID is required"):
            User.objects.create_user(email="a@b.c", university_id="", password="x")

    def test_create_superuser_sets_flags(self):
        admin = User.objects.create_superuser(
            email="root@example.com",
            university_id="GU0001",
            password="admin-pass-123",
            first_name="Root",
            last_name="User",
        )
        assert admin.is_staff
        assert admin.is_superuser
        assert admin.status == "ACTIVE"

    def test_full_name_joins_parts(self):
        user = User(
            email="x@y.z",
            university_id="GU1",
            first_name="A",
            middle_name="B",
            last_name="C",
        )
        assert user.get_full_name() == "A B C"

    def test_uuid_primary_key(self):
        user = User.objects.create_user(
            email="u@example.com",
            university_id="GU2",
            password="x",
            first_name="U",
            last_name="X",
        )
        assert user.pk is not None
        assert len(str(user.pk)) == 36  # UUID string


@pytest.mark.django_db
class TestUserUniqueness:
    def test_email_unique(self, user):
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            User.objects.create_user(
                email=user.email,
                university_id="GU9999",
                password="x",
                first_name="A",
                last_name="B",
            )

    def test_university_id_unique(self, user):
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            User.objects.create_user(
                email="other@example.com",
                university_id=user.university_id,
                password="x",
                first_name="A",
                last_name="B",
            )
