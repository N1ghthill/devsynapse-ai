"""
Chat and execution routes.
"""
import json
import logging
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse

from api.dependencies import (
    get_brain,
    get_memory_system,
    get_monitoring_system,
    get_opencode_bridge,
    require_user,
)
from api.models import (
    ChatRequest,
    ChatResponse,
    CommandExecutionRequest,
    CommandExecutionResponse,
    ConversationListResponse,
    ConversationMutationResponse,
    ConversationRenameRequest,
    FeedbackRequest,
    FeedbackResponse,
    PrerequisiteCheckListResponse,
    PrerequisiteCheckResponse,
)
from config.settings import get_settings
from core.brain import DevSynapseBrain
from core.memory import MemorySystem
from core.opencode_bridge import OpenCodeBridge

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


async def _log_api_request_background(monitoring_system, **kwargs):
    monitoring_system.log_api_request(**kwargs)


def _refresh_bridge_projects(memory_system: MemorySystem, bridge: OpenCodeBridge) -> None:
    """Keep long-lived command bridge instances aligned with the project registry."""

    if not hasattr(bridge, "known_projects"):
        return
    bridge.known_projects.update(memory_system.get_project_lookup())


def _persist_bridge_project_if_needed(
    memory_system: MemorySystem,
    bridge: OpenCodeBridge,
    project_name: str | None,
) -> None:
    """Persist a project inferred by command execution under DEV_REPOS_ROOT."""

    if not project_name:
        return
    existing_project = memory_system.get_project(project_name, include_missing=True)
    if existing_project and existing_project["path_exists"]:
        return
    project_info = bridge.known_projects.get(project_name)
    if not project_info:
        return

    project_path = Path(project_info["path"]).expanduser().resolve()
    repos_root = get_settings().dev_repos_root.expanduser().resolve()
    try:
        project_path.relative_to(repos_root)
    except ValueError:
        return
    if not project_path.is_dir():
        return

    memory_system.add_project(
        project_name,
        str(project_path),
        project_info.get("type", "project"),
        project_info.get("priority", "medium"),
        replace=existing_project is not None,
    )


def _resolve_locked_project(
    memory_system: MemorySystem,
    conversation_id: str,
    requested_project_name: str | None,
) -> str | None:
    persisted_project = memory_system.get_conversation_project_name(conversation_id)
    if persisted_project and requested_project_name and requested_project_name != persisted_project:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Esta conversa está travada no projeto '{persisted_project}'. "
                "Abra uma nova conversa para trabalhar em outro projeto."
            ),
        )

    effective_project = persisted_project or requested_project_name
    if effective_project and memory_system.get_project(effective_project) is None:
        raise HTTPException(
            status_code=400,
            detail=f"Projeto não registrado: {effective_project}",
        )
    return effective_project


PREREQUISITE_CHECKS = [
    {
        "name": "Git",
        "command": "git --version",
        "args": ["git", "--version"],
        "install_hint": "Instale o Git pelo gerenciador de pacotes do sistema.",
    },
    {
        "name": "Python 3",
        "command": "python3 --version",
        "args": ["python3", "--version"],
        "install_hint": "Instale Python 3 pelo gerenciador de pacotes do sistema.",
    },
    {
        "name": "Node.js",
        "command": "node --version",
        "args": ["node", "--version"],
        "install_hint": "Instale Node.js via nvm, Volta ou gerenciador de pacotes.",
    },
    {
        "name": "npm",
        "command": "npm --version",
        "args": ["npm", "--version"],
        "install_hint": "Instale npm junto com Node.js ou pelo gerenciador de pacotes.",
    },
    {
        "name": "Rust",
        "command": "rustc --version",
        "args": ["rustc", "--version"],
        "install_hint": "Instale Rust pelo rustup ou pelo gerenciador de pacotes.",
    },
    {
        "name": "Cargo",
        "command": "cargo --version",
        "args": ["cargo", "--version"],
        "install_hint": "Instale Cargo junto com Rust.",
    },
    {
        "name": "Tauri CLI",
        "command": "cargo tauri --version",
        "args": ["cargo", "tauri", "--version"],
        "install_hint": "Instale com `cargo install tauri-cli` depois de instalar Rust/Cargo.",
    },
]


