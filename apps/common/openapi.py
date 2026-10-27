"""OpenAPI schema post-processing hooks.

The implementation lives in :mod:`apps.common.apenapi` for backwards
compatibility with the existing module name. This correctly named module is
the import path configured in ``SPECTACULAR_SETTINGS``.
"""

from .apenapi import camelize_schema

__all__ = ["camelize_schema"]
