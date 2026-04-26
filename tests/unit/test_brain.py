"""
Unit tests for brain system
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import json

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
    async def test_process_message_replays_only_executed_tool_call(
        self, mock_memory, mock_bridge
    ):
        brain = DevSynapseBrain(mock_memory, mock_bridge)
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
        tool_replay = replay_messages[-1]

        assert response == "Final answer"
        assert cmd is None
        assert usage is None
        assert assistant_replay["tool_calls"] == [
            {
                "id": "call_pwd",
                "type": "function",
                "function": {
                    "name": "bash",
                    "arguments": '{"command": "pwd"}',
                },
            }
        ]
        assert assistant_replay["reasoning_content"] == "I should inspect the repo."
        assert tool_replay == {
            "role": "tool",
            "tool_call_id": "call_pwd",
            "content": "tool output",
        }

    @pytest.mark.asyncio
    async def test_process_message_error_handling(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        # Mock the low-level Deepseek call to fail
        with patch.object(brain, '_call_deepseek_api', new_callable=AsyncMock) as mock_deepseek:
            mock_deepseek.side_effect = Exception("API connection failed")

            # Mock the degraded response to test it's called
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

        with patch('core.brain.requests.post') as mock_post:
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

            result = await brain._call_deepseek_api([{"role": "user", "content": "Hi"}])

            assert result.content == "Hello from Deepseek!"
            assert result.provider == "deepseek"
            assert result.usage["total_tokens"] == 26
            assert result.usage["prompt_cache_miss_tokens"] == 16
            assert result.usage["estimated_cost_usd"] == pytest.approx(0.00000504)

            call_kwargs = mock_post.call_args[1]
            payload = call_kwargs["json"]
            assert "tools" in payload
            assert len(payload["tools"]) == 6
            assert payload["tools"][0]["function"]["name"] == "bash"
            assert payload["tool_choice"] == "auto"
            assert payload["stream"] is False

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

    @pytest.mark.asyncio
    async def test_call_deepseek_api_error(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch('core.brain.requests.post') as mock_post:
            mock_post.side_effect = Exception("Connection refused")

            with pytest.raises(Exception):
                await brain._call_deepseek_api([{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_call_deepseek_api_with_tool_calls(self, mock_memory, mock_bridge):
        brain = DevSynapseBrain(mock_memory, mock_bridge)

        with patch('core.brain.requests.post') as mock_post:
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

            result = await brain._call_deepseek_api([{"role": "user", "content": "List files"}])

            assert result.content == ""
            assert result.tool_calls is not None
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0]["function"]["name"] == "bash"

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
            ('read "/tmp/test.py"', True),
            ('grep "TODO"', True),
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
        assert brain.request_timeout == 12