def _run_prerequisite_check(check: dict, cwd: str | None = None) -> PrerequisiteCheckResponse:
    args = check["args"]
    executable = args[0]
    if shutil.which(executable) is None:
        return PrerequisiteCheckResponse(
            name=check["name"],
            command=check["command"],
            installed=False,
            detail=f"{executable} não encontrado no PATH",
            install_hint=check["install_hint"],
        )

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=8,
            cwd=cwd,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return PrerequisiteCheckResponse(
            name=check["name"],
            command=check["command"],
            installed=False,
            detail="Verificação excedeu o tempo limite",
            install_hint=check["install_hint"],
        )
    except Exception as exc:
        return PrerequisiteCheckResponse(
            name=check["name"],
            command=check["command"],
            installed=False,
            detail=str(exc),
            install_hint=check["install_hint"],
        )

    output = (result.stdout or result.stderr or "").strip()
    if result.returncode == 0:
        return PrerequisiteCheckResponse(
            name=check["name"],
            command=check["command"],
            installed=True,
            detail=output or "Disponível",
            install_hint=None,
        )
    return PrerequisiteCheckResponse(
        name=check["name"],
        command=check["command"],
        installed=False,
        detail=output or f"Falhou com exit code {result.returncode}",
        install_hint=check["install_hint"],
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    user=Depends(require_user),
    brain: DevSynapseBrain = Depends(get_brain),
    memory_system: MemorySystem = Depends(get_memory_system),
    bridge: OpenCodeBridge = Depends(get_opencode_bridge),
    monitoring_system=Depends(get_monitoring_system),
):
    conversation_id = request.conversation_id or str(uuid.uuid4())
    _refresh_bridge_projects(memory_system, bridge)
    effective_project_name = _resolve_locked_project(
        memory_system,
        conversation_id,
        request.project_name,
    )
    project_permissions = memory_system.get_project_permissions(user["username"])
    user_id = user["username"]
    user_role = user["role"]
    del user

    try:
        response_text, opencode_command, llm_usage = await brain.process_message(
            user_message=request.message,
            conversation_id=conversation_id,
            project_name=effective_project_name,
            user_id=user_id,
            user_role=user_role,
            project_mutation_allowlist=project_permissions,
            auto_execute=request.execute_command,
        )
    except Exception as exc:
        logger.error("Erro processando chat: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno processando mensagem: {exc}",
        ) from exc

    requires_confirmation = opencode_command is not None and not request.execute_command
    monitoring_system.sync_llm_budget_alerts(memory_system.get_llm_budget_status())
    response_project_name = effective_project_name
    if response_project_name is None:
        context = await memory_system.get_conversation_context(conversation_id)
        response_project_name = context.get("project_name")

    return ChatResponse(
        response=response_text,
        conversation_id=conversation_id,
        opencode_command=opencode_command,
        command=opencode_command,
        requires_confirmation=requires_confirmation,
        llm_usage=llm_usage,
        project_name=response_project_name,
    )


@router.post("/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    user=Depends(require_user),
    brain: DevSynapseBrain = Depends(get_brain),
    memory_system: MemorySystem = Depends(get_memory_system),
    bridge: OpenCodeBridge = Depends(get_opencode_bridge),
):
    conversation_id = request.conversation_id or str(uuid.uuid4())
    _refresh_bridge_projects(memory_system, bridge)
    effective_project_name = _resolve_locked_project(
        memory_system,
        conversation_id,
        request.project_name,
    )

    async def event_generator():
        project_permissions = memory_system.get_project_permissions(user["username"])
        try:
            async for chunk in brain.process_message_streaming(
                user_message=request.message,
                conversation_id=conversation_id,
                project_name=effective_project_name,
                user_id=user["username"],
                user_role=user["role"],
                project_mutation_allowlist=project_permissions,
                auto_execute=request.execute_command,
            ):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.error("Erro no streaming: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/history")
