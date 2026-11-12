from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .models import User


@database_sync_to_async
def get_user_from_token(token):
    if not token:
        return AnonymousUser()
    try:
        access = AccessToken(token)  # checks the signature and the expiry time
        return User.objects.get(id=access["user_id"])
    except (TokenError, User.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    Browsers cannot send headers on a WebSocket connection,
    so the JWT access token comes in the URL: /ws/documents/?token=<access>
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        params = parse_qs(scope["query_string"].decode())
        token = params.get("token", [None])[0]
        scope["user"] = await get_user_from_token(token)
        return await self.inner(scope, receive, send)
