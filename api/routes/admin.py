"""Administrative routes for user and permission management."""

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_memory_system, require_admin
from api.models import (
    AdminAuditLogsResponse,
    AdminUserPermissionsUpdateRequest,
    AdminUsersResponse,
    AdminUserSummary,
)
from core.memory import MemorySystem

router = APIRouter(prefix="/admin", tags=["admin"])


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
            project_mutation_allowlist=memory_system.get_project_permissions(row["username"]),
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
        project_mutation_allowlist=memory_system.get_project_permissions(username),
    )
