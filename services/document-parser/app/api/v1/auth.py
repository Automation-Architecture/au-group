import logging
import secrets

from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.core.logging import log_event
from app.core.tokens import create_access_token
from app.models.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    settings = get_settings()
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT authentication is not configured",
        )
    if not settings.auth_username or not settings.auth_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login credentials are not configured",
        )

    username_ok = secrets.compare_digest(body.username, settings.auth_username)
    password_ok = secrets.compare_digest(body.password, settings.auth_password)
    if not username_ok or not password_ok:
        log_event(logger, "login_failed", username=body.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, expires_in = create_access_token(subject=body.username)
    log_event(logger, "login_success", username=body.username)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
    )
