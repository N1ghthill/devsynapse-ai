"""Administrative routes for user and permission management."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_memory_system, get_opencode_bridge, require_admin
from api.models import (
    AdminAuditLogsResponse,
    AdminProjectListResponse,
    AdminUserPermissionsUpdateRequest,
    AdminUsersResponse,
    AdminUserSummary,
    ProjectCreateRequest,
    ProjectResponse,
)
from core.memory import MemorySystem
from core.opencode_bridge import OpenCodeBridge

router = APIRouter(prefix="/admin", tags=["admin"])


def _project_mutation_scope(memory_system: MemorySystem, username: str, role: str) -> list[str]:
    if role == "admin":
        return memory_system.list_project_names()
    return memory_system.get_project_permissions(username)


def _project_response(project: dict) -> ProjectResponse:
    return ProjectResponse(
        name=project["name"],
        path=project["path"],
        type=project["type"],
        priority=project["priority"],
        last_accessed=project["last_accessed"],
        access_count=int(project["access_count"] or 0),
    )


def _path_is_allowed(path: Path, allowed_directories: list[Path]) -> bool:
    for allowed_dir in allowed_directories:
        try:
            if path.is_relative_to(allowed_dir.resolve()):
                return True
        except ValueError:
            continue
    return False


@router.get("/users", response_model=AdminUsersResponse)
async def list_users(
    admin=Depends(require_admin),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del admin
    conn = memory_system.get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT username, role, is_active
        FROM users
        ORDER BY username
        """
    )
    rows = cursor.fetchall()
    conn.close()

    users = [
        AdminUserSummary(
            username=row["username"],
            role=row["role"],
            is_active=bool(row["is_active"]),
            project_mutation_allowlist=_project_mutation_scope(
                memory_system,
                row["username"],
                row["role"],
            ),
        )
        for row in rows
    ]
    return AdminUsersResponse(users=users)


@router.get("/audit-logs", response_model=AdminAuditLogsResponse)
async def list_audit_logs(
    admin=Depends(require_admin),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del admin
    return AdminAuditLogsResponse(logs=memory_system.get_admin_audit_logs())


@router.get("/projects", response_model=AdminProjectListResponse)
async def list_admin_projects(
    admin=Depends(require_admin),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del admin
    projects = [_project_response(project) for project in memory_system.list_projects()]
    return AdminProjectListResponse(projects=projects, count=len(projects))


@router.put("/users/{username}/permissions", response_model=AdminUserSummary)
async def update_user_permissions(
    username: str,
    payload: AdminUserPermissionsUpdateRequest,
    admin=Depends(require_admin),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    user = memory_system.get_user(username)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if user["role"] == "admin":
        raise HTTPException(
            status_code=400,
            detail="Administradores têm acesso global aos projetos e não usam allowlist",
        )

    previous_allowlist = memory_system.get_project_permissions(username)
    next_allowlist = sorted(set(payload.project_mutation_allowlist))

    memory_system.replace_project_permissions(
        username,
        next_allowlist,
    )
    memory_system.log_admin_action(
        actor_username=admin["username"],
        action="update_project_permissions",
        target_username=username,
        details={
            "previous_allowlist": previous_allowlist,
            "project_mutation_allowlist": next_allowlist,
        },
    )

    updated_user = memory_system.get_user(username)
    return AdminUserSummary(
        username=updated_user["username"],
        role=updated_user["role"],
        is_active=updated_user["is_active"],
        project_mutation_allowlist=_project_mutation_scope(
            memory_system,
            updated_user["username"],
            updated_user["role"],
        ),
    )


@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    payload: ProjectCreateRequest,
    admin=Depends(require_admin),
    memory_system: MemorySystem = Depends(get_memory_system),
    bridge: OpenCodeBridge = Depends(get_opencode_bridge),
):
    project_name = payload.name.strip()
    if not project_name:
        raise HTTPException(status_code=400, detail="Nome do projeto é obrigatório")

    project_path = Path(payload.path).expanduser().resolve()
    if not project_path.exists() or not project_path.is_dir():
        raise HTTPException(status_code=400, detail="Caminho do projeto deve ser um diretório existente")
    if not _path_is_allowed(project_path, bridge.allowed_directories):
        raise HTTPException(
            status_code=400,
            detail="Caminho do projeto deve estar dentro dos diretórios permitidos",
        )
    if memory_system.get_project(project_name) is not None:
        raise HTTPException(status_code=409, detail="Projeto já registrado")

    project_type = (payload.type or "").strip() or "project"
    priority = (payload.priority or "").strip() or "medium"
    memory_system.add_project(project_name, str(project_path), project_type, priority, replace=False)
    bridge.register_project(project_name, str(project_path), project_type, priority)
    memory_system.log_admin_action(
        actor_username=admin["username"],
        action="create_project",
        details={
            "project_name": project_name,
            "path": str(project_path),
            "type": project_type,
            "priority": priority,
        },
    )

    for project in memory_system.list_projects():
        if project["name"] == project_name:
            return _project_response(project)

    raise HTTPException(status_code=500, detail="Projeto criado, mas não encontrado")
