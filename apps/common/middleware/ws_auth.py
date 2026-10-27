"""
JWT auth middleware for WebSocket connections.

Accepts the JWT from:
  1) `?token=` query string (browser clients — can't set custom headers)
  2) `Authorization: Bearer <jwt>` header (non-browser clients)

Logs every step so rejections are diagnosable.
"""

import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)
User = get_user_model()


@database_sync_to_async
def _get_user(user_id):
    try:
        return User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        logger.warning("WS auth: user_id=%s not found or inactive", user_id)
        return AnonymousUser()
    except Exception:
        logger.exception("WS auth: error looking up user_id=%s", user_id)
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope["user"] = AnonymousUser()

        # Extract token from query string first
        qs_raw = scope.get("query_string", b"").decode()
        token = None
        if qs_raw:
            try:
                qs = parse_qs(qs_raw)
                if "token" in qs and qs["token"]:
                    token = qs["token"][0]
            except Exception:
                logger.exception("WS auth: could not parse query string")

        # Fall back to Authorization header
        if not token:
            for name, value in scope.get("headers", []):
                if name == b"authorization":
                    parts = value.decode().split(None, 1)
                    if len(parts) == 2 and parts[0].lower() == "bearer":
                        token = parts[1].strip()
                    break

        if not token:
            logger.warning(
                "WS auth: no token in query string or header — path=%s",
                scope.get("path"),
            )
            return await super().__call__(scope, receive, send)

        # Decode token
        try:
            access = AccessToken(token)
            user_id = access.get("user_id")
        except (InvalidToken, TokenError) as exc:
            logger.warning(
                "WS auth: invalid token (%s) — path=%s",
                exc.__class__.__name__,
                scope.get("path"),
            )
            return await super().__call__(scope, receive, send)
        except Exception:
            logger.exception("WS auth: unexpected token decode error")
            return await super().__call__(scope, receive, send)

        if not user_id:
            logger.warning("WS auth: token has no user_id claim")
            return await super().__call__(scope, receive, send)

        user = await _get_user(user_id)
        scope["user"] = user

        if user.is_authenticated:
            logger.info(
                "WS auth: authenticated user=%s (%s) path=%s",
                user.university_id,
                user.id,
                scope.get("path"),
            )
        else:
            logger.warning("WS auth: user is anonymous after lookup")

        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
