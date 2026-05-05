"""
Unit tests for brain system
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.brain import DevSynapseBrain
from core.deepseek import LLMResult


@pytest.fixture
def mock_memory():
    memory = Mock()
    memory.get_user_preferences.return_value = "Usuário prefere Python e VS Code"
    memory.get_projects_context.return_value = "Projeto: DevSynapse AI"
    memory.get_conversation_context = AsyncMock(return_value={
        "conversation_history": [],
        "user_preferences": "Python",
        "projects_context": "DevSynapse",
        "recent_decisions": []
    })
    memory.get_app_settings.return_value = {}
    memory.get_llm_budget_status.return_value = {"overall_status": "healthy"}
    memory.get_agent_learning.return_value = None
    memory.get_agent_learning_context.return_value = "Nenhum padrão de agente aprendido ainda."
    memory.get_project_memory_context.return_value = "Nenhuma memória procedural relevante encontrada."
    memory.get_skills_context.return_value = "Nenhuma skill registrada ainda."
    memory.get_active_agent_run.return_value = None
    memory.get_agent_run_context.return_value = "Nenhuma tarefa de agente ativa."
    memory.start_or_resume_agent_run.return_value = {
        "id": 1,
        "conversation_id": "test_session",
        "goal": "test",
        "status": "running",
    }
    memory.record_agent_command_result = Mock()
    memory.record_agent_final_response = Mock()
    memory.review_completed_task = Mock()
    memory.record_agent_route_decision = Mock()
    memory.save_interaction = AsyncMock(return_value=None)
    memory.save_command_execution = AsyncMock()
    return memory


@pytest.fixture
def mock_bridge():
    bridge = Mock()
    bridge.execute_command.return_value = {
        "success": True,
        "output": "Command executed",
        "error": None
    }
    return bridge


class TestDevSynapseBrain:
    """Test DevSynapseBrain class"""

    def test_init(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        assert brain.memory == mock_memory
        assert brain.opencode == mock_bridge

    def test_init_without_api_key(self, mock_memory, mock_bridge):
        import config.settings as settings
        orig = settings.DEEPSEEK_API_KEY
        settings.DEEPSEEK_API_KEY = None
        try:
            brain = DevSynapseBrain(mock_memory, mock_bridge)
            assert brain.api_key is None
        finally:
            settings.DEEPSEEK_API_KEY = orig

    def test_generate_system_prompt(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        prompt = brain.generate_system_prompt({"test": "context"})
        assert "DevSynapse" in prompt
        assert "Irving" in prompt or "N1ghthill" in prompt
        assert "tools" in prompt.lower()
        assert "CURRENT AGENT RUN" in prompt
        assert 'Do not ask "should I continue?"' in prompt

    def test_generate_system_prompt_includes_active_project(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        prompt = brain.generate_system_prompt({"project_name": "devsynapse-ai"})

        assert "PROJETO ATIVO" in prompt
        assert "devsynapse-ai" in prompt
        assert "Repositories root" in prompt
        assert "/home/user" in prompt

    @pytest.mark.asyncio
    async def test_process_message_calls_api(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch.object(brain, '_call_llm_api', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "Here is a response for you!"

            response, cmd, usage = await brain.process_message("Hello!", "test_session")

            assert response == "Here is a response for you!"
            assert cmd is None
            assert usage is None

        # Verify memory was saved
        mock_memory.save_interaction.assert_called_once()
        args = mock_memory.save_interaction.call_args[1]
        assert args["user_message"] == "Hello!"

    @pytest.mark.asyncio
    async def test_process_message_persists_explicit_project_name(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch.object(brain, '_call_llm_api', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "Resposta sobre o projeto"

            await brain.process_message(
                "Analise este projeto",
                "test_session",
                project_name="devsynapse-ai",
            )

        args = mock_memory.save_interaction.call_args[1]
        assert args["project_name"] == "devsynapse-ai"

    @pytest.mark.asyncio
    async def test_process_message_reuses_persisted_project_name(self, mock_memory, mock_bridge):
        mock_memory.get_conversation_context.return_value = {
            "conversation_history": [],
            "user_preferences": "Python",
            "projects_context": "DevSynapse",
            "project_name": "devsynapse-ai",
            "recent_decisions": [],
        }
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch.object(brain, '_call_llm_api', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "Resposta de continuidade"

            await brain.process_message("Continue", "test_session")

        args = mock_memory.save_interaction.call_args[1]
        assert args["project_name"] == "devsynapse-ai"

    @pytest.mark.asyncio
    async def test_process_message_with_opencode_command(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch.object(brain, '_call_llm_api', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = 'Here is the file list: bash "ls -la"'

            response, cmd, usage = await brain.process_message("List files", "test_session")

            assert cmd is not None
            assert "bash" in cmd
            assert "ls" in cmd
            assert usage is None

    @pytest.mark.asyncio
    async def test_process_message_plugin_cancel_returns_full_contract(
        self, mock_memory, mock_bridge
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch("core.brain.plugin_manager.emit_event", new_callable=AsyncMock) as mock_emit:
            mock_emit.return_value = SimpleNamespace(cancelled=True, data={})

            response, cmd, usage = await brain.process_message("Hello", "test_session")

        assert response == "Processamento cancelado por plugin."
        assert cmd is None
        assert usage is None
        mock_memory.save_interaction.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_sanitizes_unconfirmed_side_effect_claims(
        self, mock_memory, mock_bridge
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch.object(brain, '_call_llm_api', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = (
                'echo "ok" > /tmp/test.txt\n\n'
                "Done! I created the file for you."
            )

            response, cmd, usage = await brain.process_message("Create a file", "test_session")

            assert cmd is None
            assert "I haven't executed any changes yet" in response
            assert usage is None

    @pytest.mark.asyncio
    async def test_process_message_uses_tool_calls_over_regex(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch.object(brain, '_call_llm_api', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = LLMResult(
                content='Let me check: bash "unused command"',
                tool_calls=[
                    {
                        "id": "call_abc",
                        "type": "function",
                        "function": {
                            "name": "bash",
                            "arguments": '{"command": "ls -la"}',
                        },
                    }
                ],
            )

            response, cmd, usage = await brain.process_message("List files", "test_session")

            assert cmd == 'bash "ls -la"'

    @pytest.mark.asyncio
    async def test_process_message_replays_command_output_as_text(
        self, mock_memory, mock_bridge
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        brain.api_key = "test-key"
        mock_bridge.execute_command = AsyncMock(
            return_value=(True, "ok", "tool output", "success", None, None)
        )

        with patch.object(brain, '_call_llm_api', new_callable=AsyncMock) as mock_call:

            mock_call.side_effect = [
                LLMResult(
                    content="",
                    reasoning_content="I should inspect the repo.",
                    tool_calls=[
                        {
                            "id": "call_pwd",
                            "type": "function",
                            "function": {
                                "name": "bash",
                                "arguments": '{"command": "pwd"}',
                            },
                        },
                        {
                            "id": "call_ls",
                            "type": "function",
                            "function": {
                                "name": "bash",
                                "arguments": '{"command": "ls"}',
                            },
                        },
                    ],
                ),
                LLMResult(content="Final answer"),
            ]

            response, cmd, usage = await brain.process_message(
                "Inspect project",
                "test_session",
                user_id="irving",
                user_role="user",
            )

        replay_messages = mock_call.await_args_list[1].args[0]
        assistant_replay = replay_messages[-2]
        output_replay = replay_messages[-1]

        assert response == "Final answer"
        assert cmd is None
        assert usage is None
        assert assistant_replay == {
            "role": "assistant",
            "content": 'Executed `bash "pwd"`.',
        }
        assert output_replay["role"] == "user"
        assert 'Command `bash "pwd"` finished with status `success`.' in output_replay["content"]
        assert "tool output" in output_replay["content"]
        assert "tool_calls" not in assistant_replay
        assert output_replay["role"] != "tool"
        mock_memory.record_agent_command_result.assert_called_once()
        mock_memory.record_agent_final_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_replays_blocked_auto_command(
        self, mock_memory, mock_bridge
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        brain.api_key = "test-key"
        mock_bridge.execute_command = AsyncMock(
            return_value=(
                False,
                "Ação bloqueada por escopo do projeto",
                None,
                "blocked",
                "project_scope_mismatch",
                "devsynapse-ai",
            )
        )

        with patch.object(brain, '_call_llm_api', new_callable=AsyncMock) as mock_call:

            mock_call.side_effect = [
                LLMResult(
                    content="",
                    tool_calls=[
                        {
                            "id": "call_ls",
                            "type": "function",
                            "function": {
                                "name": "bash",
                                "arguments": '{"command": "ls -la"}',
                            },
                        }
                    ],
                ),
                LLMResult(content="Não consegui sair do escopo; vou manter no projeto ativo."),
            ]

            response, cmd, usage = await brain.process_message(
                "Inspecione o projeto",
                "test_session",
                user_id="irving",
                user_role="user",
                project_name="devsynapse-ai",
                auto_execute=True,
            )

        replay_messages = mock_call.await_args_list[1].args[0]
        assert response == "Não consegui sair do escopo; vou manter no projeto ativo."
        assert cmd is None
        assert usage is None
        assert "blocked" in replay_messages[-1]["content"]
        assert "exact permission/project selection required" in replay_messages[-1]["content"]

    @pytest.mark.asyncio
    async def test_process_message_autoexecutes_admin_mutation_tool(
        self, mock_memory, mock_bridge
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        brain.api_key = "test-key"
        persistence_events = []

        async def record_interaction(**kwargs):
            persistence_events.append(("interaction", kwargs))

        async def record_command_execution(**kwargs):
            persistence_events.append(("command_execution", kwargs))

        mock_memory.save_interaction.side_effect = record_interaction
        mock_memory.save_command_execution.side_effect = record_command_execution
        mock_bridge.execute_command = AsyncMock(
            return_value=(True, "created", "write output", "success", None, None)
        )

        with patch.object(brain, '_call_llm_api', new_callable=AsyncMock) as mock_call:

            mock_call.side_effect = [
                LLMResult(
                    content="",
                    tool_calls=[
                        {
                            "id": "call_write",
                            "type": "function",
                            "function": {
                                "name": "write",
                                "arguments": '{"path": "/tmp/admin.txt", "content": "hello"}',
                            },
                        }
                    ],
                ),
                LLMResult(content="Created it."),
            ]

            response, cmd, usage = await brain.process_message(
                "Create the admin file",
                "test_session",
                user_id="irving",
                user_role="admin",
            )

        mock_bridge.execute_command.assert_awaited_once_with(
            'write "/tmp/admin.txt" --content="hello"',
            user_id="irving",
            project_name=None,
            user_role="admin",
            project_mutation_allowlist=[],
            conversation_id="test_session",
            tool_run_id=mock_bridge.execute_command.await_args.kwargs["tool_run_id"],
        )
        assert mock_bridge.execute_command.await_args.kwargs["tool_run_id"].startswith("tool_")
        assert response == "Created it."
        assert cmd is None
        assert usage is None
        assert [event[0] for event in persistence_events] == [
            "interaction",
            "command_execution",
        ]
        assert persistence_events[0][1]["opencode_command"] == (
            'write "/tmp/admin.txt" --content="hello"'
        )
        assert persistence_events[1][1]["command"] == (
            'write "/tmp/admin.txt" --content="hello"'
        )

        brain = DevSynapseBrain(mock_memory, mock_bridge)

        context = {"conversation_history": []}

        messages = brain._prepare_messages("First question", context)

        assert len(messages) == 2  # system + user
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_get_fallback_response(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        response = brain._get_fallback_response([{"role": "user", "content": "Hello"}])

        assert len(response) > 0
        assert isinstance(response, str)

    def test_init_uses_llm_request_timeout(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        assert brain.deepseek.request_timeout == 12
