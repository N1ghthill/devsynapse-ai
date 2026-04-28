"""Runtime bootstrap routes for first-run setup."""

from fastapi import APIRouter, Depends, HTTPException, status

from api.dependencies import (
    get_auth_service,
    get_brain,
    get_current_user,
    get_memory_system,
    get_opencode_bridge,
)
from api.models import (
    BootstrapAdminRequest,
    BootstrapCompleteResponse,
    BootstrapStatusResponse,
)
from core.auth import AuthService
from core.bootstrap import apply_bootstrap, get_bootstrap_status
from core.brain import DevSynapseBrain
from core.memory import MemorySystem
from core.opencode_bridge import OpenCodeBridge

router = APIRouter(prefix="/bootstrap", tags=["bootstrap"])


@router.get("/status", response_model=BootstrapStatusResponse)
async def bootstrap_status(
    auth_service: AuthService = Depends(get_auth_service),
):
    return BootstrapStatusResponse(**get_bootstrap_status(auth_service))


@router.post("/complete", response_model=BootstrapCompleteResponse)
async def complete_bootstrap(
    request: BootstrapAdminRequest,
    user=Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    memory_system: MemorySystem = Depends(get_memory_system),
    bridge: OpenCodeBridge = Depends(get_opencode_bridge),
    brain: DevSynapseBrain = Depends(get_brain),
):
    admin_password_required = auth_service.admin_requires_password_setup()
    if admin_password_required and not request.admin_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin password is required for first-run setup",
        )
    if not admin_password_required and (user is None or user.get("role") != "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin authentication is required to update runtime setup",
        )

    try:
        result = apply_bootstrap(
            auth_service=auth_service,
            memory_system=memory_system,
            bridge=bridge,
            deepseek_api_key=request.deepseek_api_key,
            repos_root=request.repos_root,
            workspace_root=request.workspace_root,
            admin_password=request.admin_password if admin_password_required else None,
            register_discovered_projects=request.register_discovered_projects,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    brain.api_key = result["deepseek_api_key"]

    access_token = None
    token_user = user
    if admin_password_required:
        token_user = result["user"]
        access_token = auth_service.create_access_token(token_user)

    return BootstrapCompleteResponse(
        access_token=access_token,
        token=access_token,
        user=token_user,
        status=BootstrapStatusResponse(**result["status"]),
        registered_projects=result["registered_projects"],
    )
