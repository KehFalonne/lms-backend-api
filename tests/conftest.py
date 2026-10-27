import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        email="student@graciousuniversity.edu",
        university_id="GU2026001",
        password="test-password-1234",
        first_name="John",
        last_name="Doe",
    )


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        email="admin@graciousuniversity.edu",
        university_id="GU0001",
        password="test-password-1234",
        first_name="Super",
        last_name="Admin",
    )
