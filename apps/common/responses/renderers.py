"""
Standard renderer for GU-LMS.

Two jobs:
  1. Wrap bare payloads in the standard envelope (backend doc §13).
  2. Convert snake_case Python keys → camelCase JSON (per all doc examples).

Errors bypass wrapping because the global exception handler already
envelopes them (§14).
"""

from collections import OrderedDict

from djangorestframework_camel_case.render import CamelCaseJSONRenderer


class StandardJSONRenderer(CamelCaseJSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get("response")

        # Errors — already enveloped, don't touch.
        if response is not None and getattr(response, "status_code", 200) >= 400:
            return super().render(data, accepted_media_type, renderer_context)

        # Already enveloped.
        if isinstance(data, dict) and "success" in data:
            return super().render(data, accepted_media_type, renderer_context)

        # Bare payload → wrap.
        if data is None:
            wrapped = OrderedDict(
                [
                    ("success", True),
                    ("message", "Success"),
                    ("data", {}),
                    ("meta", None),
                ]
            )
        else:
            wrapped = OrderedDict(
                [
                    ("success", True),
                    ("message", "Success"),
                    ("data", data),
                    ("meta", None),
                ]
            )

        return super().render(wrapped, accepted_media_type, renderer_context)
