"""
Test settings — no external services required.
"""

from .base import *  # noqa

DEBUG = False

# ──────────────────────────────────────────────────────────────────────
# No Redis in tests — in-memory cache, channel layer, throttling off
# ──────────────────────────────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "gu-lms-tests",
    }
}

CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# Disable DRF throttling entirely for tests (uses cache, causes flakiness)
# REST_FRAMEWORK = {**REST_FRAMEWORK}  # noqa: F405
# REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
# REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {}

# Keep throttle classes enabled (they're referenced explicitly by LoginView
# and ForgotPasswordView), but set rates so high tests never hit them.
REST_FRAMEWORK = {**REST_FRAMEWORK}  # noqa: F405
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "999999/hour",
    "user": "999999/hour",
    "login": "999999/min",
    "password_reset": "999999/hour",
}

# ──────────────────────────────────────────────────────────────────────
# Fast password hashing
# ──────────────────────────────────────────────────────────────────────
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# ──────────────────────────────────────────────────────────────────────
# Run Celery tasks inline — no broker needed
# ──────────────────────────────────────────────────────────────────────
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
