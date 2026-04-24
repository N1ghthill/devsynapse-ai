"""
Chat and execution routes.
"""
import logging
import time
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import PlainTextResponse

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
)
from core.brain import DevSynapseBrain
from core.memory import MemorySystem
from core.opencode_bridge import OpenCodeBridge

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    brain: DevSynapseBrain = Depends(get_brain),
):
    conversation_id = request.conversation_id or str(uuid.uuid4())

    try:
        response_text, opencode_command, llm_usage = await brain.process_message(
            user_message=request.message,
            conversation_id=conversation_id,
        )
    except Exception as exc:
        logger.error("Erro processando chat: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno processando mensagem: {exc}",
        ) from exc

    requires_confirmation = opencode_command is not None and not request.execute_command

    return ChatResponse(
        response=response_text,
        conversation_id=conversation_id,
        opencode_command=opencode_command,
        command=opencode_command,
        requires_confirmation=requires_confirmation,
        llm_usage=llm_usage,
    )


@router.get("/chat/history")
async def get_history(
    conversation_id: str | None = None,
    memory_system: MemorySystem = Depends(get_memory_system),
):
    context = await memory_system.get_conversation_context(conversation_id)
    return {
        "conversation_id": conversation_id,
        "history": context.get("conversation_messages", []),
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    memory_system: MemorySystem = Depends(get_memory_system),
):
    context = await memory_system.get_conversation_context(conversation_id)
    return {
        "conversation_id": conversation_id,
        "history": context.get("conversation_messages", []),
        "preferences": memory_system.get_user_preferences(),
    }


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = 20,
    memory_system: MemorySystem = Depends(get_memory_system),
):
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
    memory_system: MemorySystem = Depends(get_memory_system),
):
    updated = memory_system.rename_conversation(conversation_id, payload.title)
    if not updated:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    return {"success": True, "conversation_id": conversation_id}


@router.delete("/conversations/{conversation_id}", response_model=ConversationMutationResponse)
async def delete_conversation(
    conversation_id: str,
    memory_system: MemorySystem = Depends(get_memory_system),
):
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
    memory_system: MemorySystem = Depends(get_memory_system),
    monitoring_system=Depends(get_monitoring_system),
):
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmação necessária para executar comandos",
        )

    start_time = time.time()

    try:
        project_mutation_allowlist = memory_system.get_project_permissions(user["username"])

        success, message, output, status, reason_code, project_name = await bridge.execute_command(
            request.command,
            user_id=user["username"],
            project_name=request.project_name,
            user_role=user["role"],
            project_mutation_allowlist=project_mutation_allowlist,
        )

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
            monitoring_system.log_api_request,
            endpoint="/execute",
            method="POST",
            status_code=200 if success else 500,
            response_time=response_time,
            user_id=user["username"],
            ip_address=None,
        )
        return CommandExecutionResponse(
            success=success,
            message=message,
            output=output,
            status=status,
            reason_code=reason_code,
        )
    except Exception as exc:
        logger.error("Erro executando comando: %s", exc)
        response_time = time.time() - start_time
        background_tasks.add_task(
            monitoring_system.log_api_request,
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


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    memory_system: MemorySystem = Depends(get_memory_system),
):
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
