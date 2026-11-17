from contextvars import ContextVar

_audit_actor = ContextVar("audit_actor", default=None)
_audit_request = ContextVar("audit_request", default=None)


def set_audit_context(*, actor=None, request=None):
    return _audit_actor.set(actor), _audit_request.set(request)


def set_audit_actor(actor):
    return _audit_actor.set(actor)


def reset_audit_context(tokens):
    actor_token, request_token = tokens
    _audit_actor.reset(actor_token)
    _audit_request.reset(request_token)


def reset_audit_actor(token):
    _audit_actor.reset(token)


def get_audit_actor():
    return _audit_actor.get()


def get_audit_request():
    return _audit_request.get()
