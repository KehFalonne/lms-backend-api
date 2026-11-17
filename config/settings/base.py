"""
Base settings — shared by all environments.

Environment selection is done via DJANGO_SETTINGS_MODULE:
    config.settings.development
    config.settings.production
    config.settings.testing
"""

from datetime import timedelta
from pathlib import Path

import environ
import os

# ──────────────────────────────────────────────────────────────────────
# Paths & Environment
# ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    JWT_ACCESS_TOKEN_LIFETIME_MINUTES=(int, 15),
    JWT_REFRESH_TOKEN_LIFETIME_DAYS=(int, 7),
)

# Load .env from project root if it exists
environ.Env.read_env(BASE_DIR / ".env")

# ──────────────────────────────────────────────────────────────────────
# Core
# ──────────────────────────────────────────────────────────────────────
SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-dev-key-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTITUTION_NAME = env("INSTITUTION_NAME", default="Gracious University")
INSTITUTION_CODE = env("INSTITUTION_CODE", default="GU")

# ──────────────────────────────────────────────────────────────────────
# Applications
# ──────────────────────────────────────────────────────────────────────
DJANGO_APPS = [
    "daphne",  # must precede staticfiles
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "channels",
    "storages",
    "django_celery_results",
]

LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.university",
    "apps.academics",
    "apps.courses",
    "apps.content",
    "apps.files",
    "apps.announcements",
    "apps.discussions",
    "apps.notifications",
    "apps.assignments",
    "apps.assessments",
    "apps.grading",
    "apps.analytics",
    "apps.audit",
    "apps.calendar",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ──────────────────────────────────────────────────────────────────────
# Middleware (order matters — per request lifecycle in backend doc)
# ──────────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.audit.middleware.AuditContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.common.middleware.request_id.RequestIDMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ──────────────────────────────────────────────────────────────────────
# Database (PostgreSQL — per backend architecture doc, section 2)
# ──────────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB"),
        "USER": os.getenv("POSTGRES_USER"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}
# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": BASE_DIR / "db.sqlite3",
#     }
# }
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DATABASES["default"]["CONN_MAX_AGE"] = 60

# ──────────────────────────────────────────────────────────────────────
# Auth (custom User — must be set before any migration, per doc §7.1)
# ──────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ──────────────────────────────────────────────────────────────────────
# i18n / tz (per backend architecture doc, section 43)
# ──────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("INSTITUTION_TIMEZONE", default="Africa/Douala")
USE_I18N = True
USE_TZ = True

# ──────────────────────────────────────────────────────────────────────
# Static & Media
# ──────────────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ──────────────────────────────────────────────────────────────────────
# Django REST Framework (per backend architecture doc, sections 3 & 13–14)
# ──────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.SessionJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.page_number.StandardPageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    # -- camelCase in / camelCase out (per doc examples) --
    "DEFAULT_RENDERER_CLASSES": (
        "apps.common.responses.renderers.StandardJSONRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "djangorestframework_camel_case.parser.CamelCaseJSONParser",
        "djangorestframework_camel_case.parser.CamelCaseFormParser",
        "djangorestframework_camel_case.parser.CamelCaseMultiPartParser",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.handlers.global_exception_handler",
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%SZ",
    # ── Rate limiting (per request lifecycle doc §6) ──
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/hour",
        "user": "2000/hour",
        "login": "10/min",
        "password_reset": "5/hour",
    },
}

# ──────────────────────────────────────────────────────────────────────
# JWT (per backend architecture doc, section 8)
# ──────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env("JWT_ACCESS_TOKEN_LIFETIME_MINUTES")
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env("JWT_REFRESH_TOKEN_LIFETIME_DAYS")),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
}

# ──────────────────────────────────────────────────────────────────────
# CORS (per backend architecture doc, section 42)
# ──────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# ──────────────────────────────────────────────────────────────────────
# OpenAPI / drf-spectacular (per backend architecture doc, section 40)
# ──────────────────────────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "GU-LMS API",
    "DESCRIPTION": (
        "Gracious University Learning Management System — REST API.\n\n"
        "All endpoints are versioned under `/api/v1/`."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "COMPONENT_SPLIT_REQUEST": False,
    "SORT_OPERATIONS": False,
    "CAMELIZE_NAMES": True,
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
        "displayOperationId": False,
    },
    "SECURITY": [{"jwtAuth": []}],
    "POSTPROCESSING_HOOKS": [
        "apps.common.openapi.camelize_schema",
    ],
}


# ──────────────────────────────────────────────────────────────────────
# Storage Configuration
# Supports LOCAL, R2, S3 and MINIO
# ──────────────────────────────────────────────────────────────────────

STORAGE_PROVIDER = env("STORAGE_PROVIDER", default="LOCAL").upper()

AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="")
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default="")

SUPPORTED_STORAGE_PROVIDERS = {"LOCAL", "R2", "S3", "MINIO"}

if STORAGE_PROVIDER not in SUPPORTED_STORAGE_PROVIDERS:
    raise ValueError(f"Unsupported STORAGE_PROVIDER: {STORAGE_PROVIDER}")

# Default: local filesystem storage
if STORAGE_PROVIDER == "LOCAL":

    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

# Cloud storage: R2, Amazon S3 or MinIO
else:

    if not AWS_ACCESS_KEY_ID:
        raise ValueError("AWS_ACCESS_KEY_ID is required.")

    if not AWS_SECRET_ACCESS_KEY:
        raise ValueError("AWS_SECRET_ACCESS_KEY is required.")

    if not AWS_STORAGE_BUCKET_NAME:
        raise ValueError("AWS_STORAGE_BUCKET_NAME is required.")

    if not AWS_S3_REGION_NAME:
        raise ValueError("AWS_S3_REGION_NAME is required.")

    if STORAGE_PROVIDER in {"R2", "MINIO"} and not AWS_S3_ENDPOINT_URL:
        raise ValueError(f"AWS_S3_ENDPOINT_URL is required for {STORAGE_PROVIDER}.")

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "access_key": AWS_ACCESS_KEY_ID,
                "secret_key": AWS_SECRET_ACCESS_KEY,
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "region_name": AWS_S3_REGION_NAME,
                "endpoint_url": AWS_S3_ENDPOINT_URL or None,
                "signature_version": "s3v4",
                "default_acl": None,
                "file_overwrite": False,
                "querystring_auth": True,
                "querystring_expire": 300,
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }


# ──────────────────────────────────────────────────────────────────────
# Redis (per backend architecture doc, section 33)
# ──────────────────────────────────────────────────────────────────────
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "gu_lms",
        "TIMEOUT": 300,
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# ──────────────────────────────────────────────────────────────────────
# Celery (per backend architecture doc, section 34)
# ──────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/2")
CELERY_RESULT_EXTENDED = True
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_TIME_LIMIT = 600
CELERY_TASK_SOFT_TIME_LIMIT = 540
CELERY_TASK_DEFAULT_RETRY_DELAY = 30
CELERY_TASK_MAX_RETRIES = 3

# ──────────────────────────────────────────────────────────────────────
# Email
# ──────────────────────────────────────────────────────────────────────
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@graciousuniversity.edu")
# Frontend URL for building links in emails
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")
# ──────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
