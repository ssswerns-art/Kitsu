from fastapi import APIRouter, Depends, Request, status

from ..dependencies import get_current_user_optional, get_refresh_token_port, get_user_port
from ..models.user import User
from ..schemas.auth import (
    LogoutRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
)
from ..use_cases.auth.login_user import login_user
from ..use_cases.auth.logout_user import logout_user
from ..use_cases.auth.refresh_session import refresh_session
from ..use_cases.auth.register_user import register_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    client_host = request.client.host if request.client else None
    return client_host or "unknown-ip"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegister,
    user_port=Depends(get_user_port),
    token_port=Depends(get_refresh_token_port),
) -> TokenResponse:
    tokens = await register_user(user_port, token_port, payload.email, payload.password)
    return TokenResponse(
        access_token=tokens.access_token, refresh_token=tokens.refresh_token
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLogin,
    request: Request,
    user_port=Depends(get_user_port),
    token_port=Depends(get_refresh_token_port),
) -> TokenResponse:
    tokens = await login_user(
        user_port, token_port, payload.email, payload.password, client_ip=_client_ip(request)
    )
    return TokenResponse(
        access_token=tokens.access_token, refresh_token=tokens.refresh_token
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    request: Request,
    token_port=Depends(get_refresh_token_port),
) -> TokenResponse:
    tokens = await refresh_session(
        token_port, payload.refresh_token, client_ip=_client_ip(request)
    )
    return TokenResponse(
        access_token=tokens.access_token, refresh_token=tokens.refresh_token
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    token_port=Depends(get_refresh_token_port),
    user: User | None = Depends(get_current_user_optional),
) -> None:
    await logout_user(
        token_port, payload.refresh_token, user_id=user.id if user else None
    )
