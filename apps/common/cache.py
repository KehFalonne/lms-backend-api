"""
Thin caching helpers (backend doc §33).

Per the doc, Redis is used for cache/queue, never as the source of truth.
These wrappers ensure a single, consistent key namespace.
"""

from django.core.cache import cache


class CacheKeys:
    USER_PERMISSIONS = "user:{user_id}:permissions"
    COURSE_SUMMARY = "course:{course_id}:summary"
    COURSE_OFFERING_SUMMARY = "course-offering:{offering_id}:summary"
    DASHBOARD_STUDENT = "dashboard:student:{user_id}"
    DASHBOARD_LECTURER = "dashboard:lecturer:{user_id}"
    DASHBOARD_ADMIN = "dashboard:admin"


def get_cached(key: str, default=None):
    return cache.get(key, default)


def set_cached(key: str, value, ttl: int = 300) -> None:
    cache.set(key, value, ttl)


def invalidate(key: str) -> None:
    cache.delete(key)
