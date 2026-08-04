"""
core/security.py
----------------
Supabase JWT verification helpers.

Supabase handles authentication and password storage. The backend only
verifies the JWT that Supabase issues and extracts the authenticated user's
UUID from the token payload.
"""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings


bearer_scheme = HTTPBearer(auto_error=True)


def verify_supabase_token(token: str) -> dict:
    if not settings.SUPABASE_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase URL is not configured",
        )

    try:
        if not settings.SUPABASE_ANON_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Supabase anon key is not configured",
            )

        request = Request(
            f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": settings.SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )

        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    token = credentials.credentials
    payload = verify_supabase_token(token)
    return payload["id"]