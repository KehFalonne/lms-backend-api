"""
Global DRF exception handler — normalizes every error into the standard
envelope defined in backend architecture doc §14.

Never leaks stack traces in production.
"""

from datetime import datetime, timezone as dt_timezone

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler


def _envelope(status_code, message, errors=None, path=None):
    return {
        "success": False,
        "statusCode": status_code,
        "message": message,
        "errors": errors or {},
        "timestamp": datetime.now(dt_timezone.utc).isoformat().replace("+00:00", "Z"),
        "path": path or "",
    }


def global_exception_handler(exc, context):
    import traceback

    traceback.print_exc()
    request = context.get("request") if context else None
    path = getattr(request, "path", "") if request else ""

    # Let DRF handle its own first (it knows about APIException etc.)
    response = drf_exception_handler(exc, context)

    if response is not None:
        status_code = response.status_code
        errors = (
            response.data
            if isinstance(response.data, dict)
            else {"detail": response.data}
        )
        message = _humanize_message(errors, status_code)
        response.data = _envelope(status_code, message, errors, path)
        return response

    # Non-DRF exceptions → map common Django exceptions
    if isinstance(exc, Http404):
        return _build(404, "Not found.", {}, path)
    if isinstance(exc, DjangoPermissionDenied):
        return _build(
            403, "You do not have permission to perform this action.", {}, path
        )
    if isinstance(exc, DjangoValidationError):
        return _build(
            400, "Validation failed.", {"non_field_errors": exc.messages}, path
        )
    if isinstance(exc, IntegrityError):
        return _build(
            409,
            "Conflict — resource already exists or violates a constraint.",
            {},
            path,
        )

    # Unknown → 500 (never leak internals in production)
    return _build(500, "An unexpected error occurred.", {}, path)


def _build(status_code, message, errors, path):
    from rest_framework.response import Response

    return Response(_envelope(status_code, message, errors, path), status=status_code)


def _humanize_message(errors, status_code: int) -> str:
    if status_code == 400:
        return "Validation failed."
    if status_code == 401:
        return "Authentication required."
    if status_code == 403:
        return "You do not have permission to perform this action."
    if status_code == 404:
        return "Not found."
    if status_code == 405:
        return "Method not allowed."
    if status_code == 409:
        return "Conflict."
    if status_code == 429:
        return "Too many requests."

    # Fall back to detail if present
    if isinstance(errors, dict) and isinstance(errors.get("detail"), str):
        return errors["detail"]
    return "Request failed."
