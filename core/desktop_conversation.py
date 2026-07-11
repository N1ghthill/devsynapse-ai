"""Desktop conversation adapter around the current DevSynapse core."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from config.settings import AppSettings, get_settings
from core.brain import DevSynapseBrain
from core.memory import MemorySystem
from core.opencode_bridge import OpenCodeBridge


@dataclass(frozen=True)
class DesktopConversationResult:
    text: str
    command_pending: bool = False


def has_provider_key(settings: AppSettings | None = None) -> bool:
    settings = settings or get_settings()
    return any(
        (
            settings.deepseek_api_key,
            settings.openrouter_api_key,
            settings.opencode_zen_api_key,
            settings.opencode_go_api_key,
        )
    )


class DesktopConversationService:
    """Owns the core runtime used by desktop conversation requests."""

    def __init__(self) -> None:
        self.memory = MemorySystem()
        self.opencode = OpenCodeBridge(
            known_projects=self.memory.get_project_lookup(),
        )
        self.brain = DevSynapseBrain(self.memory, self.opencode)

    def send_message(self, *, conversation_id: str, message: str) -> DesktopConversationResult:
        return asyncio.run(
            self.send_message_async(conversation_id=conversation_id, message=message)
        )

    async def send_message_async(
        self,
        *,
        conversation_id: str,
        message: str,
    ) -> DesktopConversationResult:
        if not has_provider_key():
            response = (
                "No LLM provider is configured for the desktop app yet. "
                "Open Settings to connect a provider before asking for repository analysis."
            )
            await self.memory.save_interaction(
                conversation_id=conversation_id,
                user_message=message,
                ai_response=response,
            )
            return DesktopConversationResult(text=response)

        response_text, opencode_command, _usage = await self.brain.process_message(
            message,
            conversation_id,
            user_role="user",
            auto_execute=False,
            agent_mode="plan",
        )
        return DesktopConversationResult(
            text=response_text,
            command_pending=opencode_command is not None,
        )
