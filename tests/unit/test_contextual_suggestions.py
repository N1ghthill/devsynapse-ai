"""Tests for contextual command suggestions."""
from __future__ import annotations

from devsynapse.contextual_suggestions import (
    ContextualSuggestor,
    UserContext,
    get_contextual_suggestions,
)


class TestUserContext:
    def test_default_context(self):
        context = UserContext()
        assert context.current_project is None
        assert context.last_command is None
        assert context.conversation_turns == 0
        assert context.budget_usage_percent == 0.0
        assert context.has_provider_configured is False
        assert context.has_models_discovered is False
        assert context.is_first_time is False


class TestContextualSuggestor:
    def test_suggest_slash_commands(self):
        context = UserContext()
        suggestor = ContextualSuggestor(context)

        suggestions = suggestor.suggest("/con", limit=3)
        assert len(suggestions) > 0
        assert any(s.startswith("/con") for s in suggestions)

    def test_suggest_for_first_time_user(self):
        context = UserContext(is_first_time=True, has_provider_configured=False)
        suggestor = ContextualSuggestor(context)

        suggestions = suggestor.suggest("", limit=5)
        assert "/connect" in suggestions
        assert "/providers" in suggestions

    def test_suggest_discover_when_no_models(self):
        context = UserContext(
            has_provider_configured=True,
            has_models_discovered=False,
        )
        suggestor = ContextualSuggestor(context)

        suggestions = suggestor.suggest("", limit=5)
        assert "/discover" in suggestions

    def test_suggest_budget_when_high_usage(self):
        context = UserContext(budget_usage_percent=85.0)
        suggestor = ContextualSuggestor(context)

        suggestions = suggestor.suggest("", limit=5)
        assert "/budget" in suggestions

    def test_suggest_projects_when_no_project(self):
        context = UserContext(current_project=None)
        suggestor = ContextualSuggestor(context)

        suggestions = suggestor.suggest("", limit=5)
        assert "/projects" in suggestions or "/project" in suggestions

    def test_suggest_help_for_new_conversation(self):
        context = UserContext(conversation_turns=0)
        suggestor = ContextualSuggestor(context)

        suggestions = suggestor.suggest("", limit=5)
        assert "/help" in suggestions or "/status" in suggestions

    def test_suggest_bash_commands_for_bash_input(self):
        context = UserContext()
        suggestor = ContextualSuggestor(context)

        suggestions = suggestor.suggest("!", limit=5)
        assert any(s.startswith("!") for s in suggestions)

    def test_suggestions_are_limited(self):
        context = UserContext(is_first_time=True)
        suggestor = ContextualSuggestor(context)

        suggestions = suggestor.suggest("", limit=2)
        assert len(suggestions) <= 2

    def test_get_command_insights(self):
        context = UserContext(
            is_first_time=True,
            has_provider_configured=True,
            budget_usage_percent=50.0,
        )
        suggestor = ContextualSuggestor(context)

        insights = suggestor.get_command_insights()
        assert insights["is_first_time"] is True
        assert insights["has_provider"] is True
        assert insights["budget_usage"] == 50.0


class TestGetContextualSuggestions:
    def test_with_empty_context(self):
        suggestions = get_contextual_suggestions("/help")
        assert len(suggestions) > 0

    def test_with_custom_context(self):
        context = {
            "is_first_time": True,
            "has_provider_configured": False,
        }
        suggestions = get_contextual_suggestions("", context=context)
        assert "/connect" in suggestions

    def test_with_limit(self):
        suggestions = get_contextual_suggestions("", limit=1)
        assert len(suggestions) <= 1

    def test_with_partial_input(self):
        suggestions = get_contextual_suggestions("/con")
        assert any(s.startswith("/con") for s in suggestions)
