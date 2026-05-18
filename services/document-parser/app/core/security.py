import secrets
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.tokens import decode_access_token

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def _api_key_matches(provided: str, expected: str) -> bool:
    provided_b = provided.encode("utf-8")
    expected_b = expected.encode("utf-8")
    if len(provided_b) != len(expected_b):
        secrets.compare_digest(provided_b, provided_b)
        return False
    return secrets.compare_digest(provided_b, expected_b)


@dataclass(frozen=True)
class AuthContext:
    method: Literal["api_key", "jwt"]
    subject: str


async def verify_auth(
    api_key: str | None = Security(api_key_header),
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> AuthContext:
    settings = get_settings()

    if api_key:
        if _api_key_matches(api_key, settings.api_key):
            return AuthContext(method="api_key", subject="service")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key",
        )

    if credentials and credentials.scheme.lower() == "bearer" and credentials.credentials:
        payload = decode_access_token(credentials.credentials)
        return AuthContext(method="jwt", subject=str(payload["sub"]))

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid or missing API key",
    )


# Backward-compatible alias for any external imports.
verify_api_key = verify_auth