async def get_history(
    conversation_id: str | None = None,
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del user
    context = await memory_system.get_conversation_context(conversation_id)
    return {
        "conversation_id": conversation_id,
        "history": context.get("conversation_messages", []),
        "project_name": context.get("project_name"),
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del user
    context = await memory_system.get_conversation_context(conversation_id)
    return {
        "conversation_id": conversation_id,
        "history": context.get("conversation_messages", []),
        "project_name": context.get("project_name"),
        "preferences": memory_system.get_user_preferences(),
    }


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = 20,
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del user
    return {"conversations": memory_system.list_conversations(limit=limit)}


@router.get("/conversations/export/usage.csv")
async def export_conversation_usage_csv(
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    return PlainTextResponse(
        memory_system.export_llm_usage_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="devsynapse-usage.csv"'
        },
    )


@router.put("/conversations/{conversation_id}", response_model=ConversationMutationResponse)
async def rename_conversation(
    conversation_id: str,
    payload: ConversationRenameRequest,
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del user
    updated = memory_system.rename_conversation(conversation_id, payload.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    return {"success": True, "conversation_id": conversation_id}


@router.delete("/conversations/{conversation_id}", response_model=ConversationMutationResponse)
async def delete_conversation(
    conversation_id: str,
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del user
    deleted = memory_system.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    return {"success": True, "conversation_id": conversation_id}


@router.post("/execute", response_model=CommandExecutionResponse)
async def execute_command(
    request: CommandExecutionRequest,
    background_tasks: BackgroundTasks,
    user=Depends(require_user),
    bridge: OpenCodeBridge = Depends(get_opencode_bridge),
    brain: DevSynapseBrain = Depends(get_brain),
    memory_system: MemorySystem = Depends(get_memory_system),
    monitoring_system=Depends(get_monitoring_system),
):
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmação necessária para executar comandos",
        )

    start_time = time.time()

    _refresh_bridge_projects(memory_system, bridge)
    effective_project_name = _resolve_locked_project(
        memory_system,
        request.conversation_id,
        request.project_name,
    )

    try:
        project_mutation_allowlist = memory_system.get_project_permissions(user["username"])

        success, message, output, status, reason_code, project_name = await bridge.execute_command(
            request.command,
            user_id=user["username"],
            project_name=effective_project_name,
            user_role=user["role"],
            project_mutation_allowlist=project_mutation_allowlist,
        )
        if success:
            _persist_bridge_project_if_needed(memory_system, bridge, project_name)

        await memory_system.save_command_execution(
            conversation_id=request.conversation_id,
            command=request.command,
            success=success,
            result=message,
            output=output,
            status=status,
            reason_code=reason_code,
            project_name=project_name,
        )

        response_time = time.time() - start_time
        background_tasks.add_task(
            _log_api_request_background,
            monitoring_system,
            endpoint="/execute",
            method="POST",
            status_code=200,
            response_time=response_time,
            user_id=user["username"],
            ip_address=None,
        )

        interpretation = None
        if success and output:
            try:
                interpretation = await brain.interpret_execution_result(
                    conversation_id=request.conversation_id,
                    command=request.command,
                    output=output,
                    project_name=project_name or effective_project_name,
                )
            except Exception:
                logger.debug("Failed to get execution interpretation", exc_info=True)

        return CommandExecutionResponse(
            success=success,
            message=message,
            output=output,
            status=status,
            reason_code=reason_code,
            project_name=project_name,
            interpretation=interpretation,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Erro executando comando: %s", exc)
        response_time = time.time() - start_time
        background_tasks.add_task(
            _log_api_request_background,
            monitoring_system,
            endpoint="/execute",
            method="POST",
            status_code=500,
            response_time=response_time,
            user_id=user["username"],
            ip_address=None,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Erro executando comando: {exc}",
        ) from exc


@router.get("/prerequisites", response_model=PrerequisiteCheckListResponse)
async def check_prerequisites(
    conversation_id: str | None = None,
    project_name: str | None = None,
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del user
    effective_project_name = None
    cwd = None
    if conversation_id or project_name:
        effective_project_name = _resolve_locked_project(
            memory_system,
            conversation_id or "",
            project_name,
        )
        if effective_project_name:
            project = memory_system.get_project(effective_project_name)
            if project and project.get("path"):
                cwd = project["path"]

    checks = [_run_prerequisite_check(check, cwd=cwd) for check in PREREQUISITE_CHECKS]
    return PrerequisiteCheckListResponse(
        project_name=effective_project_name,
        ready=all(check.installed for check in checks),
        checks=checks,
    )


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    user=Depends(require_user),
    memory_system: MemorySystem = Depends(get_memory_system),
):
    del user
    try:
        await memory_system.save_feedback(
            conversation_id=request.conversation_id,
            feedback=request.feedback,
            score=request.score,
        )
        return FeedbackResponse(
            success=True,
            message="Feedback recebido e processado para aprendizado",
        )
    except Exception as exc:
        logger.error("Erro processando feedback: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Erro processando feedback: {exc}",
        ) from exc
