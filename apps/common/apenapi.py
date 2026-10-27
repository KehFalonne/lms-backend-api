"""
drf-spectacular postprocessing hooks.

`camelize_schema` rewrites snake_case field names in the generated OpenAPI
schema to camelCase, matching the wire format produced by
`djangorestframework-camel-case`.

This is the officially supported way to align the schema with a camelCase
API — do NOT use the (nonexistent) `CAMELIZE_NAMES` setting.
"""

import re

_CAMEL_BOUNDARY = re.compile(r"_([a-z])")


def _to_camel(name: str) -> str:
    return _CAMEL_BOUNDARY.sub(lambda m: m.group(1).upper(), name)


def camelize_schema(result, generator, request, public):
    """
    Walk the schema and rename every property / required entry /
    parameter name from snake_case to camelCase.
    """

    def camelize_props(schema_obj):
        if not isinstance(schema_obj, dict):
            return
        props = schema_obj.get("properties")
        if isinstance(props, dict):
            schema_obj["properties"] = {_to_camel(k): v for k, v in props.items()}
        required = schema_obj.get("required")
        if isinstance(required, list):
            schema_obj["required"] = [_to_camel(r) for r in required]

    components = result.get("components", {}).get("schemas", {})
    for _name, schema in components.items():
        camelize_props(schema)
        # also handle allOf / oneOf / anyOf wrappers
        for key in ("allOf", "oneOf", "anyOf"):
            for sub in schema.get(key, []) or []:
                camelize_props(sub)

    # Query/path parameters
    for path_item in result.get("paths", {}).values():
        for method in path_item.values():
            if not isinstance(method, dict):
                continue
            for param in method.get("parameters", []) or []:
                if "name" in param:
                    param["name"] = _to_camel(param["name"])

    return result
