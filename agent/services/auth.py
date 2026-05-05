"""FBKit — Authentication helpers for REST and WebSocket endpoints."""
import secrets
from fastapi import Header, HTTPException, status

from agent.config import API_AUTH_ENABLED, API_KEY


def _is_valid_api_key(value: str | None) -> bool:
    if not API_AUTH_ENABLED:
        return True
    if not value:
        return False
    return secrets.compare_digest(value, API_KEY)


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    """Require API key via X-API-Key or Authorization: Bearer <key>."""
    if not API_AUTH_ENABLED:
        return

    candidate = x_api_key
    if not candidate and authorization and authorization.lower().startswith("bearer "):
        candidate = authorization[7:].strip()

    if not _is_valid_api_key(candidate):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
