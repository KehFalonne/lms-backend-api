"""
Helpers for building responses in the standard GU-LMS envelope.

Success (backend doc §13):
    {"success": true, "message": "...", "data": ..., "meta": null}

Error (backend doc §14):
    {"success": false, "statusCode": 400, "message": "...",
     "errors": {...}, "timestamp": "...", "path": "/api/v1/..."}
"""

from collections import OrderedDict
from datetime import datetime, timezone as dt_timezone

from rest_framework.response import Response


def success_response(data=None, message: str = "Success", meta=None, status: int = 200):
    return Response(
        OrderedDict(
            [
                ("success", True),
                ("message", message),
                ("data", data if data is not None else {}),
                ("meta", meta),
            ]
        ),
        status=status,
    )


def error_response(
    message: str,
    status_code: int = 400,
    errors=None,
    path: str | None = None,
):
    return Response(
        OrderedDict(
            [
                ("success", False),
                ("statusCode", status_code),
                ("message", message),
                ("errors", errors or {}),
                (
                    "timestamp",
                    datetime.now(dt_timezone.utc).isoformat().replace("+00:00", "Z"),
                ),
                ("path", path or ""),
            ]
        ),
        status=status_code,
    )
