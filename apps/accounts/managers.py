"""
User manager for the custom User model.

Rules (per backend architecture doc §7.1):
- `university_id` and `email` are unique.
- `email` is the login credential (USERNAME_FIELD).
- `university_id` is the institutional identifier (matricule/staff number).
"""

from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _normalize(self, email: str, university_id: str):
        if not email:
            raise ValueError("Email is required.")
        if not university_id:
            raise ValueError("University ID is required.")
        return email.lower().strip(), university_id.strip().upper()

    def create_user(self, email, university_id, password=None, **extra):
        email, university_id = self._normalize(email, university_id)
        user = self.model(email=email, university_id=university_id, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, university_id, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("status", "ACTIVE")

        if extra.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, university_id, password, **extra)
