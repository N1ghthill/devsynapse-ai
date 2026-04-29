"""
Unit tests for brain system
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.brain import DevSynapseBrain


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
    memory.review_completed_task = Mock()
    memory.record_agent_route_decision = Mock()
    memory.save_interaction = AsyncMock()
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
            from core.brain import LLMResult
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
            from core.brain import LLMResult

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
            from core.brain import LLMResult

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
        )
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

    @pytest.mark.asyncio
    async def test_process_message_streaming_autoexecutes_when_requested(
        self, mock_memory, mock_bridge
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        brain.api_key = "test-key"
        mock_bridge.execute_command = AsyncMock(
            return_value=(True, "ok", "tool output", "success", None, "devsynapse-ai")
        )

        async def stream_once(*args, **kwargs):
            del args, kwargs
            yield {"type": "text", "content": "Vou ler."}
            yield {
                "type": "done",
                "content": "Vou ler.",
                "usage": None,
                "tool_calls": [
                    {
                        "id": "call_read",
                        "type": "function",
                        "function": {
                            "name": "read",
                            "arguments": '{"path": "/tmp/file.txt"}',
                        },
                    }
                ],
            }

        async def stream_final(*args, **kwargs):
            del args, kwargs
            yield {"type": "text", "content": "Conteudo analisado."}
            yield {
                "type": "done",
                "content": "Conteudo analisado.",
                "usage": None,
                "tool_calls": None,
            }

        with patch.object(
            brain.deepseek,
            "chat_completion_streaming",
            side_effect=[stream_once(), stream_final()],
        ):
            events = [
                event
                async for event in brain.process_message_streaming(
                    "Leia o arquivo",
                    "test_session",
                    user_id="irving",
                    user_role="admin",
                    auto_execute=True,
                )
            ]

        assert [event["type"] for event in events] == [
            "text",
            "command",
            "command_status",
            "command_result",
            "text",
            "done",
        ]
        assert events[1]["command"] == 'read "/tmp/file.txt"'
        assert events[2]["status"] == "running"
        assert events[3]["status"] == "success"
        mock_bridge.execute_command.assert_awaited_once_with(
            'read "/tmp/file.txt"',
            user_id="irving",
            project_name=None,
            user_role="admin",
            project_mutation_allowlist=[],
        )
        mock_memory.save_command_execution.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_streaming_recovers_when_model_promises_action_without_tool(
        self, mock_memory, mock_bridge
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        brain.api_key = "test-key"
        mock_bridge.execute_command = AsyncMock(
            return_value=(True, "created", "write output", "success", None, "calculadora")
        )

        async def stream_stalled_intent(*args, **kwargs):
            del args, kwargs
            yield {"type": "text", "content": "Vou criar o código principal agora."}
            yield {
                "type": "done",
                "content": "Vou criar o código principal agora.",
                "usage": None,
                "tool_calls": None,
            }

        async def stream_retry_tool(*args, **kwargs):
            del args, kwargs
            yield {
                "type": "done",
                "content": "",
                "usage": None,
                "tool_calls": [
                    {
                        "id": "call_write",
                        "type": "function",
                        "function": {
                            "name": "write",
                            "arguments": json.dumps({
                                "path": "/tmp/calculadora/main.py",
                                "content": "print('ok')",
                            }),
                        },
                    }
                ],
            }

        async def stream_final(*args, **kwargs):
            del args, kwargs
            yield {"type": "text", "content": "Projeto criado."}
            yield {
                "type": "done",
                "content": "Projeto criado.",
                "usage": None,
                "tool_calls": None,
            }

        with patch.object(
            brain.deepseek,
            "chat_completion_streaming",
            side_effect=[stream_stalled_intent(), stream_retry_tool(), stream_final()],
        ):
            events = [
                event
                async for event in brain.process_message_streaming(
                    "Pode continuar",
                    "test_session",
                    user_id="irving",
                    user_role="admin",
                    auto_execute=True,
                )
            ]

        assert [event["type"] for event in events] == [
            "text",
            "command",
            "command_status",
            "command_result",
            "text",
            "done",
        ]
        assert events[1]["command"] == (
            'write "/tmp/calculadora/main.py" --content="print(\'ok\')"'
        )
        mock_bridge.execute_command.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_streaming_admin_auto_mode_replays_execution_failure(
        self, mock_memory, mock_bridge
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        brain.api_key = "test-key"
        mock_bridge.execute_command = AsyncMock(
            side_effect=[
                (False, "tests failed", "AssertionError", "failed", "execution_failed", "app"),
                (True, "fixed", "ok", "success", None, "app"),
            ]
        )

        async def stream_failing_command(*args, **kwargs):
            del args, kwargs
            yield {
                "type": "done",
                "content": "",
                "usage": None,
                "tool_calls": [
                    {
                        "id": "call_test",
                        "type": "function",
                        "function": {
                            "name": "bash",
                            "arguments": '{"command": "pytest -q"}',
                        },
                    }
                ],
            }

        async def stream_fix_command(*args, **kwargs):
            del args, kwargs
            yield {
                "type": "done",
                "content": "",
                "usage": None,
                "tool_calls": [
                    {
                        "id": "call_fix",
                        "type": "function",
                        "function": {
                            "name": "write",
                            "arguments": json.dumps({
                                "path": "/tmp/app.py",
                                "content": "print('fixed')",
                            }),
                        },
                    }
                ],
            }

        async def stream_final(*args, **kwargs):
            del args, kwargs
            yield {"type": "text", "content": "Corrigido e validado."}
            yield {
                "type": "done",
                "content": "Corrigido e validado.",
                "usage": None,
                "tool_calls": None,
            }

        with patch.object(
            brain.deepseek,
            "chat_completion_streaming",
            side_effect=[stream_failing_command(), stream_fix_command(), stream_final()],
        ) as mock_stream:
            events = [
                event
                async for event in brain.process_message_streaming(
                    "Rode os testes e corrija se falhar",
                    "test_session",
                    user_id="irving",
                    user_role="admin",
                    auto_execute=True,
                )
            ]

        event_types = [event["type"] for event in events]
        assert event_types == [
            "command",
            "command_status",
            "command_result",
            "command",
            "command_status",
            "command_result",
            "text",
            "done",
        ]
        assert events[2]["status"] == "failed"
        assert events[2]["reason_code"] == "execution_failed"
        assert events[3]["command"] == 'write "/tmp/app.py" --content="print(\'fixed\')"'
        replay_messages = mock_stream.call_args_list[1].args[0]
        assert any("AssertionError" in message["content"] for message in replay_messages)
        assert mock_bridge.execute_command.await_count == 2

    @pytest.mark.asyncio
    async def test_streaming_recovers_when_action_request_gets_empty_response(
        self, mock_memory, mock_bridge
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        brain.api_key = "test-key"
        mock_bridge.execute_command = AsyncMock(
            return_value=(True, "created", "write output", "success", None, "calculadora")
        )

        async def stream_empty_done(*args, **kwargs):
            del args, kwargs
            yield {
                "type": "done",
                "content": "",
                "usage": {"total_tokens": 10},
                "tool_calls": None,
            }

        async def stream_retry_tool(*args, **kwargs):
            del args, kwargs
            yield {
                "type": "done",
                "content": "",
                "usage": {"total_tokens": 5},
                "tool_calls": [
                    {
                        "id": "call_write",
                        "type": "function",
                        "function": {
                            "name": "write",
                            "arguments": json.dumps({
                                "path": "/tmp/calculadora/main.py",
                                "content": "print('ok')",
                            }),
                        },
                    }
                ],
            }

        async def stream_final(*args, **kwargs):
            del args, kwargs
            yield {"type": "text", "content": "Projeto criado."}
            yield {
                "type": "done",
                "content": "Projeto criado.",
                "usage": None,
                "tool_calls": None,
            }

        with patch.object(
            brain.deepseek,
            "chat_completion_streaming",
            side_effect=[stream_empty_done(), stream_retry_tool(), stream_final()],
        ) as mock_stream:
            events = [
                event
                async for event in brain.process_message_streaming(
                    "Crie uma calculadora gráfica em Python",
                    "test_session",
                    user_id="irving",
                    user_role="admin",
                    auto_execute=True,
                )
            ]

        assert [event["type"] for event in events] == [
            "command",
            "command_status",
            "command_result",
            "text",
            "done",
        ]
        assert events[0]["command"] == (
            'write "/tmp/calculadora/main.py" --content="print(\'ok\')"'
        )
        repair_messages = mock_stream.call_args_list[1].args[0]
        assert "CRITICAL TOOL REPAIR" in repair_messages[0]["content"]
        mock_bridge.execute_command.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_streaming_filters_provider_reasoning_from_client(
        self, mock_memory, mock_bridge
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        brain.api_key = "test-key"

        async def stream_with_reasoning(*args, **kwargs):
            del args, kwargs
            yield {"type": "reasoning", "content": "internal chain of thought"}
            yield {"type": "text", "content": "Resposta final."}
            yield {
                "type": "done",
                "content": "Resposta final.",
                "usage": None,
                "tool_calls": None,
            }

        with patch.object(
            brain.deepseek,
            "chat_completion_streaming",
            side_effect=[stream_with_reasoning()],
        ):
            events = [
                event
                async for event in brain.process_message_streaming(
                    "Olá",
                    "test_session",
                    user_id="irving",
                    user_role="admin",
                    auto_execute=True,
                )
            ]

        assert [event["type"] for event in events] == ["text", "done"]
        assert all(event.get("content") != "internal chain of thought" for event in events)

    @pytest.mark.asyncio
    async def test_process_message_error_handling(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        brain.api_key = "test-key"

        with patch.object(brain.deepseek, 'chat_completion') as mock_chat:
            mock_chat.side_effect = Exception("API connection failed")

            with patch.object(brain, '_get_fallback_response') as mock_fallback:
                mock_fallback.return_value = "Fallback response"

                response, cmd, usage = await brain.process_message("Hello", "test_session")

                assert response == "Fallback response"
                assert cmd is None
                assert usage is None
                mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_deepseek_api_success(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch('core.deepseek.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Hello from Deepseek!", "role": "assistant"}}],
                "model": "deepseek-chat",
                "usage": {
                    "prompt_tokens": 16,
                    "completion_tokens": 10,
                    "total_tokens": 26,
                },
            }
            mock_post.return_value = mock_response

            result = brain.deepseek.chat_completion(
                [{"role": "user", "content": "Hi"}],
                tools=[],
            )

            assert result["content"] == "Hello from Deepseek!"
            assert result["provider"] == "deepseek"
            assert result["usage"]["total_tokens"] == 26
            assert result["usage"]["prompt_cache_miss_tokens"] == 16
            assert result["usage"]["estimated_cost_usd"] == pytest.approx(0.00000504)

    def test_merge_usage_adds_prompt_tokens_and_cost(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        merged = brain._merge_usage(
            {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_cache_hit_tokens": 40,
                "prompt_cache_miss_tokens": 60,
                "reasoning_tokens": 0,
                "estimated_cost_usd": 0.00002,
            },
            {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "total_tokens": 60,
                "prompt_cache_hit_tokens": 10,
                "prompt_cache_miss_tokens": 40,
                "reasoning_tokens": 0,
                "estimated_cost_usd": 0.00001,
            },
        )

        assert merged["prompt_tokens"] == 150
        assert merged["completion_tokens"] == 30
        assert merged["total_tokens"] == 180
        assert merged["prompt_cache_hit_tokens"] == 50
        assert merged["prompt_cache_miss_tokens"] == 100
        assert merged["estimated_cost_usd"] == pytest.approx(0.00003)

    def test_select_llm_route_uses_flash_for_simple_work(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        route = brain._select_llm_route("Explique dependency injection", {})

        assert route.model == "deepseek-v4-flash"
        assert route.fallback_model == "deepseek-v4-pro"

    def test_select_llm_route_forces_flash_on_critical_budget(self, mock_memory, mock_bridge):
        mock_memory.get_llm_budget_status.return_value = {"overall_status": "critical"}
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        route = brain._select_llm_route("Desenhe uma arquitetura de cache", {})

        assert route.model == "deepseek-v4-flash"
        assert route.budget_mode == "economy"
        assert route.fallback_model is None

    def test_select_llm_route_uses_agent_learning(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
        mock_memory.get_agent_learning.return_value = {
            "preferred_model": "deepseek-v4-pro",
            "confidence": 0.8,
            "learned_reason": "feedback_negative",
        }

        route = brain._select_llm_route("Explique esse erro simples", {})

        assert route.model == "deepseek-v4-pro"
        assert route.learned_preference == "deepseek-v4-pro"

    @pytest.mark.asyncio
    async def test_call_llm_api_falls_back_from_flash_to_pro(self, mock_memory, mock_bridge):
        from core.llm_optimization import ModelRoute

        brain = DevSynapseBrain(mock_memory, mock_bridge)
        brain.api_key = "test-key"

        with patch.object(brain.deepseek, "chat_completion") as mock_chat:
            mock_chat.side_effect = [
                Exception("flash unavailable"),
                {
                    "content": "Pro response",
                    "provider": "deepseek",
                    "model": "deepseek-v4-pro",
                    "usage": {"total_tokens": 1},
                    "tool_calls": None,
                    "reasoning_content": None,
                },
            ]

            result = await brain._call_llm_api(
                [{"role": "user", "content": "Hi"}],
                route=ModelRoute(
                    model="deepseek-v4-flash",
                    complexity="simple",
                    reason="test",
                    fallback_model="deepseek-v4-pro",
                ),
            )

        assert result.content == "Pro response"
        assert result.model == "deepseek-v4-pro"
        assert mock_chat.call_args_list[0].kwargs["model"] == "deepseek-v4-flash"
        assert mock_chat.call_args_list[1].kwargs["model"] == "deepseek-v4-pro"

    @pytest.mark.asyncio
    async def test_call_deepseek_api_error(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch('core.deepseek.requests.post') as mock_post:
            mock_post.side_effect = Exception("Connection refused")

            with pytest.raises(Exception):
                brain.deepseek.chat_completion(
                    [{"role": "user", "content": "Hi"}],
                    tools=[],
                )

    @pytest.mark.asyncio
    async def test_call_deepseek_api_with_tool_calls(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch('core.deepseek.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_xyz",
                                    "type": "function",
                                    "function": {
                                        "name": "bash",
                                        "arguments": '{"command": "ls -la"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
                "model": "deepseek-chat",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
            mock_post.return_value = mock_response

            result = brain.deepseek.chat_completion(
                [{"role": "user", "content": "List files"}],
                tools=[],
            )

            assert result["content"] == ""
            assert result["tool_calls"] is not None
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["function"]["name"] == "bash"

    def test_extract_opencode_command_bash(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        command = brain._extract_opencode_command('Vou listar: bash "ls -la"')
        assert command == 'bash "ls -la"'

    def test_extract_opencode_command_read(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        command = brain._extract_opencode_command('Deixe-me ler: read "/path/to/file.py"')
        assert command == 'read "/path/to/file.py"'

    def test_extract_opencode_command_write(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        response = (
            'Vou criar o arquivo: write "/tmp/test.md" '
            '--content="# Teste\\n\\nConteudo de exemplo."'
        )
        command = brain._extract_opencode_command(response)
        assert command == 'write "/tmp/test.md" --content="# Teste\\n\\nConteudo de exemplo."'

    def test_extract_opencode_command_prefers_last_command(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        response = (
            'Primeiro vou localizar: bash "find /tmp -name test" '
            'depois ler: read "/tmp/test.md" '
            'e por fim criar: write "/tmp/out.md" --content="ok"'
        )
        command = brain._extract_opencode_command(response)
        assert command == 'write "/tmp/out.md" --content="ok"'

    def test_extract_opencode_command_normalizes_unquoted_bash_line(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        response = "Vou listar a pasta agora.\n`bash ls -la /workspace/repos`"
        command = brain._extract_opencode_command(response)
        assert command == 'bash "ls -la /workspace/repos"'

    def test_extract_opencode_command_normalizes_bare_shell_line(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        response = "docker ps"
        command = brain._extract_opencode_command(response)
        assert command == 'bash "docker ps"'

    def test_extract_opencode_command_normalizes_touch_line(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        response = "touch /workspace/TESTE_ESCRITA.md"
        command = brain._extract_opencode_command(response)
        assert command == 'bash "touch /workspace/TESTE_ESCRITA.md"'

    def test_extract_opencode_command_none(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        command = brain._extract_opencode_command("This is just a regular conversation response")
        assert command is None

    def test_tool_calls_to_opencode_command_bash(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "bash", "arguments": '{"command": "git status"}'},
            }
        ]
        command = brain._tool_calls_to_opencode_command(tool_calls)
        assert command == 'bash "git status"'

    def test_tool_calls_to_opencode_command_read(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        tool_calls = [
            {
                "id": "call_2",
                "type": "function",
                "function": {"name": "read", "arguments": '{"path": "/tmp/test.py"}'},
            }
        ]
        command = brain._tool_calls_to_opencode_command(tool_calls)
        assert command == 'read "/tmp/test.py"'

    def test_tool_calls_to_opencode_command_edit(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        tool_calls = [
            {
                "id": "call_3",
                "type": "function",
                "function": {
                    "name": "edit",
                    "arguments": '{"path": "/tmp/f.py", "old": "foo", "new": "bar"}',
                },
            }
        ]
        command = brain._tool_calls_to_opencode_command(tool_calls)
        assert command == 'edit "/tmp/f.py" --old="foo" --new="bar"'

    def test_tool_calls_to_opencode_command_write(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        tool_calls = [
            {
                "id": "call_4",
                "type": "function",
                "function": {
                    "name": "write",
                    "arguments": '{"path": "/tmp/out.md", "content": "# Hello"}',
                },
            }
        ]
        command = brain._tool_calls_to_opencode_command(tool_calls)
        assert command == 'write "/tmp/out.md" --content="# Hello"'

    def test_tool_calls_to_opencode_command_escapes_quoted_content(
        self, mock_memory, mock_bridge
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        tool_calls = [
            {
                "id": "call_5",
                "type": "function",
                "function": {
                    "name": "write",
                    "arguments": json.dumps({
                        "path": "/tmp/out.py",
                        "content": 'print("hi")\npath = "C:\\tmp"',
                    }),
                },
            }
        ]

        command = brain._tool_calls_to_opencode_command(tool_calls)

        assert command == (
            'write "/tmp/out.py" --content="print(\\"hi\\")\\n'
            'path = \\"C:\\\\tmp\\""'
        )

    def test_tool_calls_to_opencode_command_none(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        assert brain._tool_calls_to_opencode_command(None) is None
        assert brain._tool_calls_to_opencode_command([]) is None

    @pytest.mark.parametrize(
        ("command", "expected"),
        [
            ('read "/tmp/test.py"', False),
            ('grep "TODO"', False),
            ('glob "**/*.py"', False),
            ('bash "ls -la"', True),
            ('bash "pwd"', True),
            ('bash "git status --short"', True),
            ('bash "git diff -- README.md"', True),
            ('bash "git checkout main"', False),
            ('bash "git diff --output=patch.txt"', False),
            ('bash "curl https://example.com"', False),
            ('bash "npm test"', False),
            ('bash "python script.py"', False),
            ('bash "tar -xf archive.tar"', False),
        ],
    )
    def test_is_read_only_command_is_conservative_for_autoexec(
        self, mock_memory, mock_bridge, command, expected
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        assert brain._is_read_only_command(command) is expected

    @pytest.mark.parametrize(
        "command",
        [
            'read "/home/irving/.ssh/id_rsa"',
            'grep "DEEPSEEK_API_KEY"',
            'glob "/etc/*"',
            'write "/tmp/out.txt" --content="hello"',
            'edit "/tmp/out.txt" --old="hello" --new="bye"',
            'bash "npm test && npm run build"',
        ],
    )
    def test_can_autoexecute_command_allows_admin_tools(
        self, mock_memory, mock_bridge, command
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        assert brain._can_autoexecute_command(command, user_role="admin") is True

    def test_can_autoexecute_command_blocks_blacklisted_admin_command(
        self, mock_memory, mock_bridge
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        assert brain._can_autoexecute_command('bash "rm -rf /"', user_role="admin") is False

    def test_admin_auto_mode_gets_larger_iteration_budget(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        assert brain._max_autoexec_rounds(auto_execute=True, user_role="admin") == 20
        assert brain._max_autoexec_rounds(auto_execute=True, user_role="user") == 8
        assert brain._max_autoexec_rounds(auto_execute=False, user_role="admin") == 5

    def test_prepare_messages_with_history(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        context = {
            "conversation_history": [
                {"role": "user", "content": "Previous question"},
                {"role": "assistant", "content": "Previous answer"}
            ]
        }

        messages = brain._prepare_messages("New question", context)

        assert len(messages) == 4  # system + 2 history + user
        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "New question"

    def test_prepare_messages_no_history(self, mock_memory, mock_bridge):
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
