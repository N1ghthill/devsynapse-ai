"""Memory contracts used by the agent brain."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)


class BrainMemoryProtocol(Protocol):
    """Memory operations required by DevSynapseBrain."""

    def get_user_preferences(self) -> str: ...

    def get_projects_context(self) -> str: ...

    async def get_conversation_context(self, conversation_id: Optional[str] = None) -> Dict: ...

    async def save_interaction(
        self,
        conversation_id: Optional[str],
        user_message: str,
        ai_response: str,
        opencode_command: Optional[str] = None,
        conversation_title: Optional[str] = None,
        llm_usage: Optional[Dict[str, Any]] = None,
        project_name: Optional[str] = None,
    ) -> Optional[str]: ...

    async def save_command_execution(
        self,
        conversation_id: Optional[str],
        command: str,
        success: bool,
        result: str,
        output: Optional[str] = None,
        status: Optional[str] = None,
        reason_code: Optional[str] = None,
        project_name: Optional[str] = None,
        record_agent_event: bool = True,
    ) -> Any: ...


class BrainMemoryAdapter:
    """Compatibility wrapper for optional memory capabilities."""

    def __init__(self, backend: BrainMemoryProtocol):
        self.backend = backend

    def get_project(self, name: str) -> Optional[Dict[str, Any]]:
        return self._call_optional("get_project", None, name)

    def get_project_memory_context(
        self,
        project_name: Optional[str],
        user_message: str,
    ) -> str:
        return self._call_optional(
            "get_project_memory_context",
            "Nenhuma memória procedural relevante encontrada.",
            project_name,
            user_message,
        )

    def get_skills_context(
        self,
        user_message: str,
        project_name: Optional[str] = None,
    ) -> str:
        return self._call_optional(
            "get_skills_context",
            "Nenhuma skill registrada ainda.",
            user_message,
            project_name=project_name,
        )

    def get_active_agent_run(self, conversation_id: Optional[str]) -> Optional[Dict[str, Any]]:
        return self._call_optional("get_active_agent_run", None, conversation_id)

    def start_or_resume_agent_run(
        self,
        conversation_id: Optional[str],
        goal: str,
        project_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return self._call_optional(
            "start_or_resume_agent_run",
            None,
            conversation_id=conversation_id,
            goal=goal,
            project_name=project_name,
        )

    def get_agent_run_context(self, conversation_id: Optional[str]) -> str:
        return self._call_optional(
            "get_agent_run_context",
            "Nenhuma tarefa de agente ativa.",
            conversation_id,
        )

    def record_agent_command_result(self, **kwargs: Any) -> None:
        self._call_optional("record_agent_command_result", None, **kwargs)

    def record_agent_final_response(self, **kwargs: Any) -> None:
        self._call_optional("record_agent_final_response", None, **kwargs)

    def review_completed_task(self, **kwargs: Any) -> None:
        self._call_optional("review_completed_task", None, **kwargs)

    def record_agent_route_decision(self, **kwargs: Any) -> None:
        self._call_optional("record_agent_route_decision", None, **kwargs)

    def add_project(self, *args: Any, **kwargs: Any) -> Any:
        return self._call_optional("add_project", None, *args, **kwargs)

    def get_llm_model(self, provider: str, model: str) -> Optional[Dict[str, Any]]:
        return self._call_optional("get_llm_model", None, provider, model)

    def record_llm_request_telemetry(self, **kwargs: Any) -> None:
        self._call_optional("record_llm_request_telemetry", None, **kwargs)

    def _call_optional(
        self,
        method_name: str,
        default: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        method = getattr(self.backend, method_name, None)
        if method is None:
            return default
        try:
            return method(*args, **kwargs)
        except Exception:
            logger.debug("Memory optional method failed: %s", method_name, exc_info=True)
            return default
