"""
Attaches a request ID to every incoming request for tracing.

Exposes `request.id` and echoes it via `X-Request-ID` response header.
"""

import uuid


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = self.get_response(request)
        response["X-Request-ID"] = request.id
        return response
