"""Contextual command suggestions for DevSynapse AI TUI."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from devsynapse.command_catalog import build_command_suggestions

logger = logging.getLogger(__name__)


@dataclass
class UserContext:
    """Contexto atual do usuário para personalizar sugestões."""

    current_project: str | None = None
    last_command: str | None = None
    conversation_turns: int = 0
    budget_usage_percent: float = 0.0
    has_provider_configured: bool = False
    has_models_discovered: bool = False
    is_first_time: bool = False


class ContextualSuggestor:
    """Gera sugestões de comandos baseadas no contexto do usuário."""

    def __init__(self, context: UserContext | None = None):
        self.context = context or UserContext()

    def suggest(self, current_input: str, limit: int = 5) -> list[str]:
        """
        Retorna sugestões ordenadas por relevância contextual.

        Se o input começar com '/', usa o sistema de sugestões padrão.
        Caso contrário, sugere comandos baseados no contexto.
        """
        if current_input.startswith("/"):
            return self._suggest_slash_commands(current_input, limit)

        return self._suggest_contextual_commands(current_input, limit)

    def _suggest_slash_commands(self, current_input: str, limit: int) -> list[str]:
        """Sugere comandos slash baseados no input parcial."""
        suggestions = build_command_suggestions(current_input, limit=limit)
        return [s.value for s in suggestions]

    def _suggest_contextual_commands(self, current_input: str, limit: int) -> list[str]:
        """Sugere comandos baseados no contexto do usuário."""
        scored_suggestions = []

        if self.context.is_first_time and not self.context.has_provider_configured:
            scored_suggestions.append((100, "/connect"))
            scored_suggestions.append((90, "/providers"))

        if not self.context.has_models_discovered and self.context.has_provider_configured:
            scored_suggestions.append((85, "/discover"))

        if self.context.budget_usage_percent > 80:
            scored_suggestions.append((95, "/budget"))

        if not self.context.current_project:
            scored_suggestions.append((70, "/projects"))
            scored_suggestions.append((65, "/project"))

        if self.context.conversation_turns == 0:
            scored_suggestions.append((60, "/help"))
            scored_suggestions.append((55, "/status"))

        if current_input.startswith("!"):
            scored_suggestions.append((80, "!git status"))
            scored_suggestions.append((75, "!ls"))

        scored_suggestions.sort(key=lambda x: x[0], reverse=True)
        return [cmd for _, cmd in scored_suggestions[:limit]]

    def get_command_insights(self) -> dict[str, Any]:
        """
        Retorna estatísticas de uso para personalizar sugestões.
        """
        return {
            "is_first_time": self.context.is_first_time,
            "has_provider": self.context.has_provider_configured,
            "has_models": self.context.has_models_discovered,
            "budget_usage": self.context.budget_usage_percent,
            "conversation_turns": self.context.conversation_turns,
            "current_project": self.context.current_project,
        }


def get_contextual_suggestions(
    current_input: str,
    context: dict[str, Any] | None = None,
    limit: int = 5,
) -> list[str]:
    """
    Função auxiliar para obter sugestões contextuais.

    Args:
        current_input: Input atual do usuário
        context: Dicionário com contexto opcional
        limit: Número máximo de sugestões

    Returns:
        Lista de sugestões de comandos
    """
    if context is None:
        context = {}

    user_context = UserContext(
        current_project=context.get("current_project"),
        last_command=context.get("last_command"),
        conversation_turns=context.get("conversation_turns", 0),
        budget_usage_percent=context.get("budget_usage_percent", 0.0),
        has_provider_configured=context.get("has_provider_configured", False),
        has_models_discovered=context.get("has_models_discovered", False),
        is_first_time=context.get("is_first_time", False),
    )

    suggestor = ContextualSuggestor(user_context)
    return suggestor.suggest(current_input, limit)
