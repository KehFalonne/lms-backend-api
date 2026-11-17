from apps.common.audit_context import reset_audit_context, set_audit_context


class AuditContextMiddleware:
    """Expose the current request to model-level audit signals.

    The actor is resolved lazily by `AuditService.record` from
    `request.user`, so only the request itself is stored here.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tokens = set_audit_context(actor=None, request=request)
        try:
            return self.get_response(request)
        finally:
            reset_audit_context(tokens)
