"""
Shared API dependencies and singleton services.
"""

from __future__ import annotations

from typing import Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import get_settings
from core.auth import AuthService
from core.brain import DevSynapseBrain
from core.memory import MemorySystem
from core.monitoring import monitoring_system
from core.opencode_bridge import OpenCodeBridge
from core.plugin_system import plugin_manager

settings = get_settings()
memory_system = MemorySystem()
opencode_bridge = OpenCodeBridge(
    known_projects=memory_system.get_project_lookup(),
    monitoring_system=monitoring_system,
)
devsynapse_brain = DevSynapseBrain(memory_system, opencode_bridge)
auth_service = AuthService(memory_system)
security = HTTPBearer(auto_error=False)


def get_memory_system() -> MemorySystem:
    return memory_system


def get_auth_service() -> AuthService:
    return auth_service


def get_brain() -> DevSynapseBrain:
    return devsynapse_brain


def get_opencode_bridge() -> OpenCodeBridge:
    return opencode_bridge


def get_monitoring_system():
    return monitoring_system


def get_plugin_manager():
    return plugin_manager


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    service: AuthService = Depends(get_auth_service),
) -> Optional[Dict]:
    if credentials is None:
        return None
    return service.verify_access_token(credentials.credentials)


async def require_user(
    user: Optional[Dict] = Depends(get_current_user),
) -> Dict:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(
    user: Dict = Depends(require_user),
) -> Dict:
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissão de administrador necessária",
        )
    return user
