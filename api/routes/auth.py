"""
Authentication routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import get_auth_service, get_current_user
from api.models import AuthRequest, AuthResponse, TokenVerifyResponse
from core.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthResponse)
async def login(
    request: AuthRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    user = auth_service.authenticate_user(request.username, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos",
        )

    token = auth_service.create_access_token(user)
    return AuthResponse(
        access_token=token,
        token=token,
        user=user,
    )


@router.get("/verify", response_model=TokenVerifyResponse)
async def verify_token(user=Depends(get_current_user)):
    if user is None:
        return TokenVerifyResponse(valid=False)
    return TokenVerifyResponse(valid=True, user=user)
