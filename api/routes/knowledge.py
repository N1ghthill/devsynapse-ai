"""Routes for procedural memories and skills."""

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_memory_system, require_admin, require_user
from api.models import (
    KnowledgeStatsResponse,
    ProjectMemoryCreateRequest,
    ProjectMemoryFeedbackRequest,
    ProjectMemoryListResponse,
    ProjectMemoryResponse,
    SkillActivateRequest,
    SkillCreateRequest,
    SkillDetailResponse,
    SkillListResponse,
    SkillSummaryResponse,
    SkillUpdateRequest,
)
from core.memory import MemorySystem
from core.skills import SkillError

router = APIRouter(tags=["knowledge"])


def _validate_project(memory_system: MemorySystem, project_name: str | None) -> None:
    if project_name and memory_system.get_project(project_name) is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")


def _can_write_knowledge(memory_system: MemorySystem, user: dict, project_name: str | None) -> bool:
    if user.get("role") == "admin":
        return True
    if not project_name:
        return False
    return project_name in memory_system.get_project_permissions(user.get("username"))


def _require_knowledge_write_scope(
    memory_system: MemorySystem,
    user: dict,
    project_name: str | None,
) -> None:
    if not _can_write_knowledge(memory_system, user, project_name):
        raise HTTPException(
            status_code=403,
            detail="Permissão de mutação do projeto necessária para alterar conhecimento",
        )


def _skill_summary(skill: dict) -> SkillSummaryResponse:
    return SkillSummaryResponse(**skill)


@router.get("/knowledge/stats", response_model=KnowledgeStatsResponse)
async def knowledge_stats(
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del user
    return KnowledgeStatsResponse(**memory_system.get_knowledge_stats())


@router.get("/memories", response_model=ProjectMemoryListResponse)
async def list_memories(
    project_name: str | None = None,
    query: str | None = None,
    limit: int = 20,
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del user
    _validate_project(memory_system, project_name)
    memories = memory_system.list_project_memories(
        project_name=project_name,
        query=query,
        limit=min(max(limit, 1), 100),
    )
    return ProjectMemoryListResponse(
        memories=[ProjectMemoryResponse(**memory) for memory in memories]
    )


@router.post("/memories", response_model=ProjectMemoryResponse)
async def create_memory(
    payload: ProjectMemoryCreateRequest,
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    _validate_project(memory_system, payload.project_name)
    _require_knowledge_write_scope(memory_system, user, payload.project_name)
    try:
        memory = memory_system.upsert_project_memory(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProjectMemoryResponse(**memory)


@router.post("/memories/{memory_id}/feedback", response_model=ProjectMemoryResponse)
async def adjust_memory_confidence(
    memory_id: int,
    payload: ProjectMemoryFeedbackRequest,
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    existing = memory_system.get_project_memory(memory_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Memória não encontrada")
    _require_knowledge_write_scope(memory_system, user, existing.get("project_name"))

    memory = memory_system.adjust_project_memory_confidence(
        memory_id,
        payload.delta,
        payload.source,
    )
    if memory is None:
        raise HTTPException(status_code=404, detail="Memória não encontrada")
    return ProjectMemoryResponse(**memory)


@router.get("/skills", response_model=SkillListResponse)
async def list_skills(
    project_name: str | None = None,
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del user
    _validate_project(memory_system, project_name)
    skills = memory_system.list_skills(project_name=project_name)
    return SkillListResponse(skills=[_skill_summary(skill) for skill in skills])


@router.post("/skills", response_model=SkillDetailResponse)
async def create_skill(
    payload: SkillCreateRequest,
    admin=Depends(require_admin),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del admin
    _validate_project(memory_system, payload.project_name)
    try:
        skill = memory_system.create_skill(
            name=payload.name,
            description=payload.description,
            body=payload.body,
            category=payload.category,
            project_name=payload.project_name,
            tags=payload.tags,
            replace=payload.replace,
            source="api",
        )
    except SkillError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SkillDetailResponse(**skill)


@router.get("/skills/{skill_name}", response_model=SkillDetailResponse)
async def get_skill(
    skill_name: str,
    project_name: str | None = None,
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del user
    _validate_project(memory_system, project_name)
    skill = memory_system.get_skill(skill_name, project_name=project_name)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill não encontrada")
    return SkillDetailResponse(**skill)


@router.post("/skills/{skill_name}/activate", response_model=SkillDetailResponse)
async def activate_skill(
    skill_name: str,
    payload: SkillActivateRequest,
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del user
    _validate_project(memory_system, payload.project_name)
    skill = memory_system.activate_skill(
        skill_name,
        project_name=payload.project_name,
        conversation_id=payload.conversation_id,
        reason=payload.reason,
    )
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill não encontrada")
    return SkillDetailResponse(**skill)


@router.patch("/skills/{skill_name}", response_model=SkillDetailResponse)
async def update_skill(
    skill_name: str,
    payload: SkillUpdateRequest,
    admin=Depends(require_admin),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del admin
    _validate_project(memory_system, payload.project_name)
    try:
        skill = memory_system.update_skill(
            skill_name,
            body=payload.body,
            description=payload.description,
            project_name=payload.project_name,
        )
    except SkillError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill não encontrada")
    return SkillDetailResponse(**skill)


@router.delete("/skills/{skill_name}")
async def delete_skill(
    skill_name: str,
    project_name: str | None = None,
    admin=Depends(require_admin),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del admin
    _validate_project(memory_system, project_name)
    deleted = memory_system.delete_skill(skill_name, project_name=project_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Skill não encontrada")
    return {"success": True, "skill": skill_name}
