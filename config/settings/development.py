from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]

# ──────────────────────────────────────────────────────────────────────
# Local-dev overrides — no external services required.
#
# We intentionally replace Redis with in-memory equivalents so a fresh
# clone can run without Docker or a native Redis install.
#
# Set USE_REDIS=1 in .env to switch back to real Redis.
# ──────────────────────────────────────────────────────────────────────
import os

USE_REDIS = os.environ.get("USE_REDIS", "0") == "1"

if not USE_REDIS:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "gu-lms-dev",
        }
    }

    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

    # Celery — run tasks synchronously so nothing needs a broker
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

# ──────────────────────────────────────────────────────────────────────
# Dev-only permissiveness
# ──────────────────────────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True

# Email → console
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INTERNAL_IPS = ["127.0.0.1", "localhost"]

# Disable HTTPS-only CSRF/cookie flags in dev
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
